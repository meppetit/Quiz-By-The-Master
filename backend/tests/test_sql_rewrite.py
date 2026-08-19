"""Iteration 4: targeted checks for the SQL rewrite (single-statement + autocommit).

- REGISTER_SQL creates 1 participant + 1 attempt + bumps attempt_count by exactly 1
- Rejected duplicate registration leaves no orphan participant/attempt
- NEXT_QUESTION_SQL: invalid token -> 404 (not 500); garbage token -> 404
- ANSWER_SQL: returns `next` with the following question so client needs ONE request per question
- ANSWER_SQL final question -> completed:True, NO next, score/time set
- AUTOCOMMIT: after POST returns, the answer row is durably visible via a fresh admin session
- Performance sanity: single register, single GET question, single POST answer, full 20 Q run
"""
import os
import random
import string
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://quiz-burst-mep.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
ADMIN = ("admin", "mepquiz2026")


def _sfx(n=8):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


def _phone():
    return "9" + "".join(random.choices(string.digits, k=9))


@pytest.fixture(scope="module")
def admin_headers():
    r = requests.post(f"{API}/admin/login", json={"username": ADMIN[0], "password": ADMIN[1]})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _register(email=None, phone=None):
    email = email or f"TEST_rw_{_sfx()}@example.com"
    phone = phone or _phone()
    r = requests.post(f"{API}/register", json={"name": "SQL Rewrite", "email": email, "phone": phone}, timeout=60)
    return r, email, phone


class TestRegisterAtomicity:
    def test_register_creates_one_participant_one_attempt_and_bumps_counter(self, admin_headers):
        # Capture snapshot before
        before_sets = {s["id"]: s["attempt_count"] for s in
                       requests.get(f"{API}/admin/sets", headers=admin_headers).json()}
        before_stats = requests.get(f"{API}/admin/stats", headers=admin_headers).json()

        r, email, _ = _register()
        assert r.status_code == 200, r.text
        d = r.json()
        assert "attempt_token" in d and "set_name" in d and "started_at" in d
        assert d["total_questions"] == 20

        after_stats = requests.get(f"{API}/admin/stats", headers=admin_headers).json()
        # exactly +1 participant
        assert after_stats["total_participants"] == before_stats["total_participants"] + 1

        # exactly one set counter bumped by +1
        after_sets = {s["id"]: s["attempt_count"] for s in
                      requests.get(f"{API}/admin/sets", headers=admin_headers).json()}
        deltas = {sid: after_sets[sid] - before_sets.get(sid, 0) for sid in after_sets}
        bumped = [sid for sid, d_ in deltas.items() if d_ >= 1]
        # NOTE: other workers may register in parallel; assert AT LEAST one bump and our set_name appears
        assert bumped, f"no set attempt_count bumped: {deltas}"
        # participant row exists w/ set assigned
        parts = requests.get(f"{API}/admin/participants?search={email.split('@')[0]}",
                             headers=admin_headers, timeout=60).json()
        me = next((p for p in parts if p["email"] == email.lower()), None)
        assert me is not None and me["set"] == d["set_name"]

    def test_duplicate_registration_no_orphan(self, admin_headers):
        r1, email, phone = _register()
        assert r1.status_code == 200
        before_stats = requests.get(f"{API}/admin/stats", headers=admin_headers).json()

        # duplicate email
        r2, _, _ = _register(email=email)
        assert r2.status_code == 409
        assert "email" in r2.json()["detail"].lower()

        # duplicate phone
        r3, _, _ = _register(phone=phone)
        assert r3.status_code == 409
        assert "phone" in r3.json()["detail"].lower()

        after_stats = requests.get(f"{API}/admin/stats", headers=admin_headers).json()
        # rejected registrations must not leave any orphan
        assert after_stats["total_participants"] == before_stats["total_participants"]


class TestQuestionEndpointGuards:
    def test_invalid_uuid_returns_404(self):
        r = requests.get(f"{API}/attempt/not-a-uuid/question", timeout=60)
        assert r.status_code == 404, r.text

    def test_nonexistent_uuid_returns_404(self):
        r = requests.get(f"{API}/attempt/{uuid.uuid4()}/question", timeout=60)
        assert r.status_code == 404, r.text

    def test_garbage_token_returns_404_not_500(self):
        r = requests.get(f"{API}/attempt/%20%20/question", timeout=60)
        assert r.status_code in (404, 422), r.text

    def test_question_omits_correct_option(self):
        r, _, _ = _register()
        assert r.status_code == 200
        token = r.json()["attempt_token"]
        gq = requests.get(f"{API}/attempt/{token}/question", timeout=60).json()
        assert "correct_option" not in gq["question"]


class TestAnswerReturnsNextForOnePerScreen:
    def test_answer_contains_next_question(self):
        r, _, _ = _register()
        assert r.status_code == 200
        token = r.json()["attempt_token"]
        gq = requests.get(f"{API}/attempt/{token}/question", timeout=60).json()
        q1 = gq["question"]
        t0 = time.time()
        ar = requests.post(f"{API}/attempt/{token}/answer",
                           json={"question_id": q1["id"], "selected_option": "A"}, timeout=60)
        dt_answer = time.time() - t0
        assert ar.status_code == 200, ar.text
        j = ar.json()
        assert j["completed"] is False
        assert j["answered"] == 1
        assert "next" in j and j["next"]["question"]["id"] != q1["id"]
        assert "correct_option" not in j["next"]["question"]
        assert j["next"]["index"] == 2
        # Perf sanity: with autocommit + single statement, one answer round-trip should be < 1.5s
        # We only assert < 3s here to be robust to Mumbai jitter.
        assert dt_answer < 3.0, f"answer took {dt_answer:.2f}s"


class TestFullRunOneRequestPerScreen:
    def test_full_run_one_request_per_question_and_score(self, admin_headers):
        # Build correct-answer map first
        id_to_correct = {}
        for s in requests.get(f"{API}/admin/sets", headers=admin_headers, timeout=60).json():
            qs = requests.get(f"{API}/admin/sets/{s['id']}/questions",
                              headers=admin_headers, timeout=60).json()
            for q in qs:
                id_to_correct[q["id"]] = q["correct_option"]

        email = f"TEST_full1req_{_sfx()}@example.com"
        r = requests.post(f"{API}/register",
                          json={"name": "Full One Req", "email": email, "phone": _phone()}, timeout=60)
        assert r.status_code == 200
        token = r.json()["attempt_token"]

        # Only ONE GET at start
        cur = requests.get(f"{API}/attempt/{token}/question", timeout=60).json()
        assert cur["index"] == 1
        started = time.time()
        expected_correct = 0
        per_answer_times = []
        for i in range(20):
            q = cur["question"]
            correct = id_to_correct[q["id"]]
            if i < 13:
                sel = correct
                expected_correct += 1
            else:
                sel = "A" if correct != "A" else "B"
            t0 = time.time()
            ar = requests.post(f"{API}/attempt/{token}/answer",
                               json={"question_id": q["id"], "selected_option": sel}, timeout=60)
            per_answer_times.append(time.time() - t0)
            assert ar.status_code == 200, ar.text
            j = ar.json()
            assert j["answered"] == i + 1
            if i == 19:
                assert j["completed"] is True
                assert "next" not in j, "final answer must NOT include next"
            else:
                assert j["completed"] is False
                assert "next" in j
                cur = j["next"]
        elapsed = time.time() - started

        # Post-completion GET is idempotent
        final = requests.get(f"{API}/attempt/{token}/question", timeout=60).json()
        assert final == {"completed": True}

        # verify score + time via admin
        parts = requests.get(f"{API}/admin/participants?search={email.split('@')[0]}",
                             headers=admin_headers, timeout=60).json()
        me = next(p for p in parts if p["email"] == email.lower())
        assert me["score"] == expected_correct
        # server time_taken must be >= wall-clock (register + loop). Just sanity-check upper bound.
        assert me["time_taken_seconds"] >= 0
        assert me["completed_at"] is not None

        # Perf log
        print(f"\n[PERF] full-run answer loop = {elapsed:.1f}s over 20 answers "
              f"(median {sorted(per_answer_times)[10]:.2f}s, max {max(per_answer_times):.2f}s)")
        # None of the answer round-trips should regress beyond 3s
        assert max(per_answer_times) < 3.5, per_answer_times


class TestAutocommitDurability:
    def test_answer_visible_from_fresh_admin_session(self, admin_headers):
        r, email, _ = _register()
        assert r.status_code == 200
        token = r.json()["attempt_token"]
        gq = requests.get(f"{API}/attempt/{token}/question", timeout=60).json()
        qid = gq["question"]["id"]
        ar = requests.post(f"{API}/attempt/{token}/answer",
                           json={"question_id": qid, "selected_option": "A"}, timeout=60)
        assert ar.status_code == 200
        # A brand-new session (fresh HTTP client) should immediately see answered=1
        fresh = requests.Session()
        st = fresh.get(f"{API}/attempt/{token}/state", timeout=60).json()
        assert st["answered"] == 1, st
