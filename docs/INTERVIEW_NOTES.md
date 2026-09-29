# Interview notes: AI Mock Interviewer

## The core problem: can an LLM grade answers fairly?

A mock interviewer is only useful if its score means something. "Rate this
answer out of 10" gives scores that drift between runs and reward long,
confident answers. So the design question was how to make grading *checkable*.

## Decisions

**Rubric of key points per question, not a free-form score.** Each question in
`data/questions.json` lists the 3-5 points an interviewer listens for. The LLM
does a narrow job: for each point, covered / partial / missed, plus the words
from the answer that prove it. Narrow judgments are more consistent than one
holistic number, and the quoted evidence lets a user see *why*.

**Score computed in code.** `score = 10 x (covered + 0.5 x partial) / points
- 1 per wrong statement (max 3)`. LLMs are unreliable at arithmetic and at
keeping a scale stable; code is not.

**Structured output (JSON schema).** Ollama's `format` parameter constrains
generation to the schema, so the reply always parses. No regex-scraping of
free text, no retry loops.

**Temperature 0 for grading.** Same answer, same score. Consistency is
measured anyway by re-grading at temperature 0.7.

**Local model via Ollama.** Free, private (answers never leave the laptop),
works offline. Trade-off: smaller models than a paid API. The eval measures
whether that is good enough.

**Curated question bank over LLM-generated questions.** Generated questions
cannot be graded against a known rubric, and they vary in difficulty. The LLM
is used where it adds value: judging answers and writing a follow-up question
that nudges toward the missed point without giving it away.

**Voice via faster-whisper, optional.** Interviews are spoken; typing an
answer is a different skill. Whisper runs locally; the transcript stays
editable because speech-to-text makes mistakes on technical words.

## How the grader is validated

`eval/graded_answers.json`: 12 questions x 4 answers written on purpose to be
**strong**, **medium**, **weak**, and **waffle** (fluent, confident, long, but
missing every key point). They are synthetic and labeled as such.

Four checks (`python -m src.evaluate --model ...`):

1. **Ordering accuracy**: on how many questions is strong > medium > weak?
2. **Spearman correlation** between intended quality and score.
3. **Waffle test**: does filler score below a genuine medium answer? This is
   the length / confidence bias every LLM judge is known for.
4. **Consistency**: standard deviation of the score over re-grades at temperature 0.7.

Both models are compared on these plus seconds per grade. See `README.md` for the numbers.

## Limits

- The eval answers were written by one person. The next step is 30-40 real
  answers from classmates, each scored by a human, and reporting how often the
  grader agrees with the human.
- The rubric only knows what is in it. A creative correct answer that uses
  different points can be under-scored.
- HR answers are graded on structure (STAR, evidence), not on whether the
  story is true.
