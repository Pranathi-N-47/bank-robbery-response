# Real-Time Multi-Agent Daytime Bank Robbery Response System (23CSE401)

A multi-agent simulation for daytime urban bank robbery response, suspect tracking, and dynamic police interception. Built using **Mesa 3.5.1**, **FastAPI**, **NetworkX**, and a high-performance **HTML5 Canvas** tactical dashboard.

---

## 1. System Overview & Architecture

The system models an active daytime robbery in a graph-represented city road network. Five autonomous agents cooperate and compete:
1. **Surveillance Agent**: Monitors CCTV sensor coverage cones and silent bank alarm triggers; performs probabilistic multi-sensor confidence fusion ($1 - \prod(1 - c_i)$); emits incident alerts and suspect sightings.
2. **Command & Intelligence (C&I) Agent**: Maintains a belief state of suspect location with expanding uncertainty ellipse; predicts escape trajectories using multinomial logit models; evaluates reachable interception candidates ($t_{\text{rob}} > t_{\text{pol}} + \text{buffer}$); dispatches operational plans.
3. **Dispatch Agent**: Solves optimal multi-unit assignment via the **Hungarian algorithm** (`scipy.optimize.linear_sum_assignment`) to minimize police arrival time while dedicating an interceptor to pursuit.
4. **Patrol Agent(s)**: Navigates road network graphs using custom **$A^*$ Search** ($f = g + h$); re-evaluates trajectories when traffic congestion spikes.
5. **Robber Agent**: Operates with danger-aversion cost functions ($f_{\text{danger}} = t \cdot (1 + \lambda \sum e^{-d^2/2\sigma^2})$); dynamically reroutes when police units enter its visual perception radius.
6. **Civilian Agents**: Wandering urban traffic generators producing dynamic localized road congestion bottlenecks.

---

## 2. Quickstart & Installation

### Requirements
- Python 3.10+ (Tested on Python 3.12.6)
- Windows / macOS / Linux

### Setup

```powershell
# 1. Clone repository and enter directory
cd bank-robbery-response

# 2. Create virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt -r requirements-dev.txt
pip install -e .
```

---

## 3. Running the Tactical Web Dashboard

Start the FastAPI + WebSocket simulation server:

```powershell
python -m uvicorn brrs.server.app:app --host 127.0.0.1 --port 8000
```

Open your browser at **[http://127.0.0.1:8000](http://127.0.0.1:8000)**.

### Dashboard Features:
- **Real-Time Canvas Map**: Visualizes road networks, dynamic traffic heatmaps, CCTV camera cones, police patrol cars, robber unit, civilians, and bank/exits.
- **Visual Overlays**:
  - Predicted Escape Routes & Probabilities
  - Candidate Interception Points & Time Margins
  - Command Uncertainty Belief Ellipse
  - Police $A^*$ Planned Paths
- **Playback Controls**: Start, Pause, Single-Step, Reset, and Live Speed Slider (1x–20x).
- **Inspector Tabs**: Live PEAS Performance Metrics, Agent State Cards, Inter-Agent Message Log, and Scenario Selector.

---

## 4. Predefined Testing Scenarios

Scenarios are defined in pure YAML in the `scenarios/` directory:
- `baseline.yaml`: Standard balanced conditions with 4 police units, 6 CCTV cameras, and 20 civilians.
- `rush_hour.yaml`: Severe downtown traffic congestion bottlenecks and spontaneous traffic jams.
- `blind_spots.yaml`: Sparse CCTV placement and delayed bank alarm, forcing deep belief dead-reckoning.
- `outnumbered.yaml`: Only 2 police patrol units attempting perimeter containment across 4 exits.
- `fast_getaway.yaml`: Robber equipped with high-speed vehicle testing rapid police replanning.
- `large_city.yaml`: Scaled metropolis ($10 \times 10$ grid, 8 police units, 14 CCTV cameras, 2 surveillance zones, 60 civilians) demonstrating architectural scalability.

---

## 5. Running Automated Tests & Experiments

### Unit & Integration Test Suite:
```powershell
pytest -v
```
Verifies custom $A^*$ path optimality against Dijkstra, physical capture collision logic, publish-subscribe message routing, and scenario termination.

### Headless Batch Evaluation:
```powershell
python -m brrs.experiments.batch_runner --runs 15 --output results
```
Executes Monte Carlo batches across all scenarios, outputting:
- `results/batch_results.csv`: Per-run metrics.
- `results/scenario_summary.csv`: Aggregated scenario performance.
- `results/experiment_analysis.png`: Multi-panel comparative charts (Success Rate, Replannings, Detection/Response Times, Travel Distance).

---

## 6. Project Structure

```
bank-robbery-response/
├── pyproject.toml              # Build & package configuration
├── requirements.txt            # Runtime dependencies
├── requirements-dev.txt        # Testing dependencies
├── scenarios/                  # YAML scenario definitions
├── src/brrs/
│   ├── config.py               # Pydantic scenario schemas
│   ├── scenario_loader.py      # Scenario file loader
│   ├── core/                   # Mesa model, message bus, metrics, capture logic
│   ├── environment/            # Road network graph, dynamic traffic, CCTV, movement
│   ├── algorithms/             # Custom A*, cost heuristics, escape prediction, Hungarian assignment
│   ├── agents/                 # 5 autonomous agents + civilians
│   ├── server/                 # FastAPI and WebSocket runner
│   └── experiments/            # Batch evaluator & Matplotlib charting
├── frontend/                   # Tactical HTML5 Canvas dashboard & CSS
├── tests/                      # Pytest test suite
└── results/                    # Batch CSV results and figures
```
