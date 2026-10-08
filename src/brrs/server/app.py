from __future__ import annotations
import os
import json
import asyncio
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from brrs.server.runner import SimulationRunner
from brrs.scenario_loader import load_scenario


app = FastAPI(title="Bank Robbery Response Multi-Agent Simulation")

# Global connected WebSockets
connected_clients: set[WebSocket] = set()

async def broadcast_message(data: dict) -> None:
    """Send JSON message to all active WebSocket clients."""
    disconnected = set()
    for ws in connected_clients:
        try:
            await ws.send_json(data)
        except Exception:
            disconnected.add(ws)
    for ws in disconnected:
        connected_clients.remove(ws)

runner = SimulationRunner(broadcast_callback=broadcast_message)


@app.get("/api/scenarios")
async def list_scenarios():
    """Returns all available YAML scenarios with their metadata."""
    scenarios_dir = Path("scenarios")
    items = []
    if scenarios_dir.exists():
        for file in sorted(scenarios_dir.glob("*.yaml")):
            try:
                cfg = load_scenario(file)
                items.append({
                    "id": file.stem,
                    "name": cfg.name,
                    "description": cfg.description,
                    "seed": cfg.seed,
                    "police_count": cfg.police.count,
                    "cctv_count": cfg.cctv.count,
                    "civilians": cfg.civilians.count,
                })
            except Exception as e:
                pass
    return {"scenarios": items}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    try:
        # On connection, send initial state if loaded, or load default baseline
        if runner.model is None:
            init_data = runner.load("baseline")
        else:
            init_data = {
                "type": "init",
                "scenario": runner.scenario_name,
                "seed": runner.current_config.seed if runner.current_config else None,
                "map": runner.model.city_map.to_dict(),
                "cctv": runner.model.cctv_network.to_dict(),
                "state": runner.model.snapshot(),
            }
        await websocket.send_json(init_data)

        while True:
            raw_text = await websocket.receive_text()
            cmd_data = json.loads(raw_text)
            action = cmd_data.get("action")

            if action == "load":
                sc_name = cmd_data.get("scenario", "baseline")
                seed_val = cmd_data.get("seed")
                init_pkg = runner.load(sc_name, seed=seed_val)
                await broadcast_message(init_pkg)

            elif action == "start":
                runner.start()

            elif action == "pause":
                runner.pause()

            elif action == "step":
                runner.pause()
                tick_pkg = runner.step()
                if tick_pkg:
                    await broadcast_message(tick_pkg)

            elif action == "reset":
                seed_val = cmd_data.get("seed")
                init_pkg = runner.load(runner.scenario_name, seed=seed_val)
                await broadcast_message(init_pkg)

            elif action == "set_speed":
                tps = cmd_data.get("speed", 4.0)
                runner.set_speed(tps)

            elif action == "trigger_jam":
                u = cmd_data.get("u")
                v = cmd_data.get("v")
                if runner.model and u is not None and v is not None:
                    runner.model.traffic_model.trigger_jam(int(u), int(v), duration_ticks=40, severity=2.5)

    except WebSocketDisconnect:
        connected_clients.discard(websocket)
    except Exception:
        connected_clients.discard(websocket)


# Mount static frontend assets
frontend_dir = Path("frontend")
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory="frontend"), name="static")

    @app.get("/")
    async def serve_index():
        return FileResponse(frontend_dir / "index.html")
