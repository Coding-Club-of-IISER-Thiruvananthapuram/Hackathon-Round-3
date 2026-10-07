"""
Clash Royale Arena Game State representation.
Tracks 2-lane bridge arena, King and Princess towers, live troops,
elixir bars, crowns, and match combat logs.
"""
import uuid
from typing import Dict, List, Tuple, Any, Optional
from engine.config import (
    CARD_CATALOG, MAX_ELIXIR, STARTING_ELIXIR,
    PRINCESS_TOWER_MAX_HP, KING_TOWER_MAX_HP,
    PRINCESS_TOWER_RADIUS, KING_TOWER_RADIUS,
    LEFT_LANE_X, RIGHT_LANE_X, DEFAULT_MATCH_DURATION_SECONDS
)

class ClashTroop:
    def __init__(
        self,
        card_id: str,
        team: str,
        lane: str,
        y_pos: float,
        troop_id: Optional[str] = None,
        x_pos: Optional[float] = None
    ):
        proto = CARD_CATALOG.get(card_id, CARD_CATALOG["knight"])
        self.id = troop_id or f"{team}_{card_id}_{uuid.uuid4().hex[:5]}"
        self.card_id = card_id
        self.name = proto["name"]
        self.team = team      # "red" or "blue"
        self.lane = lane      # "left" or "right"
        self.x = x_pos if x_pos is not None else (LEFT_LANE_X if lane == "left" else RIGHT_LANE_X)
        self.y = y_pos        # 0.0 (Red side) to 100.0 (Blue side)
        
        self.hp = proto.get("hp", 800)
        self.max_hp = self.hp
        self.damage = proto.get("damage", 100)
        self.speed = proto.get("speed", 10.0)
        self.range = proto.get("range", 3.0)
        self.target_type = proto.get("target", "all")
        self.splash = proto.get("splash", False)
        self.icon = proto["icon"]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "card_id": self.card_id,
            "name": self.name,
            "team": self.team,
            "lane": self.lane,
            "x": self.x,
            "y": round(self.y, 1),
            "hp": self.hp,
            "max_hp": self.max_hp,
            "damage": self.damage,
            "speed": self.speed,
            "range": self.range,
            "target": self.target_type,
            "icon": self.icon
        }


class ClashPlayerState:
    def __init__(self, team: str, name: str, author: str):
        self.team = team  # "red" (top) or "blue" (bottom)
        self.name = name
        self.author = author
        self.elixir = STARTING_ELIXIR
        self.crowns = 0

        is_red = (team == "red")
        self.towers = {
            "king": {
                "name": "King Tower",
                "hp": KING_TOWER_MAX_HP,
                "max_hp": KING_TOWER_MAX_HP,
                "active": False,
                "x": 50.0,
                "y": 7.0 if is_red else 93.0,
                "radius": KING_TOWER_RADIUS,
                "destroyed": False
            },
            "left_princess": {
                "name": "Left Princess Tower",
                "hp": PRINCESS_TOWER_MAX_HP,
                "max_hp": PRINCESS_TOWER_MAX_HP,
                "active": True,
                "x": LEFT_LANE_X,
                "y": 22.0 if is_red else 78.0,
                "radius": PRINCESS_TOWER_RADIUS,
                "destroyed": False
            },
            "right_princess": {
                "name": "Right Princess Tower",
                "hp": PRINCESS_TOWER_MAX_HP,
                "max_hp": PRINCESS_TOWER_MAX_HP,
                "active": True,
                "x": RIGHT_LANE_X,
                "y": 22.0 if is_red else 78.0,
                "radius": PRINCESS_TOWER_RADIUS,
                "destroyed": False
            }
        }

        self.deck: List[str] = ["knight", "archers", "giant", "musketeer", "hog_rider", "skeletons", "baby_dragon", "fireball"]
        self.last_thought = "Reading opponent deck and pooling elixir."
        self.last_taunt = ""
        self.last_action = {}

        self.stats = {
            "cards_played": 0,
            "elixir_spent": 0,
            "damage_dealt": 0,
            "troops_killed": 0
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "team": self.team,
            "name": self.name,
            "author": self.author,
            "elixir": round(self.elixir, 1),
            "max_elixir": MAX_ELIXIR,
            "crowns": self.crowns,
            "towers": self.towers,
            "deck": self.deck,
            "last_thought": self.last_thought,
            "last_taunt": self.last_taunt,
            "stats": self.stats
        }


class ClashGameState:
    def __init__(self, match_id: Optional[str] = None, max_duration_seconds: int = DEFAULT_MATCH_DURATION_SECONDS):
        self.match_id = match_id or f"clash_{uuid.uuid4().hex[:8]}"
        self.round_number = 0
        self.max_duration_seconds = max_duration_seconds
        self.elapsed_seconds = 0.0
        self.status = "not_started"  # "not_started", "running", "paused", "finished"
        self.winner: Optional[str] = None
        self.win_reason: str = ""
        self.is_double_elixir = False
        self.is_overtime = False

        self.players: Dict[str, ClashPlayerState] = {
            "red": ClashPlayerState("red", "Red Kingdom", "Team Red"),
            "blue": ClashPlayerState("blue", "Blue Kingdom", "Team Blue")
        }

        self.troops: List[ClashTroop] = []
        self.combat_log: List[Dict[str, Any]] = []
        self.events: List[Dict[str, Any]] = []

    def add_combat_log(self, text: str, category: str = "combat", icon: str = "⚔️"):
        entry = {
            "round": self.round_number,
            "time": round(self.elapsed_seconds, 1),
            "category": category,
            "icon": icon,
            "text": text
        }
        self.combat_log.append(entry)
        if len(self.combat_log) > 60:
            self.combat_log = self.combat_log[-60:]

    def get_situational_brief(self, team: str) -> str:
        opp_team = "blue" if team == "red" else "red"
        me = self.players[team]
        opp = self.players[opp_team]

        my_left = me.towers["left_princess"]["hp"]
        my_right = me.towers["right_princess"]["hp"]
        my_king = me.towers["king"]["hp"]

        opp_left = opp.towers["left_princess"]["hp"]
        opp_right = opp.towers["right_princess"]["hp"]
        opp_king = opp.towers["king"]["hp"]

        my_troops = [t for t in self.troops if t.team == team]
        opp_troops = [t for t in self.troops if t.team == opp_team]

        opp_last_card = opp.last_action.get("card", "none")
        opp_last_lane = opp.last_action.get("lane", "none")
        last_deployment_line = ""
        if opp_last_card and opp_last_card != "none":
            last_deployment_line = f"\nLast Enemy Deployment: {opp_last_card} on {opp_last_lane}"

        brief = f"""CLASH ARENA BRIEF ({team.upper()}):
Time: {int(self.elapsed_seconds)}s / {self.max_duration_seconds}s {'[2X ELIXIR!]' if self.is_double_elixir else ''}
Your Elixir: {int(me.elixir)}/10 | Crowns: {me.crowns}
Your Towers: Left Princess={my_left}HP, Right Princess={my_right}HP, King={my_king}HP
Enemy Towers: Left Princess={opp_left}HP, Right Princess={opp_right}HP, King={opp_king}HP
Your Active Troops: {len(my_troops)} ({', '.join([f'{t.name} on {t.lane}' for t in my_troops[:6]]) or 'None'})
Enemy Incoming Troops: {len(opp_troops)} ({', '.join([f'{t.name} on {t.lane}' for t in opp_troops[:6]]) or 'None'}){last_deployment_line}
Available Cards in Deck: {', '.join(me.deck)}

Choose 1 card to play and lane ("left" or "right"), or "none" to save elixir!"""
        return brief.strip()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "match_id": self.match_id,
            "round_number": self.round_number,
            "max_duration_seconds": self.max_duration_seconds,
            "elapsed_seconds": round(self.elapsed_seconds, 1),
            "status": self.status,
            "winner": self.winner,
            "win_reason": self.win_reason,
            "is_double_elixir": self.is_double_elixir,
            "is_overtime": self.is_overtime,
            "players": {k: v.to_dict() for k, v in self.players.items()},
            # Keep "kingdoms" key for backwards compatibility with UI if needed
            "kingdoms": {k: v.to_dict() for k, v in self.players.items()},
            "troops": [t.to_dict() for t in self.troops],
            "units": [t.to_dict() for t in self.troops],
            "combat_log": self.combat_log[-20:],
            "events": list(self.events)
        }
