"""Follow-up questions and the end-of-interview report."""

from .llm import MODEL, chat

FOLLOWUP_SYSTEM = """You are a campus-placement interviewer. The candidate just answered a question
and missed some points. Ask ONE short follow-up question (max 25 words) that nudges them toward
the most important missed point without giving the answer away. Reply with the question only."""


def follow_up(question: dict, answer: str, graded: dict, model: str = MODEL) -> str | None:
    missed = [p["point"] for p in graded["points"] if p["verdict"] != "covered"]
    if not missed or graded["score"] >= 8:
        return None
    user = f"Question: {question['question']}\nCandidate answer: {answer}\nMissed points: {'; '.join(missed)}"
    return chat([{"role": "system", "content": FOLLOWUP_SYSTEM}, {"role": "user", "content": user}],
                model=model, temperature=0.3).strip().strip('"')


def report(history: list[dict]) -> str:
    """Markdown summary of the whole interview; computed in code, no LLM needed."""
    if not history:
        return "No answers yet."
    avg = sum(h["graded"]["score"] for h in history) / len(history)
    by_topic: dict[str, list[float]] = {}
    for h in history:
        by_topic.setdefault(h["question"]["topic"], []).append(h["graded"]["score"])

    lines = [f"# Mock interview report\n", f"**Overall: {avg:.1f} / 10** over {len(history)} questions\n",
             "| Topic | Avg score |", "|---|---|"]
    lines += [f"| {t} | {sum(s) / len(s):.1f} |" for t, s in sorted(by_topic.items(), key=lambda kv: sum(kv[1]) / len(kv[1]))]
    lines.append("\n## Points to revise\n")
    for h in history:
        missed = [p["point"] for p in h["graded"]["points"] if p["verdict"] == "missed"]
        if missed:
            lines.append(f"**{h['question']['question']}**")
            lines += [f"- {m}" for m in missed]
            lines.append("")
    lines.append("## Your answers\n")
    for i, h in enumerate(history, 1):
        lines += [f"### {i}. {h['question']['question']}  ({h['graded']['score']}/10)",
                  f"> {h['answer']}", "", f"**Feedback:** {h['graded']['feedback']}", "",
                  f"**Model answer:** {h['graded']['model_answer']}", ""]
    return "\n".join(lines)
