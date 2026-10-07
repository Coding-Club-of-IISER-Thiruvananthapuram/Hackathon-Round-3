"""
Clash Royale Arena Battle Simulator.
Resolves lane-based troop movement, Princess and King tower targeting,
elixir regeneration, spell strikes, crown achievements, 3-Crown KO finishes,
and high-frequency animation & particle event dispatching.
"""
import math
from typing import Dict, Any, List
from engine.config import (
    CARD_CATALOG, MAX_ELIXIR, NORMAL_ELIXIR_RATE, DOUBLE_ELIXIR_RATE,
    DOUBLE_ELIXIR_THRESHOLD_SECONDS, PRINCESS_TOWER_DAMAGE, KING_TOWER_DAMAGE,
    PRINCESS_TOWER_RANGE, KING_TOWER_RANGE, PRINCESS_TOWER_RADIUS, KING_TOWER_RADIUS,
    LEFT_LANE_X, RIGHT_LANE_X
)
from engine.game_state import ClashGameState, ClashTroop

class SpatialGrid:
    """2D Spatial Hash Grid dividing pitch into buckets for O(1) spatial target queries."""
    def __init__(self, cell_size: float = 10.0):
        self.cell_size = cell_size
        self.grid: Dict[tuple, List[ClashTroop]] = {}

    def clear(self):
        self.grid.clear()

    def insert(self, troop: ClashTroop):
        cx = int(troop.x // self.cell_size)
        cy = int(troop.y // self.cell_size)
        cell = (cx, cy)
        if cell not in self.grid:
            self.grid[cell] = []
        self.grid[cell].append(troop)

    def query_nearby(self, x: float, y: float, radius: float) -> List[ClashTroop]:
        min_cx = int((x - radius) // self.cell_size)
        max_cx = int((x + radius) // self.cell_size)
        min_cy = int((y - radius) // self.cell_size)
        max_cy = int((y + radius) // self.cell_size)

        results = []
        for cx in range(min_cx, max_cx + 1):
            for cy in range(min_cy, max_cy + 1):
                cell = (cx, cy)
                if cell in self.grid:
                    results.extend(self.grid[cell])
        return results

class ClashBattleSimulator:
    def __init__(self, state: ClashGameState):
        self.state = state
        self.spatial_grid = SpatialGrid(cell_size=10.0)

    def rebuild_spatial_grid(self):
        """Rebuilds spatial grid index for active troops."""
        self.spatial_grid.clear()
        for t in self.state.troops:
            if t.hp > 0:
                self.spatial_grid.insert(t)

    def execute_round(self, red_order: Dict[str, Any], blue_order: Dict[str, Any], round_delta_seconds: float = 1.0):
        if self.state.status != "running":
            return

        self.state.round_number += 1
        self.state.elapsed_seconds += round_delta_seconds
        self.state.events = []

        # Store commander thoughts and orders
        self.state.players["red"].last_thought = red_order.get("thought", "Advancing lane push.")
        self.state.players["red"].last_taunt = red_order.get("taunt", "")
        self.state.players["red"].last_action = red_order

        self.state.players["blue"].last_thought = blue_order.get("thought", "Advancing lane push.")
        self.state.players["blue"].last_taunt = blue_order.get("taunt", "")
        self.state.players["blue"].last_action = blue_order

        # Update resources and actions
        self._resolve_elixir(round_delta_seconds)
        self._resolve_card_play("red", red_order)
        self._resolve_card_play("blue", blue_order)
        self.rebuild_spatial_grid()
        self._resolve_movement(round_delta_seconds)
        self.rebuild_spatial_grid()
        self._resolve_tower_attacks()
        self._resolve_combat()
        self._check_match_conclusion()

    def _resolve_elixir(self, delta: float):
        # Trigger Double Elixir after 120s or in overtime
        if self.state.elapsed_seconds >= DOUBLE_ELIXIR_THRESHOLD_SECONDS:
            if not self.state.is_double_elixir:
                self.state.is_double_elixir = True
                self.state.events.append({"type": "double_elixir"})
                self.state.add_combat_log("⚡ 60 SECONDS REMAINING: 2X DOUBLE ELIXIR UNLEASHED!", category="match", icon="⚡")

        rate = DOUBLE_ELIXIR_RATE if self.state.is_double_elixir else NORMAL_ELIXIR_RATE
        for p in self.state.players.values():
            p.elixir = min(MAX_ELIXIR, p.elixir + (rate * delta))

    def _resolve_card_play(self, team: str, order: Dict[str, Any]):
        card_name = str(order.get("card", "none")).lower().strip()
        lane = str(order.get("lane", "left")).lower().strip()
        if lane not in ["left", "right"]:
            lane = "left"

        if card_name == "none" or card_name not in CARD_CATALOG:
            return

        player = self.state.players[team]
        proto = CARD_CATALOG[card_name]
        cost = proto["elixir"]

        if player.elixir >= cost:
            player.elixir -= cost
            player.stats["cards_played"] += 1
            player.stats["elixir_spent"] += cost

            opp_team = "blue" if team == "red" else "red"
            opp_towers = self.state.players[opp_team].towers
            opp_princess_dead = opp_towers[f"{lane}_princess"]["destroyed"]

            self.state.events.append({
                "type": "deploy",
                "team": team,
                "card": card_name,
                "lane": lane,
                "cost": cost
            })

            # SPELL CARDS (Fireball, Goblin Barrel)
            if proto.get("type") == "spell":
                if card_name == "fireball":
                    target_tower = opp_towers[f"{lane}_princess"] if not opp_princess_dead else opp_towers["king"]
                    t_dmg = proto.get("tower_damage", 130)
                    target_tower["hp"] = max(0, target_tower["hp"] - t_dmg)
                    if not target_tower.get("active", False) and target_tower == opp_towers["king"]:
                        target_tower["active"] = True

                    self.state.events.append({
                        "type": "projectile",
                        "kind": "fireball",
                        "team": team,
                        "from_x": 50.0,
                        "from_y": 10.0 if team == "red" else 90.0,
                        "to_x": target_tower["x"],
                        "to_y": target_tower["y"],
                        "damage": t_dmg
                    })
                    self.state.events.append({
                        "type": "damage",
                        "x": target_tower["x"],
                        "y": target_tower["y"],
                        "amount": t_dmg,
                        "target_type": "tower",
                        "is_crit": True
                    })
                    self.state.events.append({"type": "shake", "intensity": 6.0})

                    # Splash troops in lane
                    splash_dmg = proto.get("damage", 350)
                    for t in self.state.troops:
                        if t.team == opp_team and t.lane == lane:
                            t.hp -= splash_dmg
                            self.state.events.append({
                                "type": "damage",
                                "x": t.x,
                                "y": t.y,
                                "amount": splash_dmg,
                                "target_type": "troop",
                                "is_crit": False
                            })

                    self.state.add_combat_log(
                        f"{team.upper()} hurled a Fireball at {opp_team.upper()} {target_tower['name']} (-{t_dmg} HP)!",
                        category="spell", icon="🔥"
                    )

                elif card_name == "goblin_barrel":
                    target_tower = opp_towers["king"] if opp_princess_dead else opp_towers[f"{lane}_princess"]
                    target_x = target_tower["x"]
                    spawn_y = target_tower["y"] + (2.0 if team == "blue" else -2.0)

                    self.state.events.append({
                        "type": "projectile",
                        "kind": "barrel",
                        "team": team,
                        "from_x": 50.0,
                        "from_y": 7.0 if team == "red" else 93.0,
                        "to_x": target_x,
                        "to_y": spawn_y
                    })

                    count = proto.get("count", 3)
                    for i in range(count):
                        t = ClashTroop("knight", team, lane, spawn_y + (i * 0.5), x_pos=target_x + ((i - 1) * 1.5))
                        t.card_id = "goblin_barrel"
                        t.name = "Dagger Goblin"
                        t.hp = proto.get("hp", 100)
                        t.damage = proto.get("damage", 60)
                        t.speed = proto.get("speed", 11.0)
                        t.icon = "🗡️"
                        self.state.troops.append(t)

                    self.state.add_combat_log(
                        f"{team.upper()} landed a Goblin Barrel directly onto {opp_team.upper()}'s {target_tower['name']}!",
                        category="spell", icon="🪵"
                    )

            # TROOP CARDS
            else:
                if team == "red":
                    spawn_y = 52.0 if opp_princess_dead else 28.0
                else:
                    spawn_y = 48.0 if opp_princess_dead else 72.0

                count = proto.get("count", 1)
                for i in range(count):
                    offset = (i - (count - 1) / 2.0) * 1.5
                    t = ClashTroop(card_name, team, lane, spawn_y + offset)
                    self.state.troops.append(t)

                self.state.events.append({
                    "type": "spawn",
                    "team": team,
                    "card": card_name,
                    "lane": lane,
                    "x": LEFT_LANE_X if lane == "left" else RIGHT_LANE_X,
                    "y": spawn_y
                })

                self.state.add_combat_log(
                    f"{team.upper()} deployed {proto['name']} on {lane.upper()} lane!",
                    category="recruit", icon=proto["icon"]
                )

    def _resolve_movement(self, delta: float):
        """Troops march down their assigned lane towards bridges and towers."""
        for t in self.state.troops:
            opp_team = "blue" if t.team == "red" else "red"
            opp_towers = self.state.players[opp_team].towers

            # Determine destination tower
            target_tower = opp_towers[f"{t.lane}_princess"]
            if target_tower["destroyed"]:
                target_tower = opp_towers["king"]

            is_king = (target_tower == opp_towers["king"])
            t_radius = KING_TOWER_RADIUS if is_king else PRINCESS_TOWER_RADIUS

            # Check if an enemy troop is right in front of us in our lane (O(1) Spatial Hash Grid)
            enemy_ahead = False
            if t.target_type != "buildings":
                nearby = self.spatial_grid.query_nearby(t.x, t.y, t.range)
                for other in nearby:
                    if other.team == opp_team and other.lane == t.lane and other.hp > 0:
                        dist = math.hypot(other.x - t.x, other.y - t.y)
                        if dist <= t.range:
                            enemy_ahead = True
                            break

            dx = target_tower["x"] - t.x
            dy = target_tower["y"] - t.y
            dist_to_tower = math.hypot(dx, dy)
            reach = t_radius + t.range

            # Stop when in attack reach of the outer castle wall, or engaged with troop
            if dist_to_tower <= reach or enemy_ahead:
                continue

            # Move towards destination tower, strictly stopping at the outer perimeter
            step = (t.speed * 0.6) * delta
            min_perimeter = t_radius + 0.8  # Physical fortress wall buffer
            if dist_to_tower > min_perimeter:
                max_step = dist_to_tower - min_perimeter
                move_dist = min(step, max_step)
                t.x += (dx / dist_to_tower) * move_dist
                t.y += (dy / dist_to_tower) * move_dist

    def _resolve_tower_attacks(self):
        """Princess and King towers fire upon enemy invaders in their quadrant."""
        for team in ["red", "blue"]:
            opp_team = "blue" if team == "red" else "red"
            towers = self.state.players[team].towers

            for t_key, tower in towers.items():
                if tower["destroyed"]:
                    continue
                if t_key == "king" and not tower["active"]:
                    continue  # King tower sleeps until provoked!

                is_left = ("left" in t_key)
                is_right = ("right" in t_key)
                is_king = (t_key == "king")
                t_radius = KING_TOWER_RADIUS if is_king else PRINCESS_TOWER_RADIUS
                t_range = KING_TOWER_RANGE if is_king else PRINCESS_TOWER_RANGE

                enemies_in_range = []
                for u in self.state.troops:
                    if u.team == opp_team:
                        if is_left and u.lane != "left" and not is_king:
                            continue
                        if is_right and u.lane != "right" and not is_king:
                            continue
                        dist = math.hypot(u.x - tower["x"], u.y - tower["y"])
                        if dist <= (t_range + t_radius):
                            enemies_in_range.append((dist, u))

                if enemies_in_range:
                    enemies_in_range.sort(key=lambda x: x[0])
                    target = enemies_in_range[0][1]
                    dmg = KING_TOWER_DAMAGE if t_key == "king" else PRINCESS_TOWER_DAMAGE
                    target.hp -= dmg

                    self.state.events.append({
                        "type": "tower_attack",
                        "team": team,
                        "tower": t_key,
                        "from_x": tower["x"],
                        "from_y": tower["y"],
                        "to_x": target.x,
                        "to_y": target.y,
                        "target_id": target.id,
                        "damage": dmg,
                        "kind": "cannon" if t_key == "king" else "arrow"
                    })
                    self.state.events.append({
                        "type": "damage",
                        "x": target.x,
                        "y": target.y,
                        "amount": dmg,
                        "target_type": "troop",
                        "is_crit": False
                    })

    def _resolve_combat(self):
        """Troops clash with enemy troops in the lane or smash Crown Towers."""
        for u in [t for t in self.state.troops if t.hp > 0]:
            opp_team = "blue" if u.team == "red" else "red"
            opp_towers = self.state.players[opp_team].towers

            target_tower = opp_towers[f"{u.lane}_princess"]
            if target_tower["destroyed"]:
                target_tower = opp_towers["king"]

            is_king = (target_tower == opp_towers["king"])
            t_radius = KING_TOWER_RADIUS if is_king else PRINCESS_TOWER_RADIUS

            dx = target_tower["x"] - u.x
            dy = target_tower["y"] - u.y
            dist_to_tower = math.hypot(dx, dy)
            reach = t_radius + u.range

            # 1. Siege units (Giant, Hog Rider) strictly prioritize towers!
            if u.target_type == "buildings":
                if dist_to_tower <= reach:
                    target_tower["hp"] = max(0, target_tower["hp"] - u.damage)
                    if target_tower == opp_towers["king"]:
                        target_tower["active"] = True
                    self.state.players[u.team].stats["damage_dealt"] += u.damage

                    impact_x = (u.x * 0.6) + (target_tower["x"] * 0.4)
                    impact_y = (u.y * 0.6) + (target_tower["y"] * 0.4)

                    self.state.events.append({
                        "type": "troop_attack",
                        "attacker_id": u.id,
                        "attacker_card": u.card_id,
                        "team": u.team,
                        "target_type": "tower",
                        "from_x": u.x,
                        "from_y": u.y,
                        "to_x": impact_x,
                        "to_y": impact_y,
                        "damage": u.damage
                    })
                    self.state.events.append({
                        "type": "damage",
                        "x": impact_x,
                        "y": impact_y,
                        "amount": u.damage,
                        "target_type": "tower",
                        "is_crit": (u.damage >= 200)
                    })
                continue

            # 2. Combat units (Knight, PEKKA, Musketeer, Archers, Skeletons, Baby Dragon):
            # Prioritize defending troops in range!
            enemies_in_lane = [
                e for e in self.state.troops
                if e.team == opp_team and e.lane == u.lane and math.hypot(e.x - u.x, e.y - u.y) <= u.range
            ]
            if enemies_in_lane:
                if u.splash:
                    for e in enemies_in_lane:
                        e.hp -= u.damage
                        self.state.events.append({
                            "type": "damage",
                            "x": e.x,
                            "y": e.y,
                            "amount": u.damage,
                            "target_type": "troop",
                            "is_crit": False
                        })
                else:
                    target = min(enemies_in_lane, key=lambda e: math.hypot(e.x - u.x, e.y - u.y))
                    target.hp -= u.damage
                    self.state.events.append({
                        "type": "damage",
                        "x": target.x,
                        "y": target.y,
                        "amount": u.damage,
                        "target_type": "troop",
                        "is_crit": (u.damage >= 200)
                    })

                self.state.players[u.team].stats["damage_dealt"] += u.damage
                self.state.events.append({
                    "type": "troop_attack",
                    "attacker_id": u.id,
                    "attacker_card": u.card_id,
                    "team": u.team,
                    "target_type": "troop",
                    "from_x": u.x,
                    "from_y": u.y,
                    "to_x": u.x,
                    "to_y": u.y,
                    "damage": u.damage,
                    "splash": u.splash
                })
            elif dist_to_tower <= reach:
                # No troops blocking; strike the tower!
                target_tower["hp"] = max(0, target_tower["hp"] - u.damage)
                if target_tower == opp_towers["king"]:
                    target_tower["active"] = True
                self.state.players[u.team].stats["damage_dealt"] += u.damage

                impact_x = (u.x * 0.6) + (target_tower["x"] * 0.4)
                impact_y = (u.y * 0.6) + (target_tower["y"] * 0.4)

                self.state.events.append({
                    "type": "troop_attack",
                    "attacker_id": u.id,
                    "attacker_card": u.card_id,
                    "team": u.team,
                    "target_type": "tower",
                    "from_x": u.x,
                    "from_y": u.y,
                    "to_x": impact_x,
                    "to_y": impact_y,
                    "damage": u.damage
                })
                self.state.events.append({
                    "type": "damage",
                    "x": impact_x,
                    "y": impact_y,
                    "amount": u.damage,
                    "target_type": "tower",
                    "is_crit": (u.damage >= 200)
                })

        # Process casualties & Crown captures
        self._process_towers_and_deaths()

    def _process_towers_and_deaths(self):
        for team in ["red", "blue"]:
            opp_team = "blue" if team == "red" else "red"
            towers = self.state.players[team].towers

            for t_key in ["left_princess", "right_princess"]:
                t = towers[t_key]
                if t["hp"] <= 0 and not t["destroyed"]:
                    t["destroyed"] = True
                    t["hp"] = 0
                    self.state.players[opp_team].crowns += 1
                    towers["king"]["active"] = True  # King tower awakens!

                    self.state.events.append({
                        "type": "tower_destroyed",
                        "team": team,
                        "tower": t_key,
                        "crowns": self.state.players[opp_team].crowns
                    })
                    self.state.events.append({"type": "shake", "intensity": 8.0})

                    self.state.add_combat_log(
                        f"👑 CROWN TAKEN! {opp_team.upper()} shattered {team.upper()}'s {t['name']}!",
                        category="crown", icon="👑"
                    )

            k = towers["king"]
            if k["hp"] <= 0 and not k["destroyed"]:
                k["destroyed"] = True
                k["hp"] = 0
                self.state.players[opp_team].crowns = 3
                self.state.status = "finished"
                self.state.winner = opp_team
                self.state.win_reason = f"🏆 3-CROWN KNOCKOUT! {opp_team.upper()} shattered the Royal King Tower!"

                self.state.events.append({
                    "type": "tower_destroyed",
                    "team": team,
                    "tower": "king",
                    "crowns": 3
                })
                self.state.events.append({"type": "victory", "winner": opp_team})
                self.state.events.append({"type": "shake", "intensity": 14.0})

                self.state.add_combat_log(self.state.win_reason, category="victory", icon="👑")
                return

        # Remove dead troops
        survivors = []
        for t in self.state.troops:
            if t.hp > 0:
                survivors.append(t)
            else:
                killer = "blue" if t.team == "red" else "red"
                self.state.players[killer].stats["troops_killed"] += 1
                self.state.events.append({
                    "type": "death",
                    "card_id": t.card_id,
                    "team": t.team,
                    "x": t.x,
                    "y": t.y
                })
        self.state.troops = survivors

    def _check_match_conclusion(self):
        if self.state.status == "finished":
            return

        red_crowns = self.state.players["red"].crowns
        blue_crowns = self.state.players["blue"].crowns

        # 3-Crown KO instant win
        if red_crowns >= 3:
            self.state.status = "finished"
            self.state.winner = "red"
            self.state.win_reason = "🏆 3-CROWN KNOCKOUT VICTORY for RED!"
            self.state.events.append({"type": "victory", "winner": "red"})
            return
        elif blue_crowns >= 3:
            self.state.status = "finished"
            self.state.winner = "blue"
            self.state.win_reason = "🏆 3-CROWN KNOCKOUT VICTORY for BLUE!"
            self.state.events.append({"type": "victory", "winner": "blue"})
            return

        # Sudden Death Overtime: first tower taken down wins immediately!
        if self.state.is_overtime and red_crowns != blue_crowns:
            self.state.status = "finished"
            self.state.winner = "red" if red_crowns > blue_crowns else "blue"
            self.state.win_reason = f"⏱️ SUDDEN DEATH OVERTIME VICTORY for {self.state.winner.upper()}! First tower taken down!"
            self.state.events.append({"type": "victory", "winner": self.state.winner})
            self.state.add_combat_log(self.state.win_reason, category="victory", icon="👑")
            return

        # Standard Timer (3 mins = 180s)
        if self.state.elapsed_seconds >= self.state.max_duration_seconds:
            if red_crowns > blue_crowns:
                self.state.status = "finished"
                self.state.winner = "red"
                self.state.win_reason = f"MATCH FINISHED! Red wins {red_crowns} - {blue_crowns} on Crowns!"
                self.state.events.append({"type": "victory", "winner": "red"})
                self.state.add_combat_log(self.state.win_reason, category="victory", icon="🏆")
            elif blue_crowns > red_crowns:
                self.state.status = "finished"
                self.state.winner = "blue"
                self.state.win_reason = f"MATCH FINISHED! Blue wins {blue_crowns} - {red_crowns} on Crowns!"
                self.state.events.append({"type": "victory", "winner": "blue"})
                self.state.add_combat_log(self.state.win_reason, category="victory", icon="🏆")
            else:
                # Sudden Death Overtime (up to 60s extra)
                if not self.state.is_overtime:
                    self.state.is_overtime = True
                    self.state.max_duration_seconds += 60
                    self.state.is_double_elixir = True
                    self.state.events.append({"type": "overtime"})
                    self.state.add_combat_log("⏱️ OVERTIME SUDDEN DEATH: FIRST TOWER FALLS WINS!", category="match", icon="⏳")
                elif self.state.elapsed_seconds >= self.state.max_duration_seconds:
                    self._resolve_lowest_hp_tiebreak()

    def _resolve_lowest_hp_tiebreak(self):
        self.state.status = "finished"
        red_min_hp = min(t["hp"] for t in self.state.players["red"].towers.values() if not t["destroyed"])
        blue_min_hp = min(t["hp"] for t in self.state.players["blue"].towers.values() if not t["destroyed"])

        if red_min_hp > blue_min_hp:
            self.state.winner = "red"
            self.state.win_reason = f"TIEBREAKER VICTORY: Red towers had more HP ({red_min_hp} vs {blue_min_hp})!"
            self.state.events.append({"type": "victory", "winner": "red"})
        elif blue_min_hp > red_min_hp:
            self.state.winner = "blue"
            self.state.win_reason = f"TIEBREAKER VICTORY: Blue towers had more HP ({blue_min_hp} vs {red_min_hp})!"
            self.state.events.append({"type": "victory", "winner": "blue"})
        else:
            self.state.winner = "draw"
            self.state.win_reason = "DRAW: Dead heat in Sudden Death!"
            self.state.events.append({"type": "victory", "winner": "draw"})

        self.state.add_combat_log(self.state.win_reason, category="victory", icon="🏆")
