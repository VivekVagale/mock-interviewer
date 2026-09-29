"""The question bank and how an interview picks from it."""

import json
import random
from functools import lru_cache
from pathlib import Path

BANK = Path(__file__).resolve().parent.parent / "data" / "questions.json"


@lru_cache(maxsize=1)
def load() -> list[dict]:
    return json.loads(BANK.read_text(encoding="utf-8"))


def by_id(qid: str) -> dict:
    return next(q for q in load() if q["id"] == qid)


def topics() -> list[str]:
    return sorted({q["topic"] for q in load()})


def pick(chosen_topics: list[str], n: int, seed: int | None = None) -> list[dict]:
    """n questions spread across the chosen topics, HR (if chosen) asked first."""
    r = random.Random(seed)
    pools = {t: [q for q in load() if q["topic"] == t] for t in chosen_topics}
    for pool in pools.values():
        r.shuffle(pool)
    picked = []
    while len(picked) < n and any(pools.values()):
        for t in chosen_topics:
            if pools[t] and len(picked) < n:
                picked.append(pools[t].pop())
    return sorted(picked, key=lambda q: q["topic"] != "HR")
