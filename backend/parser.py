import re

LETTERS = ["A", "B", "C", "D"]


def parse_questions(raw: str):
    """Flexible parser for pasted question blocks.

    Accepted shape per block (blank-line separated):
        1. Question text?            (leading number optional)
        A) option one                (A. / A) / A- accepted)
        B) option two
        C) option three
        D) option four
        Answer: B                    (Ans / Correct / Answer accepted)
    Returns (parsed, errors).
    """
    parsed, errors = [], []
    blocks = [b for b in re.split(r"\n\s*\n", (raw or "").replace("\r\n", "\n")) if b.strip()]
    for bi, block in enumerate(blocks, start=1):
        lines = [l.strip() for l in block.split("\n") if l.strip()]
        q_lines, options, answer, category = [], {}, None, None
        for line in lines:
            m_opt = re.match(r"^\(?([A-Da-d])[\)\.\:\-]\s*(.+)$", line)
            m_ans = re.match(r"^(?:answer|ans|correct(?:\s*answer)?)\s*[:\-\)]?\s*\(?([A-Da-d])\)?\s*$", line, re.I)
            m_cat = re.match(r"^(?:category|topic)\s*[:\-]\s*(.+)$", line, re.I)
            if m_ans:
                answer = m_ans.group(1).upper()
            elif m_cat:
                category = m_cat.group(1).strip()
            elif m_opt and not options.get(m_opt.group(1).upper()):
                options[m_opt.group(1).upper()] = m_opt.group(2).strip()
            elif not options:
                q_lines.append(re.sub(r"^(?:Q\s*)?\d+[\)\.\:]\s*", "", line, flags=re.I))
            else:
                errors.append(f"Block {bi}: unrecognised line -> {line[:60]!r}")
        question_text = " ".join(q_lines).strip()
        missing = [l for l in LETTERS if not options.get(l)]
        if not question_text:
            errors.append(f"Block {bi}: missing question text")
            continue
        if missing:
            errors.append(f"Block {bi}: missing option(s) {', '.join(missing)}")
            continue
        if not answer:
            errors.append(f"Block {bi}: missing 'Answer: X' line")
            continue
        parsed.append({
            "question_text": question_text,
            "options": {l: options[l] for l in LETTERS},
            "correct_option": answer,
            "category": category,
        })
    return parsed, errors
