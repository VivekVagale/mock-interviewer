// Same grading as src/grader.py and src/interviewer.py, running on WebLLM in the browser.
// The LLM judges each rubric key point; the score is computed here in code.

export const SCHEMA = {
  type: "object",
  properties: {
    points: {
      type: "array",
      items: {
        type: "object",
        properties: {
          point: { type: "string" },
          verdict: { type: "string", enum: ["covered", "partial", "missed"] },
          evidence: { type: "string" },
        },
        required: ["point", "verdict", "evidence"],
      },
    },
    wrong_statements: { type: "array", items: { type: "string" } },
    communication: { type: "integer", minimum: 1, maximum: 5 },
    feedback: { type: "string" },
    model_answer: { type: "string" },
  },
  required: ["points", "wrong_statements", "communication", "feedback", "model_answer"],
};

const SYSTEM = `You are a strict but fair campus-placement interviewer grading a spoken answer.
For EACH rubric key point decide:
- covered: the answer clearly states it (different wording is fine)
- partial: the answer hints at it but is vague or incomplete
- missed: not mentioned
Quote the words from the answer that support each verdict in "evidence" (empty if missed).
List any factually wrong statements in "wrong_statements".
Rate "communication" 1-5 for clarity and structure only, not correctness.
"feedback": 2-3 sentences, addressed to the candidate as "you", saying what to add or fix.
"model_answer": a crisp 60-100 word answer a strong candidate would give.
Grade only what is written. Do not reward length or confident tone by itself.`;

const FOLLOWUP = `You are a campus-placement interviewer. The candidate just answered a question
and missed some points. Ask ONE short follow-up question (max 25 words) that nudges them toward
the most important missed point without giving the answer away. Reply with the question only.`;

const WEIGHT = { covered: 1, partial: 0.5, missed: 0 };

// 0-10: key-point coverage, minus 1 per wrong statement (max -3)
export function score(graded, nPoints) {
  const verdicts = (graded.points ?? []).slice(0, nPoints).map((p) => p.verdict ?? "missed");
  const coverage = verdicts.reduce((a, v) => a + (WEIGHT[v] ?? 0), 0) / nPoints;
  const penalty = Math.min((graded.wrong_statements ?? []).length, 3);
  return Math.round(Math.max(0, 10 * coverage - penalty) * 10) / 10;
}

export async function grade(engine, question, answer) {
  const rubric = question.key_points.map((p, i) => `${i + 1}. ${p}`).join("\n");
  const user = `Question: ${question.question}\n\nRubric key points:\n${rubric}\n\nCandidate answer:\n${answer.trim() || "(no answer)"}`;
  const reply = await engine.chat.completions.create({
    messages: [{ role: "system", content: SYSTEM }, { role: "user", content: user }],
    temperature: 0, max_tokens: 1200,
    response_format: { type: "json_object", schema: JSON.stringify(SCHEMA) },
    extra_body: { enable_thinking: false },
  });
  const out = JSON.parse(reply.choices[0].message.content);
  // small models sometimes rephrase or drop rubric points: always show the rubric's own wording
  out.points = question.key_points.map((kp, i) => ({ ...(out.points?.[i] ?? { verdict: "missed", evidence: "" }), point: kp }));
  out.score = score(out, question.key_points.length);
  return out;
}

export async function followUp(engine, question, answer, graded) {
  const missed = graded.points.filter((p) => p.verdict !== "covered").map((p) => p.point);
  if (!missed.length || graded.score >= 8) return null;
  const reply = await engine.chat.completions.create({
    messages: [{ role: "system", content: FOLLOWUP },
               { role: "user", content: `Question: ${question.question}\nCandidate answer: ${answer}\nMissed points: ${missed.join("; ")}` }],
    temperature: 0.3, max_tokens: 80, extra_body: { enable_thinking: false },
  });
  return reply.choices[0].message.content.trim().replace(/^"|"$/g, "");
}

export function report(history) {
  if (!history.length) return "No answers yet.";
  const avg = history.reduce((a, h) => a + h.graded.score, 0) / history.length;
  const byTopic = {};
  for (const h of history) (byTopic[h.question.topic] ??= []).push(h.graded.score);
  const lines = ["# Mock interview report", "", `**Overall: ${avg.toFixed(1)} / 10** over ${history.length} questions`, "",
    "| Topic | Avg score |", "|---|---|",
    ...Object.entries(byTopic).map(([t, s]) => [t, s.reduce((a, b) => a + b, 0) / s.length]).sort((a, b) => a[1] - b[1])
      .map(([t, s]) => `| ${t} | ${s.toFixed(1)} |`), "", "## Points to revise", ""];
  for (const h of history) {
    const missed = h.graded.points.filter((p) => p.verdict === "missed").map((p) => p.point);
    if (missed.length) lines.push(`**${h.question.question}**`, ...missed.map((m) => `- ${m}`), "");
  }
  lines.push("## Your answers", "");
  history.forEach((h, i) => lines.push(`### ${i + 1}. ${h.question.question}  (${h.graded.score}/10)`, `> ${h.answer}`, "",
    `**Feedback:** ${h.graded.feedback}`, "", `**Model answer:** ${h.graded.model_answer}`, ""));
  return lines.join("\n");
}

// n questions spread across chosen topics, HR first (same as src/questions.py)
export function pick(bank, topics, n) {
  const pools = Object.fromEntries(topics.map((t) => [t, bank.filter((q) => q.topic === t).sort(() => Math.random() - 0.5)]));
  const picked = [];
  while (picked.length < n && Object.values(pools).some((p) => p.length)) {
    for (const t of topics) if (pools[t].length && picked.length < n) picked.push(pools[t].pop());
  }
  return picked.sort((a, b) => (a.topic === "HR" ? -1 : 0) - (b.topic === "HR" ? -1 : 0));
}
