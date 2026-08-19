from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import asyncio
import csv
import io
import logging
import os
import re
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.cors import CORSMiddleware

from auth import create_access_token, require_admin, verify_admin
from db import SessionLocal, engine, get_session
from models import Answer, Attempt, Base, Participant, Question, QuestionSet
from parser import parse_questions

TOTAL_QUESTIONS = 20
NUM_SETS = 20

app = FastAPI(title="MEP Quiz")
api = APIRouter(prefix="/api")
logger = logging.getLogger("mepquiz")
logging.basicConfig(level=logging.INFO)


# ----------------------------- schemas -----------------------------
class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    phone: str
    school: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def check_phone(cls, v: str) -> str:
        digits = re.sub(r"\D", "", v or "")
        if len(digits) < 10 or len(digits) > 15:
            raise ValueError("Enter a valid phone number (10-15 digits)")
        return digits[-10:] if len(digits) > 10 and digits.startswith("91") and len(digits) == 12 else digits

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        v = " ".join(v.split())
        if not re.match(r"^[A-Za-z][A-Za-z\s.'\-]*$", v):
            raise ValueError("Name may only contain letters, spaces, apostrophes and hyphens")
        return v


class AnswerIn(BaseModel):
    question_id: int
    selected_option: str

    @field_validator("selected_option")
    @classmethod
    def check_opt(cls, v: str) -> str:
        v = (v or "").strip().upper()
        if v not in {"A", "B", "C", "D"}:
            raise ValueError("selected_option must be one of A, B, C, D")
        return v


class AdminLoginIn(BaseModel):
    username: str
    password: str


class QuestionIn(BaseModel):
    question_text: str = Field(min_length=3)
    options: dict
    correct_option: str
    category: Optional[str] = None
    order_index: Optional[int] = None

    @field_validator("options")
    @classmethod
    def check_options(cls, v: dict) -> dict:
        keys = {"A", "B", "C", "D"}
        v = {str(k).upper(): str(val) for k, val in (v or {}).items()}
        if set(v.keys()) != keys or any(not val.strip() for val in v.values()):
            raise ValueError("options must contain non-empty A, B, C and D")
        return v

    @field_validator("correct_option")
    @classmethod
    def check_correct(cls, v: str) -> str:
        v = (v or "").strip().upper()
        if v not in {"A", "B", "C", "D"}:
            raise ValueError("correct_option must be one of A, B, C, D")
        return v


class ImportIn(BaseModel):
    raw_text: str
    replace: bool = False


# ----------------------------- helpers -----------------------------
async def load_attempt(session: AsyncSession, token: str) -> Attempt:
    try:
        res = await session.execute(select(Attempt).where(Attempt.token == token))
    except Exception:
        raise HTTPException(status_code=404, detail="Attempt not found")
    attempt = res.scalar_one_or_none()
    if attempt is None:
        raise HTTPException(status_code=404, detail="Attempt not found")
    return attempt


async def answered_count(session: AsyncSession, attempt_id: int) -> int:
    res = await session.execute(select(func.count(Answer.id)).where(Answer.attempt_id == attempt_id))
    return res.scalar_one()


def elapsed_seconds(attempt: Attempt) -> int:
    end = attempt.completed_at or datetime.now(timezone.utc)
    return max(0, int((end - attempt.started_at).total_seconds()))


async def finalize(session: AsyncSession, attempt: Attempt) -> None:
    res = await session.execute(
        select(func.count(Answer.id)).where(Answer.attempt_id == attempt.id, Answer.is_correct.is_(True))
    )
    score = res.scalar_one()
    attempt.completed_at = datetime.now(timezone.utc)
    attempt.time_taken_seconds = elapsed_seconds(attempt)
    attempt.score = score
    await session.commit()


# ----------------------------- participant -----------------------------
@api.get("/")
async def root():
    return {"service": "MEP Quiz", "status": "ok"}


@api.get("/health")
async def health(session: AsyncSession = Depends(get_session)):
    await session.execute(text("SELECT 1"))
    sets = await session.scalar(select(func.count(QuestionSet.id)))
    return {"status": "ok", "database": "postgresql", "question_sets": sets or 0}


@api.post("/register")
async def register(payload: RegisterIn, session: AsyncSession = Depends(get_session)):
    email = payload.email.lower().strip()
    existing = await session.execute(
        select(Participant).where((Participant.email == email) | (Participant.phone == payload.phone))
    )
    dup = existing.scalars().first()
    if dup:
        field = "email" if dup.email == email else "phone number"
        raise HTTPException(status_code=409, detail=f"This {field} has already been used. One entry per person.")

    participant = Participant(name=payload.name, email=email, phone=payload.phone,
                              school=(payload.school or "").strip() or None)
    session.add(participant)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="This email or phone number has already been used.")

    # Least-loaded set assignment, safe under concurrent bursts.
    row = None
    for attempt_no in range(40):
        if attempt_no:
            await asyncio.sleep(0.02)
        res = await session.execute(
            text(
                "SELECT id, name FROM question_sets "
                "WHERE id IN (SELECT DISTINCT set_id FROM questions) "
                "ORDER BY attempt_count ASC, id ASC FOR UPDATE SKIP LOCKED LIMIT 1"
            )
        )
        row = res.first()
        if row:
            break
    if row is None:
        await session.rollback()
        raise HTTPException(status_code=503, detail="No question sets available. Please contact the organisers.")

    await session.execute(
        update(QuestionSet).where(QuestionSet.id == row[0]).values(attempt_count=QuestionSet.attempt_count + 1)
    )
    attempt = Attempt(participant_id=participant.id, set_id=row[0])
    session.add(attempt)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="This email or phone number has already been used.")
    await session.refresh(attempt)
    return {
        "attempt_token": str(attempt.token),
        "set_name": row[1],
        "total_questions": TOTAL_QUESTIONS,
        "started_at": attempt.started_at.isoformat(),
    }


@api.get("/attempt/{token}/state")
async def attempt_state(token: str, session: AsyncSession = Depends(get_session)):
    attempt = await load_attempt(session, token)
    count = await answered_count(session, attempt.id)
    total = await session.scalar(select(func.count(Question.id)).where(Question.set_id == attempt.set_id))
    return {
        "answered": count,
        "total_questions": min(total or 0, TOTAL_QUESTIONS),
        "elapsed_seconds": elapsed_seconds(attempt),
        "completed": attempt.completed_at is not None,
    }


@api.get("/attempt/{token}/question")
async def current_question(token: str, session: AsyncSession = Depends(get_session)):
    attempt = await load_attempt(session, token)
    if attempt.completed_at is not None:
        return {"completed": True}
    idx = await answered_count(session, attempt.id)
    res = await session.execute(
        select(Question)
        .where(Question.set_id == attempt.set_id)
        .order_by(Question.order_index, Question.id)
        .offset(idx)
        .limit(1)
    )
    q = res.scalar_one_or_none()
    if q is None:
        await finalize(session, attempt)
        return {"completed": True}
    return {
        "completed": False,
        "question": {
            "id": q.id,
            "question_text": q.question_text,
            "options": q.options,
            "category": q.category,
        },
        "index": idx + 1,
        "total_questions": TOTAL_QUESTIONS,
        "elapsed_seconds": elapsed_seconds(attempt),
    }


@api.post("/attempt/{token}/answer")
async def submit_answer(token: str, payload: AnswerIn, session: AsyncSession = Depends(get_session)):
    attempt = await load_attempt(session, token)
    if attempt.completed_at is not None:
        raise HTTPException(status_code=409, detail="This attempt is already complete.")
    q = await session.get(Question, payload.question_id)
    if q is None or q.set_id != attempt.set_id:
        raise HTTPException(status_code=400, detail="Question does not belong to this attempt.")
    session.add(Answer(
        attempt_id=attempt.id,
        question_id=q.id,
        selected_option=payload.selected_option,
        is_correct=payload.selected_option == q.correct_option,
    ))
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="This question has already been answered.")
    count = await answered_count(session, attempt.id)
    total = await session.scalar(select(func.count(Question.id)).where(Question.set_id == attempt.set_id))
    done = count >= min(total or 0, TOTAL_QUESTIONS)
    if done:
        await finalize(session, attempt)
    return {"answered": count, "completed": done}


# ----------------------------- admin -----------------------------
@api.post("/admin/login")
async def admin_login(payload: AdminLoginIn):
    if not verify_admin(payload.username.strip(), payload.password):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return {"access_token": create_access_token(payload.username.strip()), "username": payload.username.strip()}


@api.get("/admin/me")
async def admin_me(admin: str = Depends(require_admin)):
    return {"username": admin, "role": "admin"}


@api.get("/admin/stats")
async def admin_stats(admin: str = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    total = await session.scalar(select(func.count(Participant.id))) or 0
    completed = await session.scalar(select(func.count(Attempt.id)).where(Attempt.completed_at.isnot(None))) or 0
    avg_score = await session.scalar(select(func.avg(Attempt.score)).where(Attempt.completed_at.isnot(None)))
    avg_time = await session.scalar(select(func.avg(Attempt.time_taken_seconds)).where(Attempt.completed_at.isnot(None)))
    return {
        "total_participants": total,
        "completed": completed,
        "avg_score": round(float(avg_score), 2) if avg_score is not None else 0,
        "avg_time_seconds": int(avg_time) if avg_time is not None else 0,
        "completion_rate": round(completed / total * 100, 1) if total else 0.0,
    }


async def _rows(session: AsyncSession, search: str = "", sort: str = "created_at", direction: str = "desc"):
    stmt = (
        select(Participant, Attempt, QuestionSet.name)
        .join(Attempt, Attempt.participant_id == Participant.id, isouter=True)
        .join(QuestionSet, QuestionSet.id == Attempt.set_id, isouter=True)
    )
    if search:
        like = f"%{search.lower()}%"
        stmt = stmt.where(
            func.lower(Participant.name).like(like)
            | func.lower(Participant.email).like(like)
            | func.lower(func.coalesce(Participant.school, "")).like(like)
            | Participant.phone.like(like)
        )
    cols = {
        "name": Participant.name, "email": Participant.email, "school": Participant.school,
        "set": QuestionSet.name, "score": Attempt.score, "time": Attempt.time_taken_seconds,
        "completed_at": Attempt.completed_at, "created_at": Participant.created_at,
    }
    col = cols.get(sort, Participant.created_at)
    stmt = stmt.order_by(col.desc().nullslast() if direction == "desc" else col.asc().nullslast())
    res = await session.execute(stmt)
    out = []
    for p, a, set_name in res.all():
        out.append({
            "id": p.id, "name": p.name, "email": p.email, "phone": p.phone,
            "school": p.school, "set": set_name, "score": a.score if a else None,
            "time_taken_seconds": a.time_taken_seconds if a else None,
            "completed_at": a.completed_at.isoformat() if a and a.completed_at else None,
            "created_at": p.created_at.isoformat(),
        })
    return out


@api.get("/admin/participants")
async def admin_participants(
    search: str = "", sort: str = "created_at", direction: str = "desc",
    admin: str = Depends(require_admin), session: AsyncSession = Depends(get_session),
):
    return await _rows(session, search, sort, direction)


@api.get("/admin/leaderboard")
async def admin_leaderboard(
    limit: int = Query(20, le=200), admin: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    res = await session.execute(
        select(Participant.name, Participant.school, QuestionSet.name, Attempt.score, Attempt.time_taken_seconds)
        .join(Attempt, Attempt.participant_id == Participant.id)
        .join(QuestionSet, QuestionSet.id == Attempt.set_id)
        .where(Attempt.completed_at.isnot(None))
        .order_by(Attempt.score.desc(), Attempt.time_taken_seconds.asc())
        .limit(limit)
    )
    return [
        {"rank": i, "name": n, "school": s, "set": sn, "score": sc, "time_taken_seconds": t}
        for i, (n, s, sn, sc, t) in enumerate(res.all(), start=1)
    ]


@api.get("/admin/health-check")
async def admin_health_check(admin: str = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    """Pre-event readiness: flags sets missing questions, options or correct answers."""
    res = await session.execute(select(QuestionSet).order_by(QuestionSet.id))
    sets = res.scalars().all()
    report = []
    for qs in sets:
        qres = await session.execute(
            select(Question).where(Question.set_id == qs.id).order_by(Question.order_index, Question.id)
        )
        questions = qres.scalars().all()
        issues, warnings = [], []
        if len(questions) < TOTAL_QUESTIONS:
            issues.append(f"Only {len(questions)} of {TOTAL_QUESTIONS} questions")
        elif len(questions) > TOTAL_QUESTIONS:
            warnings.append(f"{len(questions)} questions — only the first {TOTAL_QUESTIONS} will be served")
        for i, q in enumerate(questions, start=1):
            opts = q.options or {}
            missing = [l for l in ("A", "B", "C", "D") if not str(opts.get(l, "")).strip()]
            if missing:
                issues.append(f"Q{i}: missing option {', '.join(missing)}")
            if q.correct_option not in ("A", "B", "C", "D"):
                issues.append(f"Q{i}: invalid correct answer")
            elif not str(opts.get(q.correct_option, "")).strip():
                issues.append(f"Q{i}: correct answer {q.correct_option} has no text")
            if not (q.question_text or "").strip():
                issues.append(f"Q{i}: empty question text")
        texts = [(q.question_text or "").strip().lower() for q in questions]
        dupes = {t for t in texts if t and texts.count(t) > 1}
        if dupes:
            issues.append(f"{len(dupes)} duplicate question text(s)")
        report.append({
            "set_id": qs.id,
            "name": qs.name,
            "question_count": len(questions),
            "attempt_count": qs.attempt_count,
            "ready": not issues,
            "issues": issues,
            "warnings": warnings,
        })
    ready_sets = sum(1 for r in report if r["ready"])
    return {
        "total_sets": len(report),
        "ready_sets": ready_sets,
        "blocked_sets": len(report) - ready_sets,
        "event_ready": ready_sets == len(report) and len(report) > 0,
        "sets": report,
    }


@api.get("/admin/export.csv")
async def admin_export(admin: str = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    rows = await _rows(session, "", "created_at", "asc")
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=[
        "name", "email", "phone", "school", "set", "score", "time_taken_seconds", "completed_at", "created_at"
    ], extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=mep-quiz-participants.csv"},
    )


@api.get("/admin/sets")
async def admin_sets(admin: str = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    res = await session.execute(
        select(QuestionSet.id, QuestionSet.name, QuestionSet.attempt_count, func.count(Question.id))
        .join(Question, Question.set_id == QuestionSet.id, isouter=True)
        .group_by(QuestionSet.id)
        .order_by(QuestionSet.id)
    )
    return [{"id": i, "name": n, "attempt_count": ac, "question_count": qc} for i, n, ac, qc in res.all()]


@api.get("/admin/sets/{set_id}/questions")
async def admin_set_questions(set_id: int, admin: str = Depends(require_admin),
                              session: AsyncSession = Depends(get_session)):
    res = await session.execute(
        select(Question).where(Question.set_id == set_id).order_by(Question.order_index, Question.id)
    )
    return [
        {"id": q.id, "question_text": q.question_text, "options": q.options,
         "correct_option": q.correct_option, "category": q.category, "order_index": q.order_index}
        for q in res.scalars().all()
    ]


@api.post("/admin/sets/{set_id}/questions")
async def admin_create_question(set_id: int, payload: QuestionIn, admin: str = Depends(require_admin),
                                session: AsyncSession = Depends(get_session)):
    if await session.get(QuestionSet, set_id) is None:
        raise HTTPException(status_code=404, detail="Question set not found")
    next_idx = payload.order_index
    if next_idx is None:
        next_idx = (await session.scalar(
            select(func.coalesce(func.max(Question.order_index), 0)).where(Question.set_id == set_id)
        )) + 1
    q = Question(set_id=set_id, question_text=payload.question_text, options=payload.options,
                 correct_option=payload.correct_option, category=payload.category, order_index=next_idx)
    session.add(q)
    await session.commit()
    return {"id": q.id}


@api.put("/admin/questions/{question_id}")
async def admin_update_question(question_id: int, payload: QuestionIn, admin: str = Depends(require_admin),
                                session: AsyncSession = Depends(get_session)):
    q = await session.get(Question, question_id)
    if q is None:
        raise HTTPException(status_code=404, detail="Question not found")
    q.question_text = payload.question_text
    q.options = payload.options
    q.correct_option = payload.correct_option
    q.category = payload.category
    if payload.order_index is not None:
        q.order_index = payload.order_index
    await session.commit()
    return {"id": q.id}


@api.delete("/admin/questions/{question_id}")
async def admin_delete_question(question_id: int, admin: str = Depends(require_admin),
                               session: AsyncSession = Depends(get_session)):
    q = await session.get(Question, question_id)
    if q is None:
        raise HTTPException(status_code=404, detail="Question not found")
    await session.delete(q)
    await session.commit()
    return {"deleted": question_id}


@api.post("/admin/sets/{set_id}/import")
async def admin_import(set_id: int, payload: ImportIn, admin: str = Depends(require_admin),
                       session: AsyncSession = Depends(get_session)):
    if await session.get(QuestionSet, set_id) is None:
        raise HTTPException(status_code=404, detail="Question set not found")
    parsed, errors = parse_questions(payload.raw_text)
    if not parsed:
        return {"imported": 0, "errors": errors or ["Nothing could be parsed from the pasted text."]}
    if payload.replace:
        await session.execute(delete(Question).where(Question.set_id == set_id))
        start = 0
    else:
        start = await session.scalar(
            select(func.coalesce(func.max(Question.order_index), 0)).where(Question.set_id == set_id)
        )
    for i, item in enumerate(parsed, start=1):
        session.add(Question(set_id=set_id, order_index=start + i, **item))
    await session.commit()
    return {"imported": len(parsed), "errors": errors}


@api.post("/admin/reset-attempts")
async def admin_reset(admin: str = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    await session.execute(delete(Answer))
    await session.execute(delete(Attempt))
    await session.execute(delete(Participant))
    await session.execute(update(QuestionSet).values(attempt_count=0))
    await session.commit()
    return {"reset": True}


app.include_router(api)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    from seed import seed_sets
    async with SessionLocal() as session:
        await seed_sets(session)


@app.on_event("shutdown")
async def shutdown():
    await engine.dispose()
