document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector("#quick-join");
  if (!form) return;
  const input = document.querySelector("#quiz-id");
  const message = document.querySelector("#quick-join-message");
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const id = input.value.trim().toUpperCase();
    if (!/^TECH-[A-F0-9]{6}$/.test(id)) return TechQuizApi.setNotice(message, "Enter the quiz ID from your host, e.g. TECH-7F4A92.", "error");
    location.href = `/join/${encodeURIComponent(id)}`;
  });
});
