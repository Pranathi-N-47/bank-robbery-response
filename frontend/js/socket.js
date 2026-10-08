class SimulationSocket {
  constructor(url, onMessageCallback) {
    this.url = url;
    this.onMessageCallback = onMessageCallback;
    this.ws = null;
    this.reconnectInterval = 2000;
  }

  connect() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const socketUrl = `${protocol}//${window.location.host}/ws`;
    this.ws = new WebSocket(socketUrl);

    this.ws.onopen = () => {
      console.log("[WS] Connected to Simulation Server");
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (this.onMessageCallback) {
          this.onMessageCallback(data);
        }
      } catch (err) {
        console.error("[WS] Error parsing JSON payload:", err);
      }
    };

    this.ws.onclose = () => {
      console.warn("[WS] Socket disconnected, attempting reconnection...");
      setTimeout(() => this.connect(), this.reconnectInterval);
    };

    this.ws.onerror = (err) => {
      console.error("[WS] Socket error:", err);
    };
  }

  send(data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }
}
