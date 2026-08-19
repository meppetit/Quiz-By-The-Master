"""Shuffle option order for every question in place (direct DB, fast)."""
import asyncio
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / "backend" / ".env")

from sqlalchemy import select  # noqa: E402

from db import SessionLocal, engine  # noqa: E402
from models import Question  # noqa: E402

LETTERS = ["A", "B", "C", "D"]


async def main():
    random.seed(20260819)
    async with SessionLocal() as session:
        rows = (await session.execute(select(Question).order_by(Question.set_id, Question.order_index))).scalars().all()
        for q in rows:
            correct_text = q.options[q.correct_option]
            texts = [q.options[l] for l in LETTERS]
            random.shuffle(texts)
            options = dict(zip(LETTERS, texts))
            q.options = options
            q.correct_option = next(l for l in LETTERS if options[l] == correct_text)
        await session.commit()
        print("shuffled", len(rows), "questions")
    await engine.dispose()


asyncio.run(main())
