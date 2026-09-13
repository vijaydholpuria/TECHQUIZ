document.addEventListener("DOMContentLoaded", () => {
  if (document.body.dataset.page !== "admin-login") return;
  const form = document.querySelector("#login-form");
  const button = document.querySelector("#login-button");
  const message = document.querySelector("#login-message");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    TechQuizApi.setBusy(button, true, "Signing in…");
    TechQuizApi.setNotice(message);
    try {
      await TechQuizApi.request("/api/admin/login", { method: "POST", body: JSON.stringify({ username: form.username.value.trim(), password: form.password.value }) });
      location.href = "/admin/dashboard";
    } catch (error) {
      TechQuizApi.setNotice(message, error.message, "error");
      TechQuizApi.setBusy(button, false);
    }
  });
});
