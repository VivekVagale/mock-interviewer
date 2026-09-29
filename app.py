"""AI Mock Interviewer.  Run:  streamlit run app.py   (needs `ollama serve` running)"""

import streamlit as st

from src import llm, speech
from src.grader import grade
from src.interviewer import follow_up, report
from src.questions import pick, topics

st.set_page_config(page_title="Mock Interviewer", page_icon="🎤", layout="centered")
S = st.session_state

st.title("🎤 AI Mock Interviewer")
st.caption("Campus-placement practice. Answer by typing or speaking; a local LLM checks your answer "
           "against the key points an interviewer listens for. Nothing leaves your laptop.")

if not llm.is_up():
    st.error("Ollama is not running. Start it (the Ollama app, or `ollama serve`) and refresh.")
    st.stop()

with st.sidebar:
    models = llm.installed_models() or [llm.MODEL]
    model = st.selectbox("Model", models, index=models.index(llm.MODEL) if llm.MODEL in models else 0)
    chosen = st.multiselect("Topics", topics(), default=["HR", "DBMS", "OS", "Machine Learning"])
    n = st.slider("Questions", 3, 10, 5)
    if st.button("Start new interview", type="primary", use_container_width=True, disabled=not chosen):
        S.questions, S.i, S.history, S.pending = pick(chosen, n), 0, [], None

if "questions" not in S:
    st.info("Pick topics in the sidebar and press **Start new interview**.")
    st.stop()

if S.i >= len(S.questions):
    st.success("Interview complete.")
    md = report(S.history)
    st.markdown(md)
    st.download_button("Download report", md, file_name="mock_interview_report.md")
    st.stop()

q = S.questions[S.i]
st.progress(S.i / len(S.questions), text=f"Question {S.i + 1} of {len(S.questions)} · {q['topic']}")
st.subheader(q["question"])

if S.pending is None:
    answer = ""
    if speech.available():
        audio = st.audio_input("Speak your answer")
        if audio is not None:
            with st.spinner("Transcribing..."):
                answer = speech.transcribe(audio.getvalue())
    answer = st.text_area("Your answer", value=answer, height=180,
                          help="Speak above, then fix the transcript here if needed, or just type.")
    if st.button("Submit answer", type="primary", disabled=not answer.strip()):
        with st.spinner("Grading against the rubric..."):
            g = grade(q, answer, model=model)
            fu = follow_up(q, answer, g, model=model)
        S.pending = {"question": q, "answer": answer, "graded": g, "follow_up": fu}
        st.rerun()
else:
    p, g = S.pending, S.pending["graded"]
    st.markdown(f"> {p['answer']}")
    st.metric("Score", f"{g['score']} / 10")
    icon = {"covered": "✅", "partial": "🟡", "missed": "❌"}
    for pt in g["points"]:
        ev = f" — *\"{pt['evidence']}\"*" if pt["evidence"] else ""
        st.markdown(f"{icon.get(pt['verdict'], '•')} {pt['point']}{ev}")
    for w in g["wrong_statements"]:
        st.markdown(f"⚠️ Incorrect: {w}")
    st.markdown(f"**Feedback:** {g['feedback']}")
    if p["follow_up"]:
        st.info(f"**The interviewer might follow up with:** {p['follow_up']}")
    with st.expander("A strong answer"):
        st.write(g["model_answer"])
    if st.button("Next question", type="primary"):
        S.history.append(p)
        S.pending, S.i = None, S.i + 1
        st.rerun()
