class UIPanels {
  constructor(renderer, socket) {
    this.renderer = renderer;
    this.socket = socket;
    this.setupTabs();
    this.setupOverlays();
  }

  setupTabs() {
    const btns = document.querySelectorAll('.tab-btn');
    btns.forEach(btn => {
      btn.addEventListener('click', () => {
        btns.forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        btn.classList.add('active');
        const targetTab = document.getElementById(btn.dataset.tab);
        if (targetTab) targetTab.classList.add('active');
      });
    });
  }

  setupOverlays() {
    const chips = document.querySelectorAll('.toggle-chip');
    chips.forEach(chip => {
      chip.addEventListener('click', () => {
        const overlayName = chip.dataset.overlay;
        chip.classList.toggle('active');
        this.renderer.overlays[overlayName] = chip.classList.contains('active');
      });
    });
  }

  updateMetrics(metrics, tick) {
    document.getElementById('metricTick').innerText = tick;
    if (metrics.detection_time_ticks >= 0) {
      document.getElementById('metricDetTime').innerHTML = `${metrics.detection_time_ticks} <span class="metric-unit">ticks</span>`;
    } else {
      document.getElementById('metricDetTime').innerHTML = `-- <span class="metric-unit">ticks</span>`;
    }
    
    if (metrics.response_time_ticks >= 0) {
      document.getElementById('metricRespTime').innerHTML = `${metrics.response_time_ticks} <span class="metric-unit">ticks</span>`;
    } else {
      document.getElementById('metricRespTime').innerHTML = `<span style="font-size: 13px; color: var(--text-secondary);">En route</span>`;
    }
    document.getElementById('metricReplans').innerText = metrics.total_route_replannings || 0;
    document.getElementById('metricPoliceDist').innerHTML = `${Math.round(metrics.total_police_travel_distance_m || 0)} <span class="metric-unit">m</span>`;
    document.getElementById('metricRobberDist').innerHTML = `${Math.round(metrics.total_robber_travel_distance_m || 0)} <span class="metric-unit">m</span>`;

    const reasons = metrics.replans_by_reason || {};
    document.getElementById('replanBreakdown').innerText = 
      `Destination updates: ${reasons.destination || 0} | Traffic spikes: ${reasons.traffic || 0} | Pursuit: ${reasons.pursuit || 0}`;
  }

  updateStatusBadge(outcome, robberPhase) {
    const badge = document.getElementById('simStatusBadge');
    badge.className = 'status-badge';

    if (outcome === 'INTERCEPTED') {
      badge.classList.add('status-intercepted');
      badge.innerText = 'INTERCEPTED';
    } else if (outcome === 'ESCAPED') {
      badge.classList.add('status-escaped');
      badge.innerText = 'ESCAPED';
    } else if (robberPhase === 'FLEEING') {
      badge.classList.add('status-detected');
      badge.innerText = 'PURSUIT ACTIVE';
    } else {
      badge.classList.add('status-undetected');
      badge.innerText = 'UNDETECTED';
    }
  }

  updateAgentsList(state) {
    const container = document.getElementById('agentsListContainer');
    let html = '';

    // 1. Robber Agent
    if (state.robber) {
      html += `
        <div class="agent-card robber">
          <div class="agent-header">
            <span class="agent-title">⚠ Robber Agent</span>
            <span class="agent-state-pill" style="color: #e11d48; border-color: #fca5a5; background: #fff1f2;">${state.robber.phase}</span>
          </div>
          <div style="font-size: 11.5px; color: #64748b; margin-bottom: 5px;"><strong>Role:</strong> Escape Road Network & Evade Police Units</div>
          <div class="agent-meta-row">
            <span>Target Exit: ${state.robber.target_exit !== null ? 'Exit ' + state.robber.target_exit : 'Planning'}</span>
            <span>Visible Police: ${state.robber.visible_police}</span>
          </div>
          <div class="agent-meta-row">
            <span>Vision Radar: ${state.robber.vision_radius_m || 160}m</span>
            <span>Threat Trigger: ${state.robber.threat_radius_m || 140}m</span>
          </div>
          <div class="agent-meta-row">
            <span>A* Route Length: ${state.robber.route ? state.robber.route.length : 0} nodes</span>
            <span>Coord: (${state.robber.x}, ${state.robber.y})</span>
          </div>
        </div>
      `;
    }

    // 2. Command & Intelligence Agent
    if (state.command) {
      const activePts = (state.command.interception_points || []).map(p => `Node ${p.point}`).join(', ');
      html += `
        <div class="agent-card command">
          <div class="agent-header">
            <span class="agent-title">🧠 Command & Intelligence Agent</span>
            <span class="agent-state-pill" style="color: #0284c7; border-color: #bae6fd; background: #f0f9ff;">OPERATIONAL</span>
          </div>
          <div style="font-size: 11.5px; color: #64748b; margin-bottom: 5px;"><strong>Role:</strong> Multi-sensor Fusion, Route Prediction & Interception Planning</div>
          <div class="agent-meta-row">
            <span>Belief Node: ${state.command.estimated_node !== null ? state.command.estimated_node : 'Awaiting Sighting'}</span>
            <span>Uncertainty: ±${state.command.uncertainty_radius_m}m</span>
          </div>
          <div class="agent-meta-row">
            <span>Predicted Routes: ${state.command.predicted_routes ? state.command.predicted_routes.length : 0}</span>
            <span>Intercept Targets: [${activePts || 'None'}]</span>
          </div>
        </div>
      `;
    }

    // 3. Dispatch Agent
    if (state.dispatch) {
      html += `
        <div class="agent-card" style="border-left: 4px solid #d97706;">
          <div class="agent-header">
            <span class="agent-title">📋 Dispatch Agent</span>
            <span class="agent-state-pill" style="color: #d97706; border-color: #fde68a; background: #fffbeb;">ACTIVE</span>
          </div>
          <div style="font-size: 11.5px; color: #64748b; margin-bottom: 5px;"><strong>Role:</strong> Hungarian Algorithm Assignment & Tactical Pursuit Allocation</div>
          <div class="agent-meta-row">
            <span>Active Plan: v${state.dispatch.plan_version}</span>
            <span>Units Under Command: ${state.dispatch.managed_units || (state.police ? state.police.length : 0)}</span>
          </div>
        </div>
      `;
    }

    // 4. Surveillance Agent(s)
    if (state.surveillance) {
      for (const s of state.surveillance) {
        html += `
          <div class="agent-card" style="border-left: 4px solid #7c3aed;">
            <div class="agent-header">
              <span class="agent-title">📹 Surveillance Agent (Zone ${s.zone_id})</span>
              <span class="agent-state-pill" style="color: #7c3aed; border-color: #ddd6fe; background: #f5f3ff;">${s.incident_detected ? 'INCIDENT VERIFIED' : 'MONITORING'}</span>
            </div>
            <div style="font-size: 11.5px; color: #64748b; margin-bottom: 5px;"><strong>Role:</strong> CCTV Sensing Cones & Silent Alarm Detection</div>
            <div class="agent-meta-row">
              <span>Alarm Status: ${s.alarm_fired ? 'FIRED' : 'ARMED'}</span>
              <span>Last Sighting: ${s.last_sighting_tick !== null ? 'T+' + s.last_sighting_tick + 's' : 'None'}</span>
            </div>
          </div>
        `;
      }
    }

    // 5. Police Patrol Units
    if (state.police) {
      for (const p of state.police) {
        const isPursuing = p.status === 'PURSUING';
        const statusColor = isPursuing ? '#9333ea' : (p.status === 'HOLDING' ? '#16a34a' : '#0284c7');
        const pillBg = isPursuing ? '#faf5ff' : (p.status === 'HOLDING' ? '#f0fdf4' : '#f0f9ff');
        const pillBorder = isPursuing ? '#e9d5ff' : (p.status === 'HOLDING' ? '#bbf7d0' : '#bae6fd');
        html += `
          <div class="agent-card police" style="border-left-color: ${statusColor};">
            <div class="agent-header">
              <span class="agent-title">★ Patrol Unit ${p.id.replace('police_', 'P')}</span>
              <span class="agent-state-pill" style="color: ${statusColor}; border-color: ${pillBorder}; background: ${pillBg};">${p.status}</span>
            </div>
            <div style="font-size: 11.5px; color: #64748b; margin-bottom: 5px;"><strong>Role:</strong> A* Tactical Navigation & Roadblock Interception</div>
            <div class="agent-meta-row">
              <span>Target Node: ${p.destination !== null ? p.destination : 'Holding'}</span>
              <span>A* Path Left: ${p.route ? p.route.length : 0} nodes</span>
            </div>
            <div class="agent-meta-row">
              <span>Dynamic Replans: ${p.replans}</span>
              <span>Distance: ${Math.round(p.distance_m)}m</span>
            </div>
          </div>
        `;
      }
    }

    container.innerHTML = html;
  }

  formatMessageText(m) {
    const p = m.payload || {};
    switch (m.type) {
      case 'INCIDENT_ALERT':
        return `🚨 <strong style="color: #ff3366;">ACTIVE ROBBERY DETECTED</strong> via ${p.source === 'bank_alarm' ? 'Silent Bank Alarm' : 'CCTV Sensor Network'} (Confidence: ${Math.round((p.confidence || 1) * 100)}%) at Node ${p.location_node}.`;
      case 'ROBBER_SIGHTING':
        return `📹 <strong>CCTV Visual Contact</strong> at Node ${p.nearest_node} (Confidence: ${Math.round((p.confidence || 0) * 100)}%). Suspect tracked fleeing.`;
      case 'INTERCEPT_PLAN':
        const points = (p.interception_points || []).map(pt => `Node ${pt.point} (+${Math.round(pt.robber_eta_s || 0)}s)`).join(', ');
        return `🧠 <strong>Interception Plan v${p.version}</strong> issued. Target choke-points: [${points || 'Perimeter'}]. Pursuit requested at Node ${p.pursuit_target_node}.`;
      case 'ASSIGNMENT':
        if (p.mode === 'PURSUE') {
          return `🎯 <strong>Order: TACTICAL PURSUIT</strong> ➔ Rush to suspect last-seen location Node ${p.destination}.`;
        }
        return `🚔 <strong>Order: INTERCEPT & BLOCK</strong> ➔ Establish roadblock at Node ${p.destination}.`;
      case 'ROUTE_PLANNED':
        return `🗺️ Planned A* route: ${p.route ? p.route.length : 0} nodes (ETA: ${Math.round(p.eta_s || 0)}s, Search expanded: ${p.nodes_expanded} nodes, Trigger: ${p.reason}).`;
      case 'POSITION_UPDATE':
        return `📍 Unit location: Node ${p.node} [${p.status}] ➔ Heading: Node ${p.destination || 'Hold'}`;
      case 'ARRIVED':
        return `🛑 <strong>ROADBLOCK ESTABLISHED</strong> at Node ${p.node}. Holding position.`;
      case 'RECALL':
        return `↩️ Unit recalled back to station.`;
      case 'INCIDENT_CLOSED':
        return `🏁 <strong>MISSION CONCLUDED</strong>: Outcome = ${p.outcome}. ${p.reason ? '(' + p.reason + ')' : ''}`;
      default:
        return JSON.stringify(p);
    }
  }

  updateMessagesLog(messages) {
    if (!messages) return;
    const container = document.getElementById('messageLogContainer');
    container.innerHTML = messages.map(m => {
      let badgeColor = '#0284c7';
      if (m.type === 'INCIDENT_ALERT' || m.type === 'INCIDENT_CLOSED') badgeColor = '#e11d48';
      else if (m.type === 'ASSIGNMENT') badgeColor = '#d97706';
      else if (m.type === 'ARRIVED') badgeColor = '#16a34a';

      const readableSender = m.sender.replace('police_', 'Officer P').replace('command_intel', 'HQ Command').replace('dispatch', 'Dispatch').replace('surveillance_z1', 'CCTV Monitor');
      const readableTarget = (m.recipient || m.topic).replace('role:', 'All ').replace('police_', 'Officer P').replace('command', 'HQ Command').replace('dispatch', 'Dispatch');

      return `
        <div class="msg-item" style="border-left: 3px solid ${badgeColor}; padding: 8px 10px;">
          <div class="msg-header">
            <span class="msg-type" style="color: ${badgeColor};">${m.type}</span>
            <span>T+${m.tick}s</span>
          </div>
          <div style="font-size: 10px; color: var(--text-secondary); margin-bottom: 4px;">
            <strong>${readableSender}</strong> ➔ <em>${readableTarget}</em>
          </div>
          <div class="msg-body" style="font-size: 11px; line-height: 1.4;">${this.formatMessageText(m)}</div>
        </div>
      `;
    }).join('');
  }

  populateScenarios(scenarios) {
    const sel = document.getElementById('scenarioSelector');
    sel.innerHTML = scenarios.map(s => `
      <option value="${s.id}">${s.name}</option>
    `).join('');

    const cardsContainer = document.getElementById('scenarioCardsContainer');
    cardsContainer.innerHTML = scenarios.map(s => `
      <div class="agent-card" style="cursor: pointer;" onclick="app.selectScenario('${s.id}')">
        <div class="agent-header">
          <strong style="color: var(--accent-cyan); font-size: 13px;">${s.name}</strong>
        </div>
        <p style="font-size: 11px; color: var(--text-secondary); margin-bottom: 6px;">${s.description}</p>
        <div style="font-size: 10px; color: var(--text-secondary);">
          Police: ${s.police_count} | CCTV: ${s.cctv_count} | Civilians: ${s.civilians}
        </div>
      </div>
    `).join('');
  }

  showOutcomeModal(metrics, robberPhase) {
    const modal = document.getElementById('outcomeModal');
    const title = document.getElementById('modalOutcomeTitle');
    const desc = document.getElementById('modalOutcomeDesc');
    const summary = document.getElementById('modalMetricsSummary');

    if (metrics.outcome === 'INTERCEPTED') {
      title.innerText = 'ROBBERY INTERCEPTED!';
      title.style.color = '#3fb950';
      desc.innerText = `Suspect was successfully neutralized by ${metrics.intercepting_unit || 'police response unit'}.`;
    } else if (metrics.outcome === 'ESCAPED') {
      title.innerText = 'ROBBER ESCAPED!';
      title.style.color = '#ff3366';
      desc.innerText = 'The suspect managed to slip through the perimeter to a designated city highway exit.';
    } else {
      title.innerText = 'SIMULATION TIMEOUT';
      title.style.color = '#e3b341';
      desc.innerText = 'Maximum simulation duration reached.';
    }

    const respTimeStr = metrics.response_time_ticks >= 0 ? `${metrics.response_time_ticks} ticks` : 'N/A (Escaped before arrival)';
    summary.innerHTML = `
      <div><strong>Detection Time:</strong> ${metrics.detection_time_ticks >= 0 ? metrics.detection_time_ticks + ' ticks' : 'Undetected'}</div>
      <div><strong>Response Time:</strong> ${respTimeStr}</div>
      <div><strong>Police Distance Traveled:</strong> ${metrics.total_police_travel_distance_m} m</div>
      <div><strong>Route Replannings:</strong> ${metrics.total_route_replannings}</div>
      <div><strong>Total Messages Exchanged:</strong> ${metrics.total_messages}</div>
    `;

    modal.style.display = 'flex';
  }
}
