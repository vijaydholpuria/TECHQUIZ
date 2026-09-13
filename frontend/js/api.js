window.TechQuizApi = (() => {
  async function request(path, options = {}) {
    const API_BASE_URL = "https://techquiz-232i.onrender.com";

    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
    });

    if (!response.ok) {
      let detail = "Something went wrong. Please try again.";
      try {
        detail = (await response.json()).detail || detail;
      } catch (_) {
        /* response was not JSON */
      }
      throw new Error(detail);
    }

    if (response.status === 204) return null;
    return response.json();
  }

  function setNotice(element, message = "", type = "") {
    if (!element) return;
    element.textContent = message;
    element.className = `notice ${type}`;
  }

  function setBusy(button, busy, busyLabel) {
    if (!button) return;
    if (busy) {
      button.dataset.label = button.textContent;
      button.textContent = busyLabel || "Working…";
      button.disabled = true;
    } else {
      button.textContent = button.dataset.label || button.textContent;
      button.disabled = false;
    }
  }

  function pageQuizId() {
    const parts = location.pathname.split("/").filter(Boolean);
    const quizIndex = parts.indexOf("quiz");
    if (quizIndex > -1) return parts[quizIndex + 1];
    return parts[0] === "join" ? parts[1] : null;
  }

  function escapeHtml(value) {
    return String(value ?? "").replace(
      /[&<>'"]/g,
      (character) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          "'": "&#039;",
          '"': "&quot;",
        })[character],
    );
  }

  return { request, setNotice, setBusy, pageQuizId, escapeHtml };
})();
