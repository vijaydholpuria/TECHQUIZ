window.TechQuizSocket = class {
  constructor(quizId, options) {
    this.quizId = quizId;
    this.options = options;
    this.closed = false;
    this.reconnectMs = 750;
    this.socket = null;
    this.connect();
  }

  connect() {
    const protocol = location.protocol === "https:" ? "wss" : "ws";
    const query = new URLSearchParams(this.options.query || {});
    this.socket = new WebSocket(`${protocol}://${location.host}/ws/quiz/${encodeURIComponent(this.quizId)}?${query}`);
    this.socket.onopen = () => {
      this.reconnectMs = 750;
      this.options.onStatus?.("connected");
      this.ping = setInterval(() => { if (this.socket?.readyState === WebSocket.OPEN) this.socket.send("ping"); }, 20000);
    };
    this.socket.onmessage = (event) => {
      try { this.options.onEvent?.(JSON.parse(event.data)); } catch (_) { /* ignore malformed network messages */ }
    };
    this.socket.onclose = () => {
      clearInterval(this.ping);
      if (this.closed) return;
      this.options.onStatus?.("reconnecting");
      window.setTimeout(() => this.connect(), this.reconnectMs);
      this.reconnectMs = Math.min(this.reconnectMs * 1.7, 8000);
    };
    this.socket.onerror = () => this.socket.close();
  }

  close() { this.closed = true; clearInterval(this.ping); this.socket?.close(); }
};
