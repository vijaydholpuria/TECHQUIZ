document.addEventListener("DOMContentLoaded", () => {
  const page = document.body.dataset.page;
  if (!page?.startsWith("admin-")) return;
  if (page === "admin-login") return;
  initializeAdmin(page);
});

async function initializeAdmin(page) {
  try {
    await TechQuizApi.request("/api/admin/me");
  } catch (_) {
    location.href = "/admin/login";
    return;
  }
  wireLogout();
  if (page === "admin-dashboard") loadDashboard();
  if (page === "admin-create") initializeBuilder();
  if (page === "admin-qr") initializeQr();
  if (page === "admin-live") initializeLive();
  if (page === "admin-results") initializeResults();
}

function wireLogout() {
  const button = document.querySelector("#logout-button");
  button?.addEventListener("click", async () => {
    await TechQuizApi.request("/api/admin/logout", { method: "POST" });
    location.href = "/";
  });
}

async function loadDashboard() {
  const message = document.querySelector("#dashboard-message");
  try {
    const data = await TechQuizApi.request("/api/admin/dashboard");
    const values = [data.total_active_quizzes, data.current_participants, data.current_status, data.total_questions];
    document.querySelectorAll("#metrics .value").forEach((node, index) => node.textContent = values[index]);
    const card = document.querySelector("#active-quiz");
    if (!data.active_quiz) {
      card.innerHTML = `<div class="kicker">No current quiz</div><h2>Create your first competition</h2><p>Build questions, generate a QR code, and invite your players.</p>`;
      return;
    }
    const quiz = data.active_quiz;
    const e = TechQuizApi.escapeHtml;
    card.innerHTML = `<div class="kicker">Current quiz</div><h2>${e(quiz.name)}</h2><div class="meta-row"><span>ID: <strong>${e(quiz.id)}</strong></span><span>${quiz.question_count} question${quiz.question_count === 1 ? "" : "s"}</span><span>${quiz.participant_count} participant${quiz.participant_count === 1 ? "" : "s"}</span><span class="status-badge ${statusClass(quiz.status)}">${e(quiz.status)}</span></div><div class="admin-actions"><a class="button button-secondary" href="/admin/quiz/${encodeURIComponent(quiz.id)}/qr">View QR</a><a class="button button-secondary" href="/admin/quiz/${encodeURIComponent(quiz.id)}/live">View live status</a><a class="button button-primary" href="/admin/quiz/${encodeURIComponent(quiz.id)}/results">View results</a></div>`;
  } catch (error) { TechQuizApi.setNotice(message, error.message, "error"); }
}

function statusClass(status) { return status === "FINISHED" ? "finished" : status === "QUESTION_ACTIVE" ? "active" : ""; }

function initializeBuilder() {
  const list = document.querySelector("#question-list");
  const add = document.querySelector("#add-question");
  const form = document.querySelector("#quiz-builder");
  const button = document.querySelector("#generate-quiz");
  const message = document.querySelector("#builder-message");
  const addQuestion = () => {
    const number = list.children.length + 1;
    const card = document.createElement("article");
    card.className = "card question-editor";
    card.innerHTML = `<div class="question-head"><h2>Question ${number} of <span class="question-total">${number}</span></h2><button type="button" class="button button-danger button-small delete-question">Delete question</button></div><div class="field"><label>Question text</label><textarea data-field="question_text" maxlength="2000" required placeholder="Write the question"></textarea></div><div class="options-grid"><div class="field"><label>Option A</label><input data-field="option_a" maxlength="500" required></div><div class="field"><label>Option B</label><input data-field="option_b" maxlength="500" required></div><div class="field"><label>Option C</label><input data-field="option_c" maxlength="500" required></div><div class="field"><label>Option D</label><input data-field="option_d" maxlength="500" required></div></div><div class="form-row"><div class="field"><label>Correct answer</label><select data-field="correct_option"><option value="A">A</option><option value="B">B</option><option value="C">C</option><option value="D">D</option></select></div><div class="field"><label>Time limit (seconds)</label><input data-field="time_limit" type="number" min="1" max="300" value="15" required></div></div>`;
    card.querySelector(".delete-question").addEventListener("click", () => { card.remove(); renumberQuestions(); });
    list.append(card);
    renumberQuestions();
  };
  add.addEventListener("click", addQuestion);
  addQuestion();
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const name = document.querySelector("#quiz-name").value.trim();
    const questions = [...list.children].map((card) => {
      const get = (field) => card.querySelector(`[data-field="${field}"]`).value.trim();
      return { question_text: get("question_text"), option_a: get("option_a"), option_b: get("option_b"), option_c: get("option_c"), option_d: get("option_d"), correct_option: get("correct_option"), time_limit: Number(get("time_limit")) };
    });
    if (!name || !questions.length || questions.some((item) => !item.question_text || !item.option_a || !item.option_b || !item.option_c || !item.option_d || !Number.isInteger(item.time_limit) || item.time_limit < 1 || item.time_limit > 300)) {
      return TechQuizApi.setNotice(message, "Add a quiz name, all four options, and a time between 1 and 300 seconds for every question.", "error");
    }
    TechQuizApi.setBusy(button, true, "Generating quiz…");
    TechQuizApi.setNotice(message);
    try {
      const data = await TechQuizApi.request("/api/quizzes", { method: "POST", body: JSON.stringify({ name, questions }) });
      location.href = `/admin/quiz/${encodeURIComponent(data.id)}/qr`;
    } catch (error) {
      TechQuizApi.setNotice(message, error.message, "error");
      TechQuizApi.setBusy(button, false);
    }
  });
}

function renumberQuestions() {
  document.querySelectorAll("#question-list .question-editor").forEach((card, index, all) => {
    card.querySelector(".question-head h2").innerHTML = `Question ${index + 1} of <span class="question-total">${all.length}</span>`;
    card.querySelector(".delete-question").disabled = all.length === 1;
  });
}

async function initializeQr() {
  const id = TechQuizApi.pageQuizId();
  const title = document.querySelector("#qr-quiz-name");
  const image = document.querySelector("#qr-image");
  const status = document.querySelector("#qr-status");
  const total = document.querySelector("#participant-total");
  const list = document.querySelector("#participant-list");
  const message = document.querySelector("#qr-message");
  const startButton = document.querySelector("#start-button");
  document.querySelector("#live-link").href = `/admin/quiz/${encodeURIComponent(id)}/live`;
  image.src = `https://techquiz-232i.onrender.com/api/quizzes/${encodeURIComponent(id)}/qr`;
  const renderParticipants = async () => {
    try {
      const [details, people] = await Promise.all([TechQuizApi.request(`/api/quizzes/${id}`), TechQuizApi.request(`/api/admin/quizzes/${id}/participants`)]);
      title.textContent = details.name;
      status.textContent = details.status;
      status.className = `status-badge ${statusClass(details.status)}`;
      total.textContent = people.total;
      list.innerHTML = people.participants.length ? people.participants.map((person, index) => `<li><span>${index + 1}. ${TechQuizApi.escapeHtml(person.name)}</span><span>Joined</span></li>`).join("") : "<li>Waiting for players…</li>";
      startButton.disabled = details.status !== "WAITING";
      if (details.status !== "WAITING") startButton.textContent = "Quiz started";
    } catch (error) { TechQuizApi.setNotice(message, error.message, "error"); }
  };
  await renderParticipants();
  const socket = new TechQuizSocket(id, { query: { admin_mode: "true" }, onEvent: (event) => {
    if (event.type === "PARTICIPANT_COUNT" || event.type === "STATE") renderParticipants();
  }});
  startButton.addEventListener("click", async () => {
    TechQuizApi.setBusy(startButton, true, "Starting quiz…");
    try { await TechQuizApi.request(`/api/admin/quizzes/${id}/start`, { method: "POST" }); location.href = `/admin/quiz/${encodeURIComponent(id)}/live`; }
    catch (error) { TechQuizApi.setNotice(message, error.message, "error"); TechQuizApi.setBusy(startButton, false); }
  });
  window.addEventListener("beforeunload", () => socket.close());
}

function initializeLive() {
  const id = TechQuizApi.pageQuizId();
  document.querySelector("#live-results").href = `/admin/quiz/${encodeURIComponent(id)}/results`;
  const status = document.querySelector("#live-status");
  const time = document.querySelector("#live-time");
  const end = document.querySelector("#end-button");
  const message = document.querySelector("#live-message");
  let endTime = null, offset = 0, timer;
  const tick = () => {
    if (!endTime) return time.textContent = "—";
    const seconds = Math.max(0, Math.ceil((new Date(endTime).getTime() - (Date.now() + offset)) / 1000));
    time.textContent = `${seconds}s`;
  };
  const render = (event) => {
    if (event.type === "PARTICIPANT_PROGRESS") { document.querySelector("#live-answered").textContent = event.answered_count; return; }
    if (event.type === "QUIZ_FINISHED") { document.querySelector("#live-description").textContent = "Quiz completed. Final standings are ready."; return; }
    if (event.type !== "STATE") return;
    document.querySelector("#live-title").textContent = `${event.name} — LIVE`;
    status.textContent = event.status;
    status.className = `status-badge ${statusClass(event.status)}`;
    document.querySelector("#live-question").textContent = `${event.current_question || 0} / ${event.total_questions}`;
    document.querySelector("#live-participants").textContent = event.participant_count;
    document.querySelector("#live-answered").textContent = event.answered_count ?? "—";
    document.querySelector("#live-question-text").textContent = event.question?.question || (event.status === "FINISHED" ? "Quiz completed — results are ready." : "Waiting for the quiz to begin.");
    end.disabled = event.status !== "QUESTION_ACTIVE";
    endTime = event.end_time || null;
    offset = event.server_time ? new Date(event.server_time).getTime() - Date.now() : 0;
    tick();
  };
  const socket = new TechQuizSocket(id, { query: { admin_mode: "true" }, onEvent: render, onStatus: (state) => { if (state === "reconnecting") TechQuizApi.setNotice(message, "Connection lost. Reconnecting…", "error"); else TechQuizApi.setNotice(message, "Live connection established.", "success"); } });
  timer = setInterval(tick, 250);
  end.addEventListener("click", async () => {
    if (!confirm("End this quiz and finalize the results? This cannot be undone.")) return;
    TechQuizApi.setBusy(end, true, "Finalizing…");
    try { await TechQuizApi.request(`/api/admin/quizzes/${id}/end`, { method: "POST" }); location.href = `/admin/quiz/${encodeURIComponent(id)}/results`; }
    catch (error) { TechQuizApi.setNotice(message, error.message, "error"); TechQuizApi.setBusy(end, false); }
  });
  window.addEventListener("beforeunload", () => { socket.close(); clearInterval(timer); });
}

function initializeResults() {
  const id = TechQuizApi.pageQuizId();
  const title = document.querySelector("#results-title");
  const subtitle = document.querySelector("#results-subtitle");
  const message = document.querySelector("#results-message");
  document.querySelector("#export-results").href = `/api/admin/quizzes/${encodeURIComponent(id)}/results.csv`;
  const load = async () => {
    try {
      const data = await TechQuizApi.request(`/api/admin/quizzes/${id}/results`);
      title.textContent = `${data.quiz.name} — RESULTS`;
      subtitle.textContent = `${data.quiz.participant_count} participant${data.quiz.participant_count === 1 ? "" : "s"} · ${data.quiz.question_count} question${data.quiz.question_count === 1 ? "" : "s"} · ${data.quiz.status}`;
      const medals = ["🥇", "🥈", "🥉"];
      document.querySelector("#podium").innerHTML = data.leaderboard.slice(0, 3).map((row, index) => `<article class="podium-card"><div class="medal">${medals[index]}</div><div class="podium-name">${TechQuizApi.escapeHtml(row.name)}</div><div class="podium-score">${row.score} points</div></article>`).join("") || "<p class=\"help\">No participants joined this quiz.</p>";
      document.querySelector("#results-table").innerHTML = data.leaderboard.map((row) => `<tr><td>#${row.rank}</td><td>${TechQuizApi.escapeHtml(row.name)}</td><td>${row.score}</td><td>${row.correct}</td><td>${row.wrong}</td><td>${row.unanswered}</td><td>${row.total_response_time}s</td></tr>`).join("") || "<tr><td colspan=\"7\">No results yet.</td></tr>";
      TechQuizApi.setNotice(message);
    } catch (error) { TechQuizApi.setNotice(message, error.message, "error"); }
  };
  document.querySelector("#refresh-results").addEventListener("click", load);
  load();
}
