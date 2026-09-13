document.addEventListener("DOMContentLoaded", () => {
  if (document.body.dataset.page !== "participant") return;
  initializeParticipant();
});

function initializeParticipant() {
  const quizId = TechQuizApi.pageQuizId();
  const screens = {
    join: document.querySelector("#join-screen"), waiting: document.querySelector("#waiting-screen"), quiz: document.querySelector("#quiz-screen"), result: document.querySelector("#result-screen"),
  };
  const storageKey = `techquiz-participant:${quizId}`;
  let identity = null;
  let socket = null;
  let currentQuestion = null;
  let submittedQuestionId = null;
  let serverOffset = 0;
  let endTime = null;
  let timer = null;

  try { identity = JSON.parse(sessionStorage.getItem(storageKey) || "null"); } catch (_) { /* storage is optional */ }
  const show = (name) => Object.entries(screens).forEach(([key, node]) => node.classList.toggle("hidden", key !== name));
  const setConnection = (state) => {
    const text = state === "connected" ? "Live connection established." : "Connection lost. Reconnecting…";
    [document.querySelector("#connection-status"), document.querySelector("#quiz-connection")].forEach((node) => { if (node) { node.textContent = text; node.classList.toggle("reconnecting", state !== "connected"); } });
  };

  async function loadQuizInfo() {
    try {
      const data = await TechQuizApi.request(`/api/quizzes/${encodeURIComponent(quizId)}`);
      document.querySelector("#join-title").textContent = data.name;
      document.querySelector("#join-subtitle").textContent = data.status === "WAITING" ? "Enter your name to enter the waiting room." : "This quiz has already started or finished.";
      if (!identity && data.status !== "WAITING") {
        document.querySelector("#join-button").disabled = true;
        TechQuizApi.setNotice(document.querySelector("#join-message"), "New participants can only join before the host starts the quiz.", "error");
      }
    } catch (error) {
      document.querySelector("#join-button").disabled = true;
      TechQuizApi.setNotice(document.querySelector("#join-message"), error.message, "error");
    }
  }

  function connect() {
    if (!identity?.participant_token) return;
    socket?.close();
    socket = new TechQuizSocket(quizId, {
      query: { participant_token: identity.participant_token },
      onStatus: setConnection,
      onEvent: handleEvent,
    });
  }

  function handleEvent(event) {
    if (event.type === "PARTICIPANT_COUNT") {
      document.querySelector("#waiting-count").textContent = event.participant_count;
      return;
    }
    if (event.type === "PARTICIPANT_PROGRESS") return;
    if (event.type === "QUESTION_ENDED") {
      lockOptions();
      document.querySelector("#answer-feedback").textContent = "Time up! Waiting for the next question…";
      return;
    }
    if (event.type === "QUIZ_FINISHED") {
      showResult();
      return;
    }
    if (event.type === "STATE") renderState(event);
  }

  function renderState(state) {
    document.querySelector("#waiting-count").textContent = state.participant_count ?? 0;
    if (state.status === "FINISHED") return showResult();
    if (state.status !== "QUESTION_ACTIVE" || !state.question) {
      show("waiting");
      return;
    }
    show("quiz");
    serverOffset = state.server_time ? new Date(state.server_time).getTime() - Date.now() : serverOffset;
    endTime = state.end_time;
    if (!currentQuestion || currentQuestion.id !== state.question.id) {
      currentQuestion = state.question;
      submittedQuestionId = state.has_answered ? state.question.id : null;
      renderQuestion(state.question);
    } else if (state.has_answered) {
      submittedQuestionId = state.question.id;
      lockOptions();
      document.querySelector("#answer-feedback").textContent = "Answer submitted and locked ✓";
    }
    updateTimer();
  }

  function renderQuestion(question) {
    document.querySelector("#question-number").textContent = `Question ${question.number}`;
    document.querySelector("#question-total").textContent = `${question.number} of live quiz`;
    document.querySelector("#question-text").textContent = question.question;
    const options = document.querySelector("#answer-options");
    options.replaceChildren();
    Object.entries(question.options).forEach(([letter, label]) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "answer-option";
      button.dataset.option = letter;
      const badge = document.createElement("span");
      badge.className = "letter";
      badge.textContent = letter;
      button.append(badge, document.createTextNode(label));
      button.addEventListener("click", () => sendAnswer(letter, button));
      options.append(button);
    });
    document.querySelector("#answer-feedback").textContent = submittedQuestionId === question.id ? "Answer submitted and locked ✓" : "Answer quickly—your answer locks after selection.";
    if (submittedQuestionId === question.id) lockOptions();
  }

  function lockOptions(selected) {
    document.querySelectorAll("#answer-options .answer-option").forEach((button) => {
      button.disabled = true;
      button.classList.toggle("locked", selected ? button === selected : button.dataset.option === document.querySelector(".answer-option.locked")?.dataset.option);
    });
  }

  async function sendAnswer(selectedOption, selectedButton) {
    if (!currentQuestion || submittedQuestionId === currentQuestion.id) return;
    lockOptions(selectedButton);
    document.querySelector("#answer-feedback").textContent = "Submitting answer…";
    try {
      await TechQuizApi.request(`/api/quizzes/${encodeURIComponent(quizId)}/answer`, { method: "POST", body: JSON.stringify({ participant_token: identity.participant_token, question_id: currentQuestion.id, selected_option: selectedOption }) });
      submittedQuestionId = currentQuestion.id;
      document.querySelector("#answer-feedback").textContent = "Answer submitted and locked ✓";
    } catch (error) {
      document.querySelector("#answer-feedback").textContent = error.message === "Time is over." ? "Time up! Waiting for the next question…" : error.message;
    }
  }

  function updateTimer() {
    const node = document.querySelector("#timer");
    if (!endTime) { node.textContent = "—"; return; }
    const seconds = Math.max(0, Math.ceil((new Date(endTime).getTime() - (Date.now() + serverOffset)) / 1000));
    node.textContent = seconds;
    node.className = `timer ${seconds === 0 ? "expired" : seconds <= 5 ? "warning" : ""}`;
    if (seconds === 0) lockOptions();
  }

  async function showResult() {
    show("result");
    clearInterval(timer);
    document.querySelector("#result-name").textContent = "Calculating results…";
    try {
      const data = await TechQuizApi.request(`/api/quizzes/${encodeURIComponent(quizId)}/my-result?participant_token=${encodeURIComponent(identity.participant_token)}`);
      if (data.status !== "FINISHED") { setTimeout(showResult, 800); return; }
      document.querySelector("#result-name").textContent = `${data.name}, you finished at rank #${data.rank}.`;
      document.querySelector("#my-result-cards").innerHTML = `<article class="podium-card"><div class="medal">🏆</div><div class="podium-name">${data.score} points</div><div class="podium-score">Total score</div></article><article class="podium-card"><div class="medal">✓</div><div class="podium-name">${data.correct}</div><div class="podium-score">Correct answers</div></article><article class="podium-card"><div class="medal">⚡</div><div class="podium-name">${data.total_response_time}s</div><div class="podium-score">Response time</div></article>`;
      document.querySelector("#my-result-table").innerHTML = `<tr><td>#${data.rank}</td><td>${TechQuizApi.escapeHtml(data.name)}</td><td>${data.score}</td><td>${data.correct}</td><td>${data.wrong}</td><td>${data.unanswered}</td></tr>`;
    } catch (error) { document.querySelector("#result-name").textContent = error.message; }
  }

  document.querySelector("#join-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const name = document.querySelector("#participant-name").value.trim();
    const button = document.querySelector("#join-button");
    const message = document.querySelector("#join-message");
    if (!name) return TechQuizApi.setNotice(message, "Name is required.", "error");
    TechQuizApi.setBusy(button, true, "Joining quiz…");
    TechQuizApi.setNotice(message);
    try {
      const data = await TechQuizApi.request(`/api/quizzes/${encodeURIComponent(quizId)}/join`, { method: "POST", body: JSON.stringify({ name }) });
      identity = data;
      sessionStorage.setItem(storageKey, JSON.stringify(identity));
      document.querySelector("#waiting-name").textContent = data.name;
      show("waiting");
      connect();
    } catch (error) { TechQuizApi.setNotice(message, error.message, "error"); TechQuizApi.setBusy(button, false); }
  });

  loadQuizInfo();
  if (identity?.participant_token) {
    document.querySelector("#waiting-name").textContent = identity.name || "Player";
    show("waiting");
    connect();
  }
  timer = setInterval(updateTimer, 250);
  window.addEventListener("beforeunload", () => { socket?.close(); clearInterval(timer); });
}
