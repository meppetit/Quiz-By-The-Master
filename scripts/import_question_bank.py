"""One-off importer: MEP question bank .docx -> question sets via the admin API."""
import os
import re
import sys
import zipfile
from io import BytesIO
from urllib.request import urlopen

import requests

DOCX_URL = sys.argv[1]
API = os.environ["API"]
ADMIN = {"username": os.environ.get("ADMIN_USERNAME", "admin"),
         "password": os.environ.get("ADMIN_PASSWORD", "mepquiz2026")}


def docx_lines(url):
    raw = urlopen(url).read()
    xml = zipfile.ZipFile(BytesIO(raw)).read("word/document.xml").decode("utf8")
    xml = re.sub(r"<w:br[^>]*>", "\n", xml)
    xml = xml.replace("</w:p>", "\n</w:p>")
    text = re.sub(r"<[^>]+>", "", xml)
    return [l.strip() for l in text.split("\n") if l.strip()]


def split_sets(lines):
    sets, cur, name = {}, [], None
    for l in lines:
        m = re.match(r"^set\s*[-:]?\s*(\d{1,2})\b", l, re.I)
        if m and len(l) < 30:
            if name:
                sets[name] = cur
            name, cur = int(m.group(1)), []
            continue
        if name:
            cur.append(l)
    if name:
        sets[name] = cur
    return sets


def to_blocks(lines):
    """Group flat lines into blank-line separated blocks the backend parser understands."""
    blocks, cur = [], []
    for l in lines:
        if re.match(r"^(?:question|qn|ques)\s*[:\-.]", l, re.I) or re.match(r"^\d+[\.\)]\s", l):
            if cur:
                blocks.append(cur)
            cur = [l]
        elif cur:
            cur.append(l)
    if cur:
        blocks.append(cur)
    return "\n\n".join("\n".join(b) for b in blocks)


def main():
    token = requests.post(f"{API}/api/admin/login", json=ADMIN, timeout=30).json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    sets_meta = requests.get(f"{API}/api/admin/sets", headers=h, timeout=30).json()
    by_number = {int(re.search(r"(\d+)", s["name"]).group(1)): s["id"] for s in sets_meta}

    parsed_sets = split_sets(docx_lines(DOCX_URL))
    print("sets found in doc:", sorted(parsed_sets))
    total_ok = 0
    for num in sorted(parsed_sets):
        set_id = by_number.get(num)
        if not set_id:
            print(f"!! no matching set for SET {num}")
            continue
        payload = {"raw_text": to_blocks(parsed_sets[num]), "replace": True}
        r = requests.post(f"{API}/api/admin/sets/{set_id}/import", json=payload, headers=h, timeout=120).json()
        total_ok += r.get("imported", 0)
        print(f"SET {num:02d} -> imported {r.get('imported')} errors {r.get('errors')[:2] if r.get('errors') else []}")
    print("TOTAL imported:", total_ok)


main()
