class CanvasRenderer {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas.getContext('2d');

    this.mapData = null;
    this.cctvData = null;
    this.currentState = null;
    this.previousState = null;
    this.lastTickTime = performance.now();

    // Camera viewport transform
    this.scale = 1.0;
    this.panX = 0;
    this.panY = 0;
    this.isDragging = false;
    this.dragStart = { x: 0, y: 0 };

    // Overlay visibility toggles
    this.overlays = {
      cctv: true,
      routes: true,
      predicted: true,
      intercept: true,
      belief: true,
      traffic: true,
    };

    this._initEvents();
    this._resize();
    window.addEventListener('resize', () => this._resize());
    requestAnimationFrame((t) => this.renderLoop(t));
  }

  _resize() {
    this.canvas.width = this.canvas.clientWidth * window.devicePixelRatio;
    this.canvas.height = this.canvas.clientHeight * window.devicePixelRatio;
    this.ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
    if (this.mapData) {
      this.centerMap();
    }
  }

  centerMap() {
    if (!this.mapData || !this.mapData.nodes.length) return;
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (const n of this.mapData.nodes) {
      minX = Math.min(minX, n.x);
      maxX = Math.max(maxX, n.x);
      minY = Math.min(minY, n.y);
      maxY = Math.max(maxY, n.y);
    }
    const mapW = maxX - minX + 160;
    const mapH = maxY - minY + 160;
    const viewW = this.canvas.clientWidth;
    const viewH = this.canvas.clientHeight;

    this.scale = Math.min(viewW / mapW, viewH / mapH) * 0.9;
    this.panX = (viewW - mapW * this.scale) / 2 - minX * this.scale + 80 * this.scale;
    this.panY = (viewH - mapH * this.scale) / 2 - minY * this.scale + 80 * this.scale;
  }

  _initEvents() {
    this.canvas.addEventListener('mousedown', (e) => {
      this.isDragging = true;
      this.dragStart = { x: e.clientX - this.panX, y: e.clientY - this.panY };
    });

    window.addEventListener('mousemove', (e) => {
      if (this.isDragging) {
        this.panX = e.clientX - this.dragStart.x;
        this.panY = e.clientY - this.dragStart.y;
      }
    });

    window.addEventListener('mouseup', () => {
      this.isDragging = false;
    });

    this.canvas.addEventListener('wheel', (e) => {
      e.preventDefault();
      const zoomFactor = e.deltaY < 0 ? 1.1 : 0.9;
      const mouseX = e.clientX - this.canvas.getBoundingClientRect().left;
      const mouseY = e.clientY - this.canvas.getBoundingClientRect().top;

      this.panX = mouseX - (mouseX - this.panX) * zoomFactor;
      this.panY = mouseY - (mouseY - this.panY) * zoomFactor;
      this.scale *= zoomFactor;
    });
  }

  initMap(mapData, cctvData) {
    this.mapData = mapData;
    this.cctvData = cctvData;
    this.centerMap();
  }

  updateState(newState) {
    this.previousState = this.currentState;
    this.currentState = newState;
    this.lastTickTime = performance.now();
  }

  renderLoop(timestamp) {
    this.ctx.clearRect(0, 0, this.canvas.clientWidth, this.canvas.clientHeight);

    if (this.mapData) {
      this.ctx.save();
      this.ctx.translate(this.panX, this.panY);
      this.ctx.scale(this.scale, this.scale);

      this.drawRoads();
      if (this.overlays.cctv) this.drawCCTV();
      if (this.overlays.predicted) this.drawPredictedRoutes();
      if (this.overlays.routes) this.drawPoliceRoutes();
      if (this.overlays.belief) this.drawBeliefEllipse();
      if (this.overlays.intercept) this.drawInterceptionPoints();

      this.drawNodes();
      this.drawCivilians();
      this.drawRobber();
      this.drawPolice();

      this.ctx.restore();
    }

    requestAnimationFrame((t) => this.renderLoop(t));
  }

  drawRoads() {
    const traffic = (this.currentState && this.currentState.traffic) || {};
    this.ctx.lineWidth = 4;
    this.ctx.lineCap = 'round';

    for (const edge of this.mapData.edges) {
      const u = this.mapData.nodes.find(n => n.id === edge.u);
      const v = this.mapData.nodes.find(n => n.id === edge.v);
      if (!u || !v) continue;

      const key1 = `${edge.u}-${edge.v}`;
      const key2 = `${edge.v}-${edge.u}`;
      const cong = traffic[key1] || traffic[key2] || 1.0;

      // Color coding road congestion on Light Mode canvas
      let strokeStyle = edge.is_arterial ? '#64748b' : '#94a3b8';
      if (this.overlays.traffic) {
        if (cong >= 1.3) strokeStyle = 'rgba(225, 29, 72, 0.95)'; // Vivid Crimson Red for heavy civilian traffic / rush hour gridlock
        else if (cong >= 1.15) strokeStyle = 'rgba(217, 119, 6, 0.95)'; // Amber/orange for moderate delays
        else strokeStyle = edge.is_arterial ? '#64748b' : '#94a3b8';
      }

      this.ctx.strokeStyle = strokeStyle;
      this.ctx.lineWidth = edge.is_arterial ? 6 : 3.5;
      this.ctx.beginPath();
      this.ctx.moveTo(u.x, u.y);
      this.ctx.lineTo(v.x, v.y);
      this.ctx.stroke();
    }
  }

  drawNodes() {
    for (const node of this.mapData.nodes) {
      this.ctx.beginPath();
      if (node.role === 'bank') {
        this.ctx.fillStyle = '#d97706';
        this.ctx.arc(node.x, node.y, 11, 0, Math.PI * 2);
        this.ctx.fill();
        this.ctx.strokeStyle = '#ffffff';
        this.ctx.lineWidth = 2;
        this.ctx.stroke();
        this.ctx.fillStyle = '#ffffff';
        this.ctx.font = 'bold 11px "Open Sans", sans-serif';
        this.ctx.textAlign = 'center';
        this.ctx.textBaseline = 'middle';
        this.ctx.fillText('$', node.x, node.y);
      } else if (node.role === 'exit') {
        this.ctx.fillStyle = '#e11d48';
        this.ctx.arc(node.x, node.y, 9, 0, Math.PI * 2);
        this.ctx.fill();
        this.ctx.strokeStyle = '#ffffff';
        this.ctx.lineWidth = 2;
        this.ctx.stroke();
      } else if (node.role === 'station') {
        this.ctx.fillStyle = '#2563eb';
        this.ctx.arc(node.x, node.y, 8, 0, Math.PI * 2);
        this.ctx.fill();
        this.ctx.strokeStyle = '#ffffff';
        this.ctx.lineWidth = 2;
        this.ctx.stroke();
      } else {
        this.ctx.fillStyle = '#64748b';
        this.ctx.arc(node.x, node.y, 4, 0, Math.PI * 2);
        this.ctx.fill();
      }
    }
  }

  drawCCTV() {
    if (!this.cctvData) return;
    for (const cam of this.cctvData) {
      this.ctx.beginPath();
      this.ctx.fillStyle = 'rgba(2, 132, 199, 0.07)';
      this.ctx.strokeStyle = 'rgba(2, 132, 199, 0.45)';
      this.ctx.lineWidth = 1.2;
      this.ctx.setLineDash([4, 4]);
      this.ctx.arc(cam.x, cam.y, cam.range_m, 0, Math.PI * 2);
      this.ctx.fill();
      this.ctx.stroke();
      this.ctx.setLineDash([]);
    }
  }

  drawPoliceRoutes() {
    if (!this.currentState || !this.currentState.police) return;
    this.ctx.lineWidth = 2.5;
    this.ctx.setLineDash([6, 6]);

    for (const p of this.currentState.police) {
      if (!p.route || p.route.length === 0) continue;
      this.ctx.strokeStyle = p.status === 'PURSUING' ? '#9333ea' : '#2563eb';
      this.ctx.beginPath();
      this.ctx.moveTo(p.x, p.y);
      for (const nid of p.route) {
        const node = this.mapData.nodes.find(n => n.id === nid);
        if (node) this.ctx.lineTo(node.x, node.y);
      }
      this.ctx.stroke();
    }
    this.ctx.setLineDash([]);
  }

  drawPredictedRoutes() {
    if (!this.currentState || !this.currentState.command || !this.currentState.command.predicted_routes) return;
    const routes = this.currentState.command.predicted_routes;

    for (const r of routes) {
      if (!r.path || r.path.length < 2) continue;
      this.ctx.lineWidth = Math.max(2, r.prob * 5);
      this.ctx.strokeStyle = `rgba(217, 119, 6, ${Math.max(0.4, r.prob)})`;
      this.ctx.beginPath();
      const first = this.mapData.nodes.find(n => n.id === r.path[0]);
      if (first) {
        this.ctx.moveTo(first.x, first.y);
        for (let i = 1; i < r.path.length; i++) {
          const n = this.mapData.nodes.find(node => node.id === r.path[i]);
          if (n) this.ctx.lineTo(n.x, n.y);
        }
        this.ctx.stroke();
      }
    }
  }
  drawInterceptionPoints() {
    // Roadblock / delayed interception points removed
    return;
  }


  drawBeliefEllipse() {
    if (!this.currentState || !this.currentState.command) return;
    const cmd = this.currentState.command;
    if (!cmd.estimated_pos || cmd.uncertainty_radius_m <= 0) return;

    const [ex, ey] = cmd.estimated_pos;
    this.ctx.beginPath();
    this.ctx.strokeStyle = 'rgba(225, 29, 72, 0.45)';
    this.ctx.fillStyle = 'rgba(225, 29, 72, 0.08)';
    this.ctx.lineWidth = 1.8;
    this.ctx.arc(ex, ey, cmd.uncertainty_radius_m, 0, Math.PI * 2);
    this.ctx.fill();
    this.ctx.stroke();
  }

  drawCivilians() {
    if (!this.currentState || !this.currentState.civilians) return;
    for (const [cx, cy] of this.currentState.civilians) {
      this.ctx.beginPath();
      this.ctx.fillStyle = '#475569';
      this.ctx.arc(cx, cy, 5.0, 0, Math.PI * 2);
      this.ctx.fill();

      // High-contrast white outer ring against roads
      this.ctx.strokeStyle = '#ffffff';
      this.ctx.lineWidth = 1.5;
      this.ctx.stroke();
    }
  }

  drawRobber() {
    if (!this.currentState || !this.currentState.robber) return;
    const r = this.currentState.robber;

    // Robber Visual Radar Field (vision_radius_m)
    const visionRadius = r.vision_radius_m || 160;
    this.ctx.beginPath();
    this.ctx.arc(r.x, r.y, visionRadius, 0, Math.PI * 2);
    this.ctx.strokeStyle = 'rgba(225, 29, 72, 0.35)';
    this.ctx.lineWidth = 1.5;
    this.ctx.setLineDash([5, 5]);
    this.ctx.stroke();
    this.ctx.fillStyle = 'rgba(225, 29, 72, 0.05)';
    this.ctx.fill();
    this.ctx.setLineDash([]);

    // Glowing outer threat ring
    this.ctx.beginPath();
    this.ctx.strokeStyle = 'rgba(225, 29, 72, 0.5)';
    this.ctx.lineWidth = 3;
    this.ctx.arc(r.x, r.y, 14, 0, Math.PI * 2);
    this.ctx.stroke();

    // Solid robber center
    this.ctx.beginPath();
    this.ctx.fillStyle = '#e11d48';
    this.ctx.shadowColor = 'rgba(225, 29, 72, 0.5)';
    this.ctx.shadowBlur = 10;
    this.ctx.arc(r.x, r.y, 9, 0, Math.PI * 2);
    this.ctx.fill();
    this.ctx.shadowBlur = 0;

    // Inner icon symbol
    this.ctx.fillStyle = '#ffffff';
    this.ctx.font = 'bold 10px "Open Sans", sans-serif';
    this.ctx.textAlign = 'center';
    this.ctx.textBaseline = 'middle';
    this.ctx.fillText('⚠', r.x, r.y);

    // Enlarged Text Label above robber with white halo
    this.ctx.font = 'bold 13px "Open Sans", sans-serif';
    this.ctx.strokeStyle = '#ffffff';
    this.ctx.lineWidth = 3.5;
    this.ctx.strokeText('SUSPECT', r.x, r.y - 19);
    this.ctx.fillStyle = '#b91c1c';
    this.ctx.fillText('SUSPECT', r.x, r.y - 19);
  }

  drawPolice() {
    if (!this.currentState || !this.currentState.police) return;
    for (const p of this.currentState.police) {
      const isPursuing = p.status === 'PURSUING';
      const mainColor = isPursuing ? '#9333ea' : '#0284c7';

      // Flashing siren ring
      this.ctx.beginPath();
      this.ctx.strokeStyle = mainColor;
      this.ctx.lineWidth = 2.5;
      this.ctx.arc(p.x, p.y, 14, 0, Math.PI * 2);
      this.ctx.stroke();

      // Police Car Body
      this.ctx.beginPath();
      this.ctx.fillStyle = mainColor;
      this.ctx.shadowColor = mainColor;
      this.ctx.shadowBlur = 8;
      this.ctx.arc(p.x, p.y, 8.5, 0, Math.PI * 2);
      this.ctx.fill();
      this.ctx.shadowBlur = 0;

      // Inner Star
      this.ctx.fillStyle = '#ffffff';
      this.ctx.font = 'bold 9px "Open Sans", sans-serif';
      this.ctx.textAlign = 'center';
      this.ctx.textBaseline = 'middle';
      this.ctx.fillText('★', p.x, p.y);

      // Enlarged Text Unit ID Label above police car with white halo
      this.ctx.font = 'bold 13px "Open Sans", sans-serif';
      this.ctx.strokeStyle = '#ffffff';
      this.ctx.lineWidth = 3.5;
      const shortId = p.id.replace('police_', 'P');
      const labelText = `${shortId} [${p.status}]`;
      this.ctx.strokeText(labelText, p.x, p.y - 18);
      this.ctx.fillStyle = '#0f172a';
      this.ctx.fillText(labelText, p.x, p.y - 18);
    }
  }


}
