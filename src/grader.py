"""Score a candidate's answer against a question's rubric key points.

Why a rubric: asking an LLM "rate this answer 1-10" gives vague, drifting
scores. Asking it to check each key point (covered / partly / missed) is a
narrower job it does more consistently, and the final score is computed in
code from those checks, so the arithmetic is never left to the model.
"""

from .llm import MODEL, chat_json

SCHEMA = {
    "type": "object",
    "properties": {
        "points": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "point": {"type": "string"},
                    "verdict": {"type": "string", "enum": ["covered", "partial", "missed"]},
                    "evidence": {"type": "string"},
                },
                "required": ["point", "verdict", "evidence"],
            },
        },
        "wrong_statements": {"type": "array", "items": {"type": "string"}},
        "communication": {"type": "integer", "minimum": 1, "maximum": 5},
        "feedback": {"type": "string"},
        "model_answer": {"type": "string"},
    },
    "required": ["points", "wrong_statements", "communication", "feedback", "model_answer"],
}

SYSTEM = """You are a strict but fair campus-placement interviewer grading a spoken answer.
For EACH rubric key point decide:
- covered: the answer clearly states it (different wording is fine)
- partial: the answer hints at it but is vague or incomplete
- missed: not mentioned
Quote the words from the answer that support each verdict in "evidence" (empty if missed).
List any factually wrong statements in "wrong_statements".
Rate "communication" 1-5 for clarity and structure only, not correctness.
"feedback": 2-3 sentences, addressed to the candidate as "you", saying what to add or fix.
"model_answer": a crisp 60-100 word answer a strong candidate would give.
Grade only what is written. Do not reward length or confident tone by itself."""

WEIGHT = {"covered": 1.0, "partial": 0.5, "missed": 0.0}


def grade(question: dict, answer: str, model: str = MODEL, temperature: float = 0.0) -> dict:
    rubric = "\n".join(f"{i + 1}. {p}" for i, p in enumerate(question["key_points"]))
    user = f"Question: {question['question']}\n\nRubric key points:\n{rubric}\n\nCandidate answer:\n{answer.strip() or '(no answer)'}"
    out = chat_json([{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
                    schema=SCHEMA, model=model, temperature=temperature)
    out["score"] = score(out, len(question["key_points"]))
    return out


def score(graded: dict, n_points: int) -> float:
    """0-10 score: key-point coverage, minus 1 per wrong statement (max -3)."""
    verdicts = [p.get("verdict", "missed") for p in graded.get("points", [])][:n_points]
    coverage = sum(WEIGHT.get(v, 0) for v in verdicts) / n_points
    penalty = min(len(graded.get("wrong_statements", [])), 3)
    return round(max(0.0, 10 * coverage - penalty), 1)
