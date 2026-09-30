import { followUp, grade, pick, report } from "./grader.js";

const WEBLLM = "https://cdn.jsdelivr.net/npm/@mlc-ai/web-llm@0.2.85/+esm";
const TRANSFORMERS = "https://cdn.jsdelivr.net/npm/@huggingface/transformers@3";

// Browser-sized models WebLLM ships. The grader was checked on each one with
// the same test set as the local 8B model; see results/ in the repo.
const MODELS = [
  { id: "Qwen3-4B-q4f16_1-MLC", label: "Qwen3 4B · best grading", gb: 3.4 },
  { id: "Qwen3-1.7B-q4f16_1-MLC", label: "Qwen3 1.7B · faster, less accurate", gb: 2.0 },
];

const $ = (id) => document.getElementById(id);
const S = { bank: [], topics: new Set(["HR", "DBMS", "OS", "Machine Learning"]), engine: null, engineId: null,
            questions: [], i: 0, history: [], pending: null, asr: null, rec: null };

// ---------- setup ----------
S.bank = await (await fetch("data/questions.json")).json();
for (const t of [...new Set(S.bank.map((q) => q.topic))]) {
  const b = document.createElement("button");
  b.className = "chip"; b.textContent = t; b.setAttribute("aria-pressed", S.topics.has(t));
  b.onclick = () => { S.topics.has(t) ? S.topics.delete(t) : S.topics.add(t); b.setAttribute("aria-pressed", S.topics.has(t)); $("start").disabled = !S.topics.size; };
  $("topics").append(b);
}
for (const m of MODELS) $("model").add(new Option(m.label, m.id));
const noteModel = () => {
  const m = MODELS.find((x) => x.id === $("model").value);
  $("modelNote").textContent = `Downloads once (about ${m.gb} GB of GPU memory needed), then it is cached and works offline.`;
};
$("model").onchange = noteModel; noteModel();
$("n").oninput = (e) => ($("nV").textContent = e.target.value);

const hasGPU = !!navigator.gpu && !!(await navigator.gpu.requestAdapter().catch(() => null));
if (!hasGPU) { $("nogpu").classList.remove("hidden"); $("start").disabled = true; }

function show(id) { for (const s of ["setup", "ask", "result", "done"]) $(s).classList.toggle("hidden", s !== id); }

// ---------- model ----------
async function loadModel(id) {
  if (S.engine && S.engineId === id) return;
  $("loading").classList.remove("hidden"); $("start").disabled = true;
  const webllm = await import(WEBLLM);
  S.engine = await webllm.CreateMLCEngine(id, {
    initProgressCallback: (p) => { $("loadBar").style.width = `${Math.round(p.progress * 100)}%`; $("loadText").textContent = p.text; },
  });
  S.engineId = id;
  $("loading").classList.add("hidden"); $("start").disabled = false;
}

// ---------- interview flow ----------
$("start").onclick = async () => {
  try { await loadModel($("model").value); }
  catch (e) { $("loadText").textContent = `Could not load the model: ${e.message}`; $("start").disabled = false; return; }
  S.questions = pick(S.bank, [...S.topics], +$("n").value);
  S.i = 0; S.history = [];
  ask();
};

function ask() {
  const q = S.questions[S.i];
  $("qmeta").textContent = `Question ${S.i + 1} of ${S.questions.length} · ${q.topic}`;
  $("question").textContent = q.question;
  $("answer").value = ""; $("submit").disabled = true; $("askNote").textContent = "";
  show("ask"); $("answer").focus();
}
$("answer").oninput = () => ($("submit").disabled = !$("answer").value.trim());

$("submit").onclick = async () => {
  const q = S.questions[S.i], answer = $("answer").value.trim();
  $("submit").disabled = true; $("askNote").textContent = "Checking your answer against the key points…";
  try {
    const g = await grade(S.engine, q, answer);
    $("askNote").textContent = "Thinking of a follow-up…";
    const fu = await followUp(S.engine, q, answer, g).catch(() => null);
    S.pending = { question: q, answer, graded: g, followUp: fu };
    showResult();
  } catch (e) {
    $("askNote").textContent = `The model could not grade that (${e.message}). Try again.`; $("submit").disabled = false;
  }
};

const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

function showResult() {
  const { question, answer, graded: g, followUp: fu } = S.pending;
  $("ring").style.setProperty("--p", g.score * 10);
  $("score").textContent = g.score;
  $("rq").textContent = question.question;
  $("rcomm").textContent = `Clarity and structure: ${g.communication}/5`;
  $("yours").textContent = answer;
  const GLYPH = { covered: "M5 12l5 5 9-10", partial: "M6 12h12", missed: "M7 7l10 10M17 7 7 17" };
  const glyph = (v) => `<span class="g"><svg class="i" viewBox="0 0 24 24" style="width:14px;height:14px;stroke-width:3"><path d="${GLYPH[v] ?? GLYPH.missed}"/></svg></span>`;
  $("points").innerHTML = g.points.map((p) => `<div class="pt ${esc(p.verdict)}">${glyph(p.verdict)}
    <div><span class="tag">${esc(p.verdict)}</span>${esc(p.point)}${p.evidence ? `<q>${esc(p.evidence)}</q>` : ""}</div></div>`).join("")
    + (g.wrong_statements ?? []).map((w) => `<div class="pt missed">${glyph("missed")}<div><span class="tag">Incorrect</span>${esc(w)}</div></div>`).join("");
  $("feedback").textContent = g.feedback;
  $("followup").classList.toggle("hidden", !fu);
  $("followup").innerHTML = fu ? `<b>The interviewer might follow up:</b> ${esc(fu)}` : "";
  $("modelAnswer").textContent = g.model_answer;
  $("next").innerHTML = S.i + 1 < S.questions.length
    ? `<svg class="i"><use href="#i-next"/></svg>Next question` : `<svg class="i"><use href="#i-next"/></svg>See my report`;
  show("result");
}

$("next").onclick = () => {
  S.history.push(S.pending); S.pending = null; S.i++;
  if (S.i < S.questions.length) return ask();
  const md = report(S.history);
  $("report").innerHTML = mdToHtml(md);
  show("done");
};
$("again").onclick = () => show("setup");
$("download").onclick = () => {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([report(S.history)], { type: "text/markdown" }));
  a.download = "mock_interview_report.md"; a.click();
};

// tiny Markdown renderer for the report (headings, bold, tables, lists, quotes)
function mdToHtml(md) {
  const inline = (s) => esc(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
  const out = []; let table = null, list = false;
  for (const line of md.split("\n")) {
    if (line.startsWith("|")) {
      const cells = line.split("|").slice(1, -1).map((c) => c.trim());
      if (cells.every((c) => /^-+$/.test(c))) continue;
      if (!table) { table = []; out.push("<table>"); }
      out.push(`<tr>${cells.map((c) => `<td>${inline(c)}</td>`).join("")}</tr>`); continue;
    } else if (table) { out.push("</table>"); table = null; }
    if (line.startsWith("- ")) { if (!list) { out.push("<ul>"); list = true; } out.push(`<li>${inline(line.slice(2))}</li>`); continue; }
    else if (list) { out.push("</ul>"); list = false; }
    const h = line.match(/^(#{1,3}) (.*)/);
    if (h) out.push(`<h${h[1].length + 1}>${inline(h[2])}</h${h[1].length + 1}>`);
    else if (line.startsWith("> ")) out.push(`<blockquote>${inline(line.slice(2))}</blockquote>`);
    else if (line.trim()) out.push(`<p>${inline(line)}</p>`);
  }
  if (table) out.push("</table>"); if (list) out.push("</ul>");
  return out.join("");
}

// ---------- voice: record, then transcribe on-device with Whisper (tiny.en, ~40 MB, loaded on first use) ----------
$("record").onclick = async () => {
  if (S.rec) { S.rec.stop(); return; }
  let stream;
  try { stream = await navigator.mediaDevices.getUserMedia({ audio: true }); }
  catch (e) { $("askNote").textContent = `Microphone not available: ${e.message}`; return; }
  const chunks = [];
  S.rec = new MediaRecorder(stream);
  S.rec.ondataavailable = (e) => chunks.push(e.data);
  S.rec.onstop = async () => {
    stream.getTracks().forEach((t) => t.stop());
    S.rec = null; $("record").classList.remove("rec"); $("record").querySelector("span").textContent = "Record";
    $("record").querySelector("use").setAttribute("href", "#i-mic");
    $("askNote").textContent = S.asr ? "Transcribing…" : "Loading speech recognition (once, ~40 MB)…";
    try {
      if (!S.asr) {
        const { pipeline } = await import(TRANSFORMERS);
        S.asr = await pipeline("automatic-speech-recognition", "Xenova/whisper-tiny.en");
        $("askNote").textContent = "Transcribing…";
      }
      const ctx = new AudioContext({ sampleRate: 16000 });
      const audio = await ctx.decodeAudioData(await new Blob(chunks).arrayBuffer());
      const { text } = await S.asr(audio.getChannelData(0), { chunk_length_s: 30 });
      $("answer").value = ($("answer").value + " " + text).trim();
      $("submit").disabled = !$("answer").value.trim();
      $("askNote").textContent = "Check the transcript, fix any mistakes, then submit.";
    } catch (e) { $("askNote").textContent = `Could not transcribe: ${e.message}`; }
  };
  S.rec.start();
  $("record").classList.add("rec"); $("record").querySelector("span").textContent = "Stop";
  $("record").querySelector("use").setAttribute("href", "#i-stop");
  $("askNote").textContent = "Recording… press Stop when you finish.";
};
