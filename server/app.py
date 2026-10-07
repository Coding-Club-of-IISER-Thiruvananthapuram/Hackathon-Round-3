"""
FastAPI Server for Clash Royale Autonomous 1v1 Arena & Tournament Engine.
Provides REST APIs for real-time match orchestration, card validation, and 1v1 knockout brackets.
"""
import os
import json
import asyncio
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from engine.config import DEFAULT_MATCH_DURATION_SECONDS, DEFAULT_MODEL, OLLAMA_BASE_URL, CARD_CATALOG
from engine.skill_loader import (
    list_available_kingdom_skills, load_kingdom_skill_file,
    validate_kingdom_skill_content, parse_kingdom_skill
)
from engine.match_orchestrator import MatchOrchestrator

app = FastAPI(title="Clash Royale Autonomous Arena", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = MatchOrchestrator(model_name=DEFAULT_MODEL, base_url=OLLAMA_BASE_URL)
spectator_sockets: List[WebSocket] = []

async def ws_broadcast(payload: Dict[str, Any]):
    message_text = json.dumps(payload)
    disconnected = []
    for ws in spectator_sockets:
        try:
            await ws.send_text(message_text)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        if ws in spectator_sockets:
            spectator_sockets.remove(ws)

orchestrator.register_listener(ws_broadcast)

# Request Models
class MatchSetupRequest(BaseModel):
    red_skill_file: str
    blue_skill_file: str
    max_duration_seconds: int = DEFAULT_MATCH_DURATION_SECONDS
    tournament_match_id: Optional[str] = None

class MatchCustomSetupRequest(BaseModel):
    red_skill_content: str
    blue_skill_content: str
    max_duration_seconds: int = DEFAULT_MATCH_DURATION_SECONDS

class SpeedRequest(BaseModel):
    speed: float

class SkillValidateRequest(BaseModel):
    content: str

class SkillSaveRequest(BaseModel):
    filename: str
    content: str

class TournamentCreateRequest(BaseModel):
    participant_files: List[str]

class TournamentLaunchMatchRequest(BaseModel):
    match_id: str

class TournamentImportRequest(BaseModel):
    tournament_data: Dict[str, Any]

class RolloutSimRequest(BaseModel):
    red_skill_file: Optional[str] = None
    blue_skill_file: Optional[str] = None
    red_skill_content: Optional[str] = None
    blue_skill_content: Optional[str] = None
    num_simulations: int = 10
    max_duration_seconds: int = DEFAULT_MATCH_DURATION_SECONDS


# REST Endpoints
@app.get("/api/cards")
def get_cards():
    return CARD_CATALOG

@app.get("/api/skills")
def get_skills():
    return list_available_kingdom_skills("skills")

@app.post("/api/skills/validate")
def validate_skill(req: SkillValidateRequest):
    return validate_kingdom_skill_content(req.content)

@app.post("/api/skills/save")
def save_skill(req: SkillSaveRequest):
    clean_name = os.path.basename(req.filename)
    if not clean_name.endswith(".md"):
        clean_name += ".md"
    filepath = os.path.join("skills", clean_name)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(req.content)
    validation = validate_kingdom_skill_content(req.content)
    return {
        "status": "saved",
        "filename": clean_name,
        "filepath": filepath,
        "validation": validation,
        "profile": validation.get("profile")
    }

@app.post("/api/skills/upload")
async def upload_skill(file: UploadFile = File(...)):
    filename = os.path.basename(file.filename)
    if not (filename.endswith(".md") or filename.endswith(".txt")):
        filename += ".md"
    elif filename.endswith(".txt"):
        filename = filename[:-4] + ".md"
        
    content_bytes = await file.read()
    content = content_bytes.decode("utf-8", errors="replace")
    
    filepath = os.path.join("skills", filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
        
    validation = validate_kingdom_skill_content(content)
    return {
        "status": "uploaded",
        "filename": filename,
        "validation": validation,
        "profile": validation.get("profile")
    }

@app.get("/api/skills/{filename}")
def get_skill_detail(filename: str):
    clean_name = os.path.basename(filename)
    filepath = os.path.join("skills", clean_name)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Skill file not found")
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    profile = parse_kingdom_skill(content)
    return {
        "filename": clean_name,
        "content": content,
        "profile": profile.to_dict()
    }

@app.get("/api/match/state")
def get_match_state():
    if not orchestrator.state:
        return {"status": "not_initialized"}
    payload = orchestrator.state.to_dict()
    payload["speed_multiplier"] = orchestrator.speed_multiplier
    payload["is_paused"] = orchestrator.is_paused
    payload["tournament"] = orchestrator.tournament.to_dict()
    payload["active_match_id"] = orchestrator.active_tournament_match_id
    return payload

@app.post("/api/match/setup")
async def setup_match(req: MatchSetupRequest):
    red_path = os.path.join("skills", os.path.basename(req.red_skill_file))
    blue_path = os.path.join("skills", os.path.basename(req.blue_skill_file))
    if not os.path.exists(red_path):
        raise HTTPException(status_code=400, detail=f"Red skill file not found: {red_path}")
    if not os.path.exists(blue_path):
        raise HTTPException(status_code=400, detail=f"Blue skill file not found: {blue_path}")

    orchestrator.setup_match(
        red_path,
        blue_path,
        max_duration_seconds=req.max_duration_seconds,
        is_raw_content=False,
        tournament_match_id=req.tournament_match_id
    )
    await orchestrator.broadcast_state()
    return {"status": "initialized", "state": orchestrator.state.to_dict()}

@app.post("/api/match/setup_custom")
async def setup_custom_match(req: MatchCustomSetupRequest):
    orchestrator.setup_match(
        req.red_skill_content,
        req.blue_skill_content,
        max_duration_seconds=req.max_duration_seconds,
        is_raw_content=True
    )
    await orchestrator.broadcast_state()
    return {"status": "initialized", "state": orchestrator.state.to_dict()}

@app.post("/api/match/start")
async def start_match():
    if not orchestrator.state:
        raise HTTPException(status_code=400, detail="Match not initialized.")
    await orchestrator.start_match()
    return {"status": "started"}

@app.post("/api/match/pause")
async def pause_match():
    orchestrator.pause_match()
    await orchestrator.broadcast_state()
    return {"status": "paused"}

@app.post("/api/match/resume")
async def resume_match():
    orchestrator.resume_match()
    await orchestrator.broadcast_state()
    return {"status": "resumed"}

@app.post("/api/match/step")
async def step_turn():
    await orchestrator.step_turn()
    return {"status": "stepped", "state": orchestrator.state.to_dict() if orchestrator.state else None}

@app.post("/api/match/speed")
async def set_speed(req: SpeedRequest):
    orchestrator.set_speed(req.speed)
    await orchestrator.broadcast_state()
    return {"status": "speed_updated", "speed": orchestrator.speed_multiplier}

@app.post("/api/match/reset")
async def reset_match():
    orchestrator.reset_match()
    await orchestrator.broadcast_state()
    return {"status": "reset", "state": orchestrator.state.to_dict() if orchestrator.state else None}

# Tournament Endpoints
@app.post("/api/tournament/create")
async def create_tournament(req: TournamentCreateRequest):
    bracket = orchestrator.tournament.create_knockout_bracket(req.participant_files)
    await orchestrator.broadcast_state()
    return {"status": "tournament_created", "tournament": bracket}

@app.get("/api/tournament/state")
def get_tournament_state():
    return orchestrator.tournament.to_dict()

@app.post("/api/tournament/launch_match")
async def launch_tournament_match(req: TournamentLaunchMatchRequest):
    match_id = req.match_id
    if match_id not in orchestrator.tournament.matches:
        raise HTTPException(status_code=404, detail="Tournament match not found")

    m = orchestrator.tournament.matches[match_id]
    if not m.team_a_file or not m.team_b_file:
        raise HTTPException(status_code=400, detail="Match combatants not determined yet")

    red_path = os.path.join("skills", os.path.basename(m.team_a_file))
    blue_path = os.path.join("skills", os.path.basename(m.team_b_file))

    orchestrator.setup_match(
        red_path,
        blue_path,
        max_duration_seconds=DEFAULT_MATCH_DURATION_SECONDS,
        tournament_match_id=match_id
    )
    m.status = "in_progress"
    await orchestrator.broadcast_state()
    return {"status": "match_loaded", "match_id": match_id, "state": orchestrator.state.to_dict()}

@app.get("/api/tournament/export")
def export_tournament():
    return orchestrator.tournament.to_dict()

@app.get("/health")
@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "arena": "ready" if orchestrator.state else "uninitialized",
        "match_status": orchestrator.state.status if orchestrator.state else "none",
        "tournament_matches": len(orchestrator.tournament.matches),
        "spectators": len(spectator_sockets)
    }

@app.post("/api/tournament/import")
async def import_tournament(req: TournamentImportRequest):
    orchestrator.tournament.import_from_dict(req.tournament_data)
    await orchestrator.broadcast_state()
    return {"status": "tournament_imported", "tournament": orchestrator.tournament.to_dict()}

@app.post("/api/simulate_rollout")
def simulate_rollout(req: RolloutSimRequest):
    """Fast-forward Monte Carlo simulator for AI deck evaluation & strategy testing."""
    if req.red_skill_content and req.blue_skill_content:
        red_profile = parse_kingdom_skill(req.red_skill_content)
        blue_profile = parse_kingdom_skill(req.blue_skill_content)
    else:
        red_path = os.path.join("skills", os.path.basename(req.red_skill_file or "hog_cycle.md"))
        blue_path = os.path.join("skills", os.path.basename(req.blue_skill_file or "giant_beatdown.md"))
        if not os.path.exists(red_path) or not os.path.exists(blue_path):
            raise HTTPException(status_code=400, detail="Skill files not found for rollout simulation")
        red_profile = load_kingdom_skill_file(red_path)
        blue_profile = load_kingdom_skill_file(blue_path)

    from engine.battle_simulator import ClashBattleSimulator
    from engine.game_state import ClashGameState

    num_sims = max(1, min(100, req.num_simulations))
    results = {"num_simulations": num_sims, "red_wins": 0, "blue_wins": 0, "draws": 0, "total_duration": 0.0, "matches": []}

    from engine.llm_commander import LLMCommander
    commander = LLMCommander()

    for i in range(num_sims):
        sim_state = ClashGameState(max_duration_seconds=req.max_duration_seconds)
        sim_state.players["red"].name = red_profile.name
        sim_state.players["red"].deck = red_profile.deck
        sim_state.players["blue"].name = blue_profile.name
        sim_state.players["blue"].deck = blue_profile.deck

        simulator = ClashBattleSimulator(sim_state)
        sim_state.status = "running"

        while sim_state.status == "running" and sim_state.elapsed_seconds < req.max_duration_seconds:
            red_brief = sim_state.get_situational_brief("red")
            blue_brief = sim_state.get_situational_brief("blue")
            red_order = commander._tactical_heuristics(red_profile, red_brief)
            blue_order = commander._tactical_heuristics(blue_profile, blue_brief)
            simulator.execute_round(red_order, blue_order, round_delta_seconds=1.0)

        winner = sim_state.winner
        if winner == "red":
            results["red_wins"] += 1
        elif winner == "blue":
            results["blue_wins"] += 1
        else:
            results["draws"] += 1
        results["total_duration"] += sim_state.elapsed_seconds
        results["matches"].append({
            "sim_id": i + 1,
            "winner": winner,
            "elapsed_seconds": sim_state.elapsed_seconds,
            "red_crowns": sim_state.players["red"].crowns,
            "blue_crowns": sim_state.players["blue"].crowns
        })

    results["avg_duration_seconds"] = round(results["total_duration"] / num_sims, 2)
    results["win_rate_red"] = round(results["red_wins"] / num_sims, 2)
    results["win_rate_blue"] = round(results["blue_wins"] / num_sims, 2)
    return results

# WebSocket Endpoint
@app.websocket("/ws/arena")
async def arena_websocket(websocket: WebSocket):
    await websocket.accept()
    spectator_sockets.append(websocket)
    try:
        if orchestrator.state:
            payload = orchestrator.state.to_dict()
            payload["speed_multiplier"] = orchestrator.speed_multiplier
            payload["is_paused"] = orchestrator.is_paused
            payload["tournament"] = orchestrator.tournament.to_dict()
            payload["active_match_id"] = orchestrator.active_tournament_match_id
            await websocket.send_text(json.dumps(payload))
        while True:
            msg = await websocket.receive_text()
            try:
                data = json.loads(msg)
                action = data.get("action")
                if action == "ping":
                    await websocket.send_text(json.dumps({"action": "pong"}))
                elif action == "pause":
                    orchestrator.pause_match()
                    await orchestrator.broadcast_state()
                elif action == "resume":
                    orchestrator.resume_match()
                    await orchestrator.broadcast_state()
                elif action == "step":
                    await orchestrator.step_turn()
                elif action == "speed":
                    new_speed = float(data.get("speed", 1.0))
                    orchestrator.set_speed(new_speed)
                    await orchestrator.broadcast_state()
                elif action == "reset":
                    orchestrator.reset_match()
                    await orchestrator.broadcast_state()
            except Exception:
                pass
    except WebSocketDisconnect:
        if websocket in spectator_sockets:
            spectator_sockets.remove(websocket)

# Static file mount
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.api_route("/", methods=["GET", "HEAD"])
def serve_index():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Clash Royale Autonomous Arena</h1>")
