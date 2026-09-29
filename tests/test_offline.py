"""Tests that need no LLM: scoring arithmetic, question picking, the stats."""

from src.evaluate import spearman
from src.grader import score
from src.interviewer import report
from src.questions import load, pick


def test_every_question_has_a_rubric():
    for q in load():
        assert q["question"].strip() and len(q["key_points"]) >= 3, q["id"]


def test_score_counts_partial_as_half_and_penalises_wrong_facts():
    graded = {"points": [{"verdict": "covered"}, {"verdict": "partial"}, {"verdict": "missed"}, {"verdict": "covered"}],
              "wrong_statements": ["x"]}
    assert abs(score(graded, 4) - (10 * 2.5 / 4 - 1)) <= 0.05  # 5.25, rounded to one decimal


def test_score_never_negative():
    assert score({"points": [{"verdict": "missed"}], "wrong_statements": ["a", "b", "c", "d"]}, 1) == 0.0


def test_pick_spreads_across_topics_and_puts_hr_first():
    qs = pick(["DBMS", "HR", "OS"], 6, seed=1)
    assert len(qs) == 6
    assert {q["topic"] for q in qs} == {"DBMS", "HR", "OS"}
    assert qs[0]["topic"] == "HR"


def test_spearman_perfect_and_reversed():
    assert round(spearman([1, 2, 3], [10, 20, 30]), 6) == 1.0
    assert round(spearman([1, 2, 3], [30, 20, 10]), 6) == -1.0


def test_report_lists_missed_points():
    q = load()[0]
    g = {"score": 5.0, "points": [{"point": "the missed idea", "verdict": "missed", "evidence": ""}],
         "feedback": "f", "model_answer": "m"}
    md = report([{"question": q, "answer": "a", "graded": g}])
    assert "5.0 / 10" in md and "the missed idea" in md
