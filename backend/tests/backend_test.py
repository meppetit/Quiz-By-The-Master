"""MEP Quiz backend tests.

Covers: registration validation/dedup, least-loaded set assignment, concurrency burst,
quiz integrity (no correct_option leaks, cross-set rejection), server-side scoring,
duplicate answer rejection, admin auth+endpoints, CSV export, question CRUD & import.
"""
import asyncio
import csv
import io
import os
import random
import string
import time

import aiohttp
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://quiz-burst-mep.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
ADMIN_USER = "admin"
ADMIN_PASS = "mepquiz2026"


def _rand_suffix(n=8):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


def _phone():
    return "9" + "".join(random.choices(string.digits, k=9))


@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(f"{API}/admin/login", json={"username": ADMIN_USER, "password": ADMIN_PASS})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="session", autouse=True)
def _reset(admin_headers):
    r = requests.post(f"{API}/admin/reset-attempts", headers=admin_headers)
    assert r.status_code == 200
    yield


# --------------- Admin auth ---------------
class TestAdminAuth:
    def test_login_ok(self):
        r = requests.post(f"{API}/admin/login", json={"username": ADMIN_USER, "password": ADMIN_PASS})
        assert r.status_code == 200
        assert "access_token" in r.json()

    def test_login_bad(self):
        r = requests.post(f"{API}/admin/login", json={"username": ADMIN_USER, "password": "wrong"})
        assert r.status_code == 401

    def test_admin_endpoints_require_bearer(self):
        for path in ["/admin/stats", "/admin/participants", "/admin/leaderboard", "/admin/sets"]:
            r = requests.get(f"{API}{path}")
            assert r.status_code == 401, path


# --------------- Registration ---------------
class TestRegistration:
    def test_register_valid(self):
        payload = {"name": "Test User", "email": f"TEST_{_rand_suffix()}@example.com",
                   "phone": _phone(), "school": "Demo"}
        r = requests.post(f"{API}/register", json=payload)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["total_questions"] == 20
        assert "attempt_token" in d
        assert "started_at" in d

    def test_missing_name(self):
        r = requests.post(f"{API}/register", json={"email": f"a{_rand_suffix()}@x.com", "phone": _phone()})
        assert r.status_code == 422

    def test_bad_email(self):
        r = requests.post(f"{API}/register", json={"name": "Alice", "email": "not-an-email", "phone": _phone()})
        assert r.status_code == 422

    def test_short_phone(self):
        r = requests.post(f"{API}/register", json={"name": "Alice", "email": f"b{_rand_suffix()}@x.com", "phone": "12345"})
        assert r.status_code == 422

    def test_duplicate_email_and_phone(self):
        email = f"TEST_dup_{_rand_suffix()}@example.com"
        phone = _phone()
        r1 = requests.post(f"{API}/register", json={"name": "Alice", "email": email, "phone": phone})
        assert r1.status_code == 200
        # duplicate email, new phone
        r2 = requests.post(f"{API}/register", json={"name": "Bob", "email": email, "phone": _phone()})
        assert r2.status_code == 409
        # duplicate phone, new email
        r3 = requests.post(f"{API}/register", json={"name": "Bob", "email": f"c{_rand_suffix()}@x.com", "phone": phone})
        assert r3.status_code == 409


# --------------- Least-loaded set assignment ---------------
class TestSetAssignment:
    def test_sequential_least_loaded(self, admin_headers):
        # After reset (session scoped), register N to observe spread.
        # NOTE: we cannot re-reset here because other tests already added ~4 registrations.
        # So do a fresh admin reset then run.
        requests.post(f"{API}/admin/reset-attempts", headers=admin_headers)
        for _ in range(20):
            r = requests.post(f"{API}/register", json={
                "name": "Seq User", "email": f"TEST_seq_{_rand_suffix()}@x.com", "phone": _phone()
            })
            assert r.status_code == 200, r.text
        sets = requests.get(f"{API}/admin/sets", headers=admin_headers).json()
        counts = [s["attempt_count"] for s in sets]
        qcs = [s["question_count"] for s in sets]
        # every set should still have at least 20 questions
        assert all(q >= 20 for q in qcs), qcs
        # 20 attempts across 20 sets - should be exactly 1 each
        assert max(counts) - min(counts) <= 1, counts
        assert sum(counts) == 20


# --------------- Concurrency burst ---------------
class TestConcurrencyBurst:
    def test_burst_registrations(self, admin_headers):
        requests.post(f"{API}/admin/reset-attempts", headers=admin_headers)

        N = 35

        async def _one(session, i):
            payload = {
                "name": f"Burst User {chr(65 + (i % 26))}",
                "email": f"TEST_burst_{i}_{_rand_suffix()}@example.com",
                "phone": _phone(),
            }
            async with session.post(f"{API}/register", json=payload) as r:
                return r.status, await r.text()

        async def _run():
            connector = aiohttp.TCPConnector(limit=50)
            async with aiohttp.ClientSession(connector=connector) as s:
                return await asyncio.gather(*[_one(s, i) for i in range(N)])

        results = asyncio.get_event_loop().run_until_complete(_run()) if False else asyncio.run(_run())
        statuses = [s for s, _ in results]
        assert all(s == 200 for s in statuses), f"non-200 in burst: {[r for r in results if r[0] != 200][:3]}"
        # give DB a beat
        time.sleep(0.5)
        sets = requests.get(f"{API}/admin/sets", headers=admin_headers).json()
        counts = [s["attempt_count"] for s in sets]
        assert sum(counts) == N, counts
        # 35 across 20 sets: min 1, max 2 -> spread <= 1
        assert max(counts) - min(counts) <= 1, f"uneven spread: {counts}"

        parts = requests.get(f"{API}/admin/participants", headers=admin_headers).json()
        assert len(parts) == N
        # attempts unique per participant: every participant row here has a set assigned
        assert all(p["set"] is not None for p in parts)


# --------------- Quiz flow + integrity ---------------
def _register():
    r = requests.post(f"{API}/register", json={
        "name": "Quiz User", "email": f"TEST_q_{_rand_suffix()}@example.com", "phone": _phone()
    })
    assert r.status_code == 200
    return r.json()["attempt_token"]


class TestQuizFlow:
    def test_question_response_omits_correct_option(self):
        token = _register()
        r = requests.get(f"{API}/attempt/{token}/question")
        assert r.status_code == 200
        j = r.json()
        assert j["completed"] is False
        q = j["question"]
        assert "correct_option" not in q
        assert "correct" not in str(q).lower() or "correct_option" not in q
        assert set(q["options"].keys()) == {"A", "B", "C", "D"}
        assert j["total_questions"] == 20
        assert j["index"] == 1

    def test_cross_set_question_rejected(self, admin_headers):
        token = _register()
        state = requests.get(f"{API}/attempt/{token}/state").json()
        # Find a question NOT in this attempt's set: fetch all sets, pick one whose questions differ
        sets = requests.get(f"{API}/admin/sets", headers=admin_headers).json()
        # get attempt's current question id
        cur = requests.get(f"{API}/attempt/{token}/question").json()["question"]["id"]
        # pull questions from set 1 & set 2, find an id not equal to cur's set
        # simpler: fetch questions of set 1, if cur is not in it, pick one from set 1
        qs1 = requests.get(f"{API}/admin/sets/1/questions", headers=admin_headers).json()
        qs2 = requests.get(f"{API}/admin/sets/2/questions", headers=admin_headers).json()
        ids1 = {q["id"] for q in qs1}
        foreign_id = qs2[0]["id"] if cur in ids1 else qs1[0]["id"]
        r = requests.post(f"{API}/attempt/{token}/answer", json={"question_id": foreign_id, "selected_option": "A"})
        assert r.status_code == 400

    def test_full_run_scoring_and_completion(self, admin_headers):
        my_email = f"TEST_full_{_rand_suffix()}@example.com"
        r = requests.post(f"{API}/register", json={
            "name": "Full Runner", "email": my_email, "phone": _phone()
        })
        assert r.status_code == 200
        token = r.json()["attempt_token"]
        # Determine set questions via admin (with correct answers) to answer correctly for 5 questions
        state = requests.get(f"{API}/attempt/{token}/question").json()
        # find set id via participant listing
        parts = requests.get(f"{API}/admin/participants", headers=admin_headers).json()
        # find latest with matching (we identify by set name from a state-less approach: just iterate)
        # Simpler: iterate over each question shown, look up its correct_option via admin question list of any set.
        # We'll first fetch all questions from all sets & build id->correct map.
        id_to_correct = {}
        set_of_qid = {}
        for s in requests.get(f"{API}/admin/sets", headers=admin_headers).json():
            qs = requests.get(f"{API}/admin/sets/{s['id']}/questions", headers=admin_headers).json()
            for q in qs:
                id_to_correct[q["id"]] = q["correct_option"]
                set_of_qid[q["id"]] = s["id"]

        correct_answers = 0
        wrong_answers = 0
        started = time.time()
        for i in range(20):
            resp = requests.get(f"{API}/attempt/{token}/question").json()
            if resp.get("completed"):
                break
            q = resp["question"]
            correct = id_to_correct[q["id"]]
            # alternate: first 12 correct, rest wrong for a known score
            if i < 12:
                sel = correct
                correct_answers += 1
            else:
                sel = "A" if correct != "A" else "B"
                wrong_answers += 1
            r = requests.post(f"{API}/attempt/{token}/answer", json={"question_id": q["id"], "selected_option": sel})
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["answered"] == i + 1
            if i == 19:
                assert data["completed"] is True
        elapsed = time.time() - started
        # After completion, question endpoint returns completed=True with no score
        final = requests.get(f"{API}/attempt/{token}/question").json()
        assert final == {"completed": True}
        # verify score via admin participants
        parts = requests.get(f"{API}/admin/participants", headers=admin_headers).json()
        my_row = next(p for p in parts if p["email"] == my_email.lower())
        assert my_row["score"] == correct_answers
        assert 0 <= my_row["time_taken_seconds"] <= int(elapsed) + 5

    def test_duplicate_answer_rejected(self):
        token = _register()
        q = requests.get(f"{API}/attempt/{token}/question").json()["question"]
        r1 = requests.post(f"{API}/attempt/{token}/answer", json={"question_id": q["id"], "selected_option": "A"})
        assert r1.status_code == 200
        r2 = requests.post(f"{API}/attempt/{token}/answer", json={"question_id": q["id"], "selected_option": "B"})
        assert r2.status_code == 409

    def test_resume_state(self):
        token = _register()
        q1 = requests.get(f"{API}/attempt/{token}/question").json()
        requests.post(f"{API}/attempt/{token}/answer", json={"question_id": q1["question"]["id"], "selected_option": "A"})
        state = requests.get(f"{API}/attempt/{token}/state").json()
        assert state["answered"] == 1
        assert state["completed"] is False
        q2 = requests.get(f"{API}/attempt/{token}/question").json()
        assert q2["index"] == 2
        assert q2["question"]["id"] != q1["question"]["id"]


# --------------- Admin stats/participants/leaderboard/export ---------------
class TestAdminData:
    def test_stats(self, admin_headers):
        r = requests.get(f"{API}/admin/stats", headers=admin_headers)
        assert r.status_code == 200
        d = r.json()
        for k in ("total_participants", "completed", "avg_score", "avg_time_seconds", "completion_rate"):
            assert k in d

    def test_participants_search_and_sort(self, admin_headers):
        r = requests.get(f"{API}/admin/participants?search=TEST_&sort=name&direction=asc", headers=admin_headers)
        assert r.status_code == 200
        rows = r.json()
        names = [x["name"] for x in rows]
        assert names == sorted(names)

    def test_leaderboard_ordering(self, admin_headers):
        r = requests.get(f"{API}/admin/leaderboard", headers=admin_headers)
        assert r.status_code == 200
        rows = r.json()
        if len(rows) >= 2:
            for i in range(len(rows) - 1):
                a, b = rows[i], rows[i + 1]
                assert (a["score"], -a["time_taken_seconds"]) >= (b["score"], -b["time_taken_seconds"])

    def test_export_csv(self, admin_headers):
        r = requests.get(f"{API}/admin/export.csv", headers=admin_headers)
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")
        reader = csv.reader(io.StringIO(r.text))
        header = next(reader)
        for h in ["name", "email", "phone", "school", "set", "score", "time_taken_seconds", "completed_at", "created_at"]:
            assert h in header


# --------------- Question management ---------------
class TestQuestionManagement:
    def test_crud_and_import(self, admin_headers):
        # Choose a set that we can safely mutate — set 20 (unused likely) then restore via replace import.
        set_id = 20
        # Create
        create = requests.post(f"{API}/admin/sets/{set_id}/questions", headers=admin_headers, json={
            "question_text": "TEST_Q new question?",
            "options": {"A": "one", "B": "two", "C": "three", "D": "four"},
            "correct_option": "B",
            "category": "TEST",
        })
        assert create.status_code == 200, create.text
        qid = create.json()["id"]
        # Update
        upd = requests.put(f"{API}/admin/questions/{qid}", headers=admin_headers, json={
            "question_text": "TEST_Q updated?",
            "options": {"A": "one", "B": "two", "C": "three", "D": "four"},
            "correct_option": "C",
            "category": "TEST",
        })
        assert upd.status_code == 200
        # Delete
        d = requests.delete(f"{API}/admin/questions/{qid}", headers=admin_headers)
        assert d.status_code == 200

    def test_bulk_import_parser(self, admin_headers):
        set_id = 20
        raw = """1. What is 2+2?
A) 3
B) 4
C) 5
D) 6
Answer: B

Broken block without answer
A) x
B) y
C) z
D) w

Category: Math
2. What is 3*3?
A) 6
B) 7
C) 9
D) 12
Answer: C
"""
        r = requests.post(f"{API}/admin/sets/{set_id}/import", headers=admin_headers,
                          json={"raw_text": raw, "replace": False})
        assert r.status_code == 200
        j = r.json()
        assert j["imported"] == 2
        assert any("Block 2" in e for e in j["errors"])
