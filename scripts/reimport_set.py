"""Re-import a single set from the question bank docx (usage: python reimport_set.py <set-number> <docx-url>)."""
import os
import sys

import requests

sys.path.insert(0, os.path.dirname(__file__))
from import_question_bank import docx_lines, split_sets, to_blocks  # noqa: E402

set_number = int(sys.argv[1])
url = sys.argv[2]
API = os.environ["API"]

tok = requests.post(f"{API}/api/admin/login",
                    json={"username": "admin", "password": "mepquiz2026"}, timeout=60).json()["access_token"]
h = {"Authorization": f"Bearer {tok}"}
sets = requests.get(f"{API}/api/admin/sets", headers=h, timeout=60).json()
set_id = next(s["id"] for s in sets if s["name"].endswith(f"{set_number:02d}"))
block = to_blocks(split_sets(docx_lines(url))[set_number])
r = requests.post(f"{API}/api/admin/sets/{set_id}/import", headers=h, timeout=180,
                  json={"raw_text": block, "replace": True}).json()
print("set", set_number, "->", r)
