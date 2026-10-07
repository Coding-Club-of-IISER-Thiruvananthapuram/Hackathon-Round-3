"""
Match Orchestrator for AI Clash Royale Arena.
Coordinates asynchronous dual-LLM inference, lane simulation loop,
spectator broadcasts, and 1v1 knockout tournament progression.
"""
import os
import asyncio
from typing import Dict, Any, Optional, List, Callable
from engine.config import DEFAULT_MATCH_DURATION_SECONDS, DEFAULT_TICK_INTERVAL_SECONDS, DEFAULT_MODEL, OLLAMA_BASE_URL
from engine.skill_loader import ClashSkillProfile, load_kingdom_skill_file, parse_kingdom_skill
from engine.game_state import ClashGameState
from engine.battle_simulator import ClashBattleSimulator
from engine.llm_commander import LLMCommander
from engine.tournament_manager import TournamentManager

class MatchOrchestrator:
    def __init__(self, model_name: str = DEFAULT_MODEL, base_url: str = OLLAMA_BASE_URL):
        self.model_name = model_name
        self.base_url = base_url
        self.llm = LLMCommander(model_name=model_name, base_url=base_url)
        
        self.state: Optional[ClashGameState] = None
        self.simulator: Optional[ClashBattleSimulator] = None
        self.red_skill: Optional[ClashSkillProfile] = None
        self.blue_skill: Optional[ClashSkillProfile] = None
        
        self.tournament = TournamentManager()
        self.active_tournament_match_id: Optional[str] = None

        self.tick_interval = DEFAULT_TICK_INTERVAL_SECONDS
        self.speed_multiplier = 1.0
        self.is_paused = False
        self._loop_task: Optional[asyncio.Task] = None
        self.listeners: List[Callable[[Dict[str, Any]], Any]] = []

        self.red_source: str = ""
        self.blue_source: str = ""
        self.is_raw_source: bool = False
        self.saved_max_duration: int = DEFAULT_MATCH_DURATION_SECONDS

    def register_listener(self, callback: Callable[[Dict[str, Any]], Any]):
        self.listeners.append(callback)

    async def broadcast_state(self):
        if not self.state:
            return
        payload = self.state.to_dict()
        payload["speed_multiplier"] = self.speed_multiplier
        payload["is_paused"] = self.is_paused
        payload["tournament"] = self.tournament.to_dict()
        payload["active_match_id"] = self.active_tournament_match_id

        for cb in self.listeners:
            try:
                res = cb(payload)
                if asyncio.iscoroutine(res):
                    await res
            except Exception:
                pass

    def setup_match(
        self,
        red_skill_path_or_content: str,
        blue_skill_path_or_content: str,
        max_duration_seconds: int = DEFAULT_MATCH_DURATION_SECONDS,
        is_raw_content: bool = False,
        tournament_match_id: Optional[str] = None
    ):
        self.red_source = red_skill_path_or_content
        self.blue_source = blue_skill_path_or_content
        self.is_raw_source = is_raw_content
        self.saved_max_duration = max_duration_seconds
        self.active_tournament_match_id = tournament_match_id

        if is_raw_content:
            self.red_skill = parse_kingdom_skill(red_skill_path_or_content)
            self.blue_skill = parse_kingdom_skill(blue_skill_path_or_content)
        else:
            self.red_skill = load_kingdom_skill_file(red_skill_path_or_content)
            self.blue_skill = load_kingdom_skill_file(blue_skill_path_or_content)

        self.state = ClashGameState(max_duration_seconds=max_duration_seconds)
        self.state.players["red"].name = self.red_skill.name
        self.state.players["red"].author = self.red_skill.author
        self.state.players["red"].deck = self.red_skill.deck
        self.state.players["red"].last_taunt = self.red_skill.war_cry

        self.state.players["blue"].name = self.blue_skill.name
        self.state.players["blue"].author = self.blue_skill.author
        self.state.players["blue"].deck = self.blue_skill.deck
        self.state.players["blue"].last_taunt = self.blue_skill.war_cry

        self.state.add_combat_log(
            f"Battle initialized in Clash Arena! {self.red_skill.name} vs {self.blue_skill.name}",
            category="match", icon="⚔️"
        )
        self.simulator = ClashBattleSimulator(self.state)
        self.is_paused = False

    def reset_match(self):
        if self._loop_task and not self._loop_task.done():
            self._loop_task.cancel()
        if self.red_source and self.blue_source:
            self.setup_match(
                self.red_source,
                self.blue_source,
                max_duration_seconds=self.saved_max_duration,
                is_raw_content=self.is_raw_source,
                tournament_match_id=self.active_tournament_match_id
            )

    async def start_match(self):
        if not self.state or not self.simulator:
            raise RuntimeError("Match has not been set up yet.")

        if self._loop_task and not self._loop_task.done():
            self._loop_task.cancel()

        self.state.status = "running"
        await self.broadcast_state()
        self._loop_task = asyncio.create_task(self._simulation_loop())

    def pause_match(self):
        self.is_paused = True
        if self.state:
            self.state.status = "paused"

    def resume_match(self):
        self.is_paused = False
        if self.state and self.state.status == "paused":
            self.state.status = "running"

    def set_speed(self, multiplier: float):
        self.speed_multiplier = max(0.25, min(10.0, float(multiplier)))

    async def step_turn(self):
        if not self.state or not self.simulator:
            return
        if self.state.status == "finished":
            return

        self.state.status = "running"
        await self._execute_one_tick()
        if self.state.status != "finished":
            self.state.status = "paused"
        await self.broadcast_state()

    async def _simulation_loop(self):
        try:
            while self.state and self.state.status == "running":
                if self.is_paused:
                    await asyncio.sleep(0.15)
                    continue

                await self._execute_one_tick()
                await self.broadcast_state()

                if self.state.status == "finished":
                    # Record tournament result if in tournament mode
                    if self.active_tournament_match_id and self.state.winner in ["red", "blue"]:
                        winner_is_red = self.state.winner == "red"
                        win_file = self.red_source if winner_is_red else self.blue_source
                        lose_file = self.blue_source if winner_is_red else self.red_source
                        win_name = self.red_skill.name if winner_is_red else self.blue_skill.name
                        lose_name = self.blue_skill.name if winner_is_red else self.red_skill.name

                        scorecard = {
                            "winner": self.state.winner,
                            "reason": self.state.win_reason,
                            "red_crowns": self.state.players["red"].crowns,
                            "blue_crowns": self.state.players["blue"].crowns,
                            "time_seconds": int(self.state.elapsed_seconds)
                        }

                        w_filename = os.path.basename(win_file) if not self.is_raw_source else f"{win_name.lower().replace(' ', '_')}.md"
                        l_filename = os.path.basename(lose_file) if not self.is_raw_source else f"{lose_name.lower().replace(' ', '_')}.md"

                        self.tournament.record_match_result(
                            self.active_tournament_match_id,
                            winner_file=w_filename,
                            winner_name=win_name,
                            loser_file=l_filename,
                            scorecard=scorecard
                        )
                        await self.broadcast_state()
                    break

                sleep_time = max(0.05, self.tick_interval / self.speed_multiplier)
                await asyncio.sleep(sleep_time)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[MatchOrchestrator] Unexpected error in simulation loop: {e}")
            if self.state:
                self.state.add_combat_log(f"Engine note: {str(e)}", category="match", icon="⚠️")
            await self.broadcast_state()

    async def _execute_one_tick(self):
        if not self.state or not self.simulator or not self.red_skill or not self.blue_skill:
            return

        red_brief = self.state.get_situational_brief("red")
        blue_brief = self.state.get_situational_brief("blue")

        red_task = self.llm.generate_order_async(self.red_skill, "red", red_brief)
        blue_task = self.llm.generate_order_async(self.blue_skill, "blue", blue_brief)

        red_order, blue_order = await asyncio.gather(red_task, blue_task)
        self.simulator.execute_round(red_order, blue_order, round_delta_seconds=1.0)
