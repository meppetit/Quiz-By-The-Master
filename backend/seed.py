from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Question, QuestionSet

NUM_SETS = 20
PER_SET = 20

TOPICS = [
    ("Data Structures", "Which data structure gives O(1) average-time lookup by key?",
     ["Hash map", "Linked list", "Binary search tree", "Array (unsorted)"], "A"),
    ("Algorithms", "What is the worst-case time complexity of quicksort?",
     ["O(n log n)", "O(n^2)", "O(n)", "O(log n)"], "B"),
    ("Networking", "Which protocol guarantees ordered, reliable delivery?",
     ["UDP", "ICMP", "TCP", "ARP"], "C"),
    ("Databases", "Which SQL clause filters rows after aggregation?",
     ["WHERE", "GROUP BY", "ORDER BY", "HAVING"], "D"),
    ("Operating Systems", "What does a mutex primarily prevent?",
     ["Race conditions", "Memory leaks", "Cache misses", "Page faults"], "A"),
    ("Mathematics", "What is the derivative of sin(x)?",
     ["-sin(x)", "cos(x)", "tan(x)", "-cos(x)"], "B"),
    ("Physics", "Which quantity is measured in newton-seconds?",
     ["Energy", "Power", "Impulse", "Pressure"], "C"),
    ("Electronics", "Ohm's law relates voltage, current and which quantity?",
     ["Capacitance", "Inductance", "Frequency", "Resistance"], "D"),
    ("Web", "Which HTTP status code means 'Conflict'?",
     ["409", "301", "503", "418"], "A"),
    ("Security", "What does hashing a password protect against?",
     ["Slow logins", "Plaintext leaks on breach", "CSRF", "DNS spoofing"], "B"),
    ("Data Structures", "Which structure follows first-in-first-out order?",
     ["Stack", "Heap", "Queue", "Trie"], "C"),
    ("Algorithms", "Binary search requires the input to be what?",
     ["Hashed", "Unique", "Reversed", "Sorted"], "D"),
    ("Cloud", "What does horizontal scaling mean?",
     ["Adding more machines", "Adding more RAM", "Reducing latency", "Caching results"], "A"),
    ("Concurrency", "What is a deadlock?",
     ["A slow query", "Two tasks each waiting on the other", "A dropped packet", "A stale cache"], "B"),
    ("Mathematics", "What is the value of log base 2 of 1024?",
     ["8", "9", "10", "11"], "C"),
    ("Databases", "Which index type suits range queries best in Postgres?",
     ["Hash", "GIN", "BRIN", "B-tree"], "D"),
    ("Web", "Which header enables cross-origin requests?",
     ["Access-Control-Allow-Origin", "Content-Type", "Cache-Control", "ETag"], "A"),
    ("Physics", "Light travels fastest in which medium?",
     ["Water", "Vacuum", "Glass", "Diamond"], "B"),
    ("Electronics", "A diode primarily allows current to flow in how many directions?",
     ["Two", "None", "One", "Three"], "C"),
    ("General", "In computing, what does 'idempotent' mean?",
     ["Runs fast", "Runs once only", "Requires auth", "Repeating gives the same result"], "D"),
]


async def seed_sets(session: AsyncSession) -> None:
    existing = await session.scalar(select(func.count(QuestionSet.id)))
    if not existing:
        for i in range(1, NUM_SETS + 1):
            session.add(QuestionSet(name=f"Set {i:02d}", attempt_count=0))
        await session.commit()

    res = await session.execute(select(QuestionSet).order_by(QuestionSet.id))
    for qs in res.scalars().all():
        count = await session.scalar(select(func.count(Question.id)).where(Question.set_id == qs.id))
        if count:
            continue
        for idx in range(PER_SET):
            cat, text_, opts, correct = TOPICS[(idx + qs.id) % len(TOPICS)]
            session.add(Question(
                set_id=qs.id,
                question_text=f"[{qs.name}] {text_}",
                options={"A": opts[0], "B": opts[1], "C": opts[2], "D": opts[3]},
                correct_option=correct,
                category=cat,
                order_index=idx + 1,
            ))
        await session.commit()
