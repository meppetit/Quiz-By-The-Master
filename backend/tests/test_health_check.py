"""Set Health Check + regression tests for iteration 2.

Covers:
- GET /api/admin/health-check auth (401 without bearer)
- Health check base shape & event_ready with seeded data
- Flagging: delete a question -> CHECK w/ 'Only 19 of 20' -> re-import -> READY
- Duplicate question text flagged
- PUT /api/admin/questions with empty option value -> 422 validation
"""
import os
import random
import string
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"
ADMIN_USER = "admin"
ADMIN_PASS = "mepquiz2026"


def _rand(n=6):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


@pytest.fixture(scope="module")
def admin_headers():
    r = requests.post(f"{API}/admin/login", json={"username": ADMIN_USER, "password": ADMIN_PASS})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


class TestHealthCheckAuth:
    def test_requires_bearer(self):
        r = requests.get(f"{API}/admin/health-check")
        assert r.status_code == 401

    def test_bad_bearer(self):
        r = requests.get(f"{API}/admin/health-check", headers={"Authorization": "Bearer garbage.token.value"})
        assert r.status_code == 401


class TestHealthCheckBase:
    def test_shape_and_seeded_all_ready(self, admin_headers):
        r = requests.get(f"{API}/admin/health-check", headers=admin_headers)
        assert r.status_code == 200
        d = r.json()
        for k in ("total_sets", "ready_sets", "blocked_sets", "event_ready", "sets"):
            assert k in d
        assert d["total_sets"] == 20
        assert isinstance(d["sets"], list) and len(d["sets"]) == 20
        for s in d["sets"]:
            for k in ("set_id", "name", "question_count", "attempt_count", "ready", "issues"):
                assert k in s
        # Freshly seeded => every set exactly 20 and READY. Regression suite
        # mutates set 20 (bulk-import parser test + CRUD test), so *exclude*
        # set 20 from the strict all-ready assertion; verify every OTHER set
        # is ready with exactly 20 questions.
        others = [s for s in d["sets"] if s["set_id"] != 20]
        blocked = [s for s in others if not s["ready"]]
        assert not blocked, blocked
        for s in others:
            assert s["question_count"] == 20, s


class TestHealthCheckFlagging:
    def test_delete_question_flags_check_then_re_import_ready(self, admin_headers):
        # Use set 10 to avoid clashing with set 20 used by other tests
        set_id = 10
        qs = requests.get(f"{API}/admin/sets/{set_id}/questions", headers=admin_headers).json()
        assert len(qs) >= 20
        victim = qs[-1]
        # Delete last question in set
        d = requests.delete(f"{API}/admin/questions/{victim['id']}", headers=admin_headers)
        assert d.status_code == 200

        report = requests.get(f"{API}/admin/health-check", headers=admin_headers).json()
        target = next(s for s in report["sets"] if s["set_id"] == set_id)
        assert target["ready"] is False
        assert any("Only 19 of 20 questions" in i for i in target["issues"]), target["issues"]
        assert report["event_ready"] is False
        assert report["blocked_sets"] >= 1

        # Add a question back to restore READY (use unique text)
        create = requests.post(
            f"{API}/admin/sets/{set_id}/questions",
            headers=admin_headers,
            json={
                "question_text": f"TEST_restore_{_rand()}?",
                "options": {"A": "a", "B": "b", "C": "c", "D": "d"},
                "correct_option": "A",
                "category": "TEST",
            },
        )
        assert create.status_code == 200, create.text

        report2 = requests.get(f"{API}/admin/health-check", headers=admin_headers).json()
        target2 = next(s for s in report2["sets"] if s["set_id"] == set_id)
        assert target2["ready"] is True, target2["issues"]

    def test_duplicate_question_text_flagged(self, admin_headers):
        set_id = 11
        qs = requests.get(f"{API}/admin/sets/{set_id}/questions", headers=admin_headers).json()
        assert qs
        existing_text = qs[0]["question_text"]
        # Create a duplicate of the first question's text
        payload = {
            "question_text": existing_text,
            "options": {"A": "a", "B": "b", "C": "c", "D": "d"},
            "correct_option": "A",
            "category": "TEST",
        }
        c = requests.post(f"{API}/admin/sets/{set_id}/questions", headers=admin_headers, json=payload)
        assert c.status_code == 200
        dupe_id = c.json()["id"]
        try:
            report = requests.get(f"{API}/admin/health-check", headers=admin_headers).json()
            target = next(s for s in report["sets"] if s["set_id"] == set_id)
            assert target["ready"] is False
            assert any("duplicate question text" in i.lower() for i in target["issues"]), target["issues"]
        finally:
            requests.delete(f"{API}/admin/questions/{dupe_id}", headers=admin_headers)


class TestQuestionValidation:
    def test_put_with_blank_option_rejected(self, admin_headers):
        # Pick an existing question in set 12
        qs = requests.get(f"{API}/admin/sets/12/questions", headers=admin_headers).json()
        assert qs
        qid = qs[0]["id"]
        payload = {
            "question_text": "TEST validation?",
            "options": {"A": "one", "B": "  ", "C": "three", "D": "four"},  # blank B
            "correct_option": "A",
            "category": "TEST",
        }
        r = requests.put(f"{API}/admin/questions/{qid}", headers=admin_headers, json=payload)
        assert r.status_code == 422, r.text
        # message mentions options / non-empty
        assert "options" in r.text.lower()

    def test_put_with_missing_option_key_rejected(self, admin_headers):
        qs = requests.get(f"{API}/admin/sets/12/questions", headers=admin_headers).json()
        qid = qs[0]["id"]
        r = requests.put(
            f"{API}/admin/questions/{qid}",
            headers=admin_headers,
            json={
                "question_text": "TEST validation2?",
                "options": {"A": "one", "B": "two", "C": "three"},
                "correct_option": "A",
            },
        )
        assert r.status_code == 422
