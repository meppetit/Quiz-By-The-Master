import collections
import os

import requests

API = os.environ["API"]
tok = requests.post(f"{API}/api/admin/login",
                    json={"username": "admin", "password": "mepquiz2026"}, timeout=30).json()["access_token"]
h = {"Authorization": f"Bearer {tok}"}
tot = collections.Counter()
for s in requests.get(f"{API}/api/admin/sets", headers=h, timeout=30).json():
    q = requests.get(f"{API}/api/admin/sets/{s['id']}/questions", headers=h, timeout=60).json()
    c = collections.Counter(x["correct_option"] for x in q)
    tot += c
    print(s["name"], len(q), dict(sorted(c.items())))
print("TOTAL", dict(sorted(tot.items())), "questions", sum(tot.values()))
