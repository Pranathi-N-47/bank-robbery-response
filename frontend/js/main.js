class Application {
  constructor() {
    this.renderer = new CanvasRenderer('simulationCanvas');
    this.socket = new SimulationSocket('/ws', (data) => this.handleServerMessage(data));
    this.ui = new UIPanels(this.renderer, this.socket);

    this.initControls();
    this.fetchScenarios();
    this.socket.connect();
  }

  initControls() {
    document.getElementById('btnStart').addEventListener('click', () => {
      this.socket.send({ action: 'start' });
    });

    document.getElementById('btnPause').addEventListener('click', () => {
      this.socket.send({ action: 'pause' });
    });

    document.getElementById('btnStep').addEventListener('click', () => {
      this.socket.send({ action: 'step' });
    });

    document.getElementById('btnReset').addEventListener('click', () => {
      this.resetSimulation();
    });

    document.getElementById('modalBtnRestart').addEventListener('click', () => {
      document.getElementById('outcomeModal').style.display = 'none';
      this.resetSimulation();
    });

    const speedSlider = document.getElementById('speedSlider');
    speedSlider.addEventListener('input', (e) => {
      const val = e.target.value;
      document.getElementById('speedValue').innerText = `${val}x`;
      this.socket.send({ action: 'set_speed', speed: parseFloat(val) });
    });

    document.getElementById('scenarioSelector').addEventListener('change', (e) => {
      this.selectScenario(e.target.value);
    });
  }

  async fetchScenarios() {
    try {
      const res = await fetch('/api/scenarios');
      const data = await res.json();
      this.ui.populateScenarios(data.scenarios);
    } catch (err) {
      console.error('Error fetching scenarios:', err);
    }
  }

  selectScenario(scenarioId) {
    document.getElementById('scenarioSelector').value = scenarioId;
    const seedInput = document.getElementById('seedInput').value;
    const seed = seedInput ? parseInt(seedInput, 10) : null;
    this.socket.send({ action: 'load', scenario: scenarioId, seed: seed });
  }

  resetSimulation() {
    const scenario = document.getElementById('scenarioSelector').value || 'baseline';
    const seedInput = document.getElementById('seedInput').value;
    const seed = seedInput ? parseInt(seedInput, 10) : null;
    this.socket.send({ action: 'load', scenario: scenario, seed: seed });
  }

  handleServerMessage(msg) {
    if (msg.type === 'init') {
      if (msg.seed !== undefined && msg.seed !== null) {
        document.getElementById('seedInput').placeholder = `Seed: ${msg.seed}`;
      }
      this.renderer.initMap(msg.map, msg.cctv);
      this.renderer.updateState(msg.state);
      this.ui.updateMetrics(msg.state.metrics, msg.state.tick);
      this.ui.updateStatusBadge(msg.state.metrics.outcome, msg.state.robber.phase);
      this.ui.updateAgentsList(msg.state);
      this.ui.updateMessagesLog(msg.state.recent_messages);
      document.getElementById('outcomeModal').style.display = 'none';
    } else if (msg.type === 'tick' || msg.type === 'end') {
      this.renderer.updateState(msg.state);
      this.ui.updateMetrics(msg.state.metrics, msg.state.tick);
      this.ui.updateStatusBadge(msg.state.metrics.outcome, msg.state.robber.phase);
      this.ui.updateAgentsList(msg.state);
      this.ui.updateMessagesLog(msg.state.recent_messages);

      if (msg.type === 'end') {
        this.ui.showOutcomeModal(msg.state.metrics, msg.state.robber.phase);
      }
    }
  }
}

// Global bootstrap
let app;
window.addEventListener('DOMContentLoaded', () => {
  app = new Application();
});
