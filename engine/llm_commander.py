"""
Async LLM Commander client for Clash Royale AI Arena.
Ensures matches purely depend on the participants' uploaded skill files:
- Custom tactical triggers and IF-THEN doctrine execution
- Strict adherence to the participant's chosen 8-card roster
- Card priority weighting according to participant percentages
- Lane preferences and authentic participant war cries
"""
import re
import json
import time
import random
import socket
import asyncio
import urllib.request
import urllib.error
from urllib.parse import urlparse
from typing import Dict, Any, Optional, List
from engine.config import OLLAMA_BASE_URL, DEFAULT_MODEL, CARD_CATALOG
from engine.skill_loader import ClashSkillProfile

class LLMCommander:
    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        base_url: str = OLLAMA_BASE_URL,
        timeout: float = 6.0
    ):
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        if "localhost" in self.base_url:
            self.base_url = self.base_url.replace("localhost", "127.0.0.1")
        self.timeout = timeout
        self._ollama_online: Optional[bool] = None
        self._last_ollama_check: float = 0.0

    def _is_ollama_online(self) -> bool:
        """Fast non-blocking probe of Ollama reachability cached for 10 seconds."""
        now = time.time()
        if self._ollama_online is not None and (now - self._last_ollama_check) < 10.0:
            return self._ollama_online

        self._last_ollama_check = now
        try:
            parsed = urlparse(self.base_url)
            host = parsed.hostname or "127.0.0.1"
            port = parsed.port or 11434
            with socket.create_connection((host, port), timeout=0.12):
                self._ollama_online = True
                return True
        except Exception:
            self._ollama_online = False
            return False

    async def generate_order_async(
        self,
        skill_profile: ClashSkillProfile,
        team: str,
        situational_brief: str
    ) -> Dict[str, Any]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._generate_order_sync,
            skill_profile,
            team,
            situational_brief
        )

    def _generate_order_sync(
        self,
        skill_profile: ClashSkillProfile,
        team: str,
        situational_brief: str
    ) -> Dict[str, Any]:
        system_prompt = skill_profile.generate_system_prompt(team)
        user_prompt = f"{situational_brief}\n\nRespond with your JSON card deployment:"

        combined_prompt = f"<|im_start|>system\n{system_prompt}<|im_end|>\n<|im_start|>user\n{user_prompt}<|im_end|>\n<|im_start|>assistant\n"

        endpoint = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model_name,
            "prompt": combined_prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.35,
                "top_p": 0.9,
                "num_predict": 90,
                "num_ctx": 2048,
                "num_thread": 4
            }
        }

        raw_response = ""
        if self._is_ollama_online():
            try:
                req_data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    endpoint,
                    data=req_data,
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    res_body = response.read().decode("utf-8")
                    res_json = json.loads(res_body)
                    raw_response = res_json.get("response", "")
            except Exception as e:
                self._ollama_online = False
                raw_response = f"ERROR: {str(e)}"
        else:
            raw_response = "OFFLINE: Tactical heuristics active"

        parsed_action = self._sanitize_and_validate(raw_response, skill_profile, situational_brief)
        parsed_action["raw_response"] = raw_response
        return parsed_action

    def _parse_brief_metrics(self, brief: str) -> Dict[str, Any]:
        metrics = {
            "elixir": 5.0,
            "my_left": 1400, "my_right": 1400, "my_king": 2400,
            "opp_left": 1400, "opp_right": 1400, "opp_king": 2400,
            "my_troops_left": [], "my_troops_right": [],
            "opp_troops_left": [], "opp_troops_right": [],
            "last_opp_card": None, "last_opp_lane": None
        }
        if not brief:
            return metrics

        elixir_m = re.search(r"Your Elixir:\s*(\d+(?:\.\d+)?)", brief)
        if elixir_m:
            try:
                metrics["elixir"] = float(elixir_m.group(1))
            except Exception:
                pass

        m_towers = re.search(r"Your Towers:\s*Left Princess=(\d+)HP,\s*Right Princess=(\d+)HP,\s*King=(\d+)HP", brief)
        if m_towers:
            metrics["my_left"] = int(m_towers.group(1))
            metrics["my_right"] = int(m_towers.group(2))
            metrics["my_king"] = int(m_towers.group(3))

        o_towers = re.search(r"Enemy Towers:\s*Left Princess=(\d+)HP,\s*Right Princess=(\d+)HP,\s*King=(\d+)HP", brief)
        if o_towers:
            metrics["opp_left"] = int(o_towers.group(1))
            metrics["opp_right"] = int(o_towers.group(2))
            metrics["opp_king"] = int(o_towers.group(3))

        from engine.skill_loader import detect_card_from_text

        opp_tr_m = re.search(r"Enemy Incoming Troops:\s*\d+\s*\((.*?)\)", brief)
        if opp_tr_m:
            items = [t.strip() for t in opp_tr_m.group(1).split(",") if t.strip() and t.strip() != "None"]
            for it in items:
                lane = "right" if "right" in it.lower() else "left"
                card = detect_card_from_text(it)
                if card:
                    metrics[f"opp_troops_{lane}"].append(card)

        my_tr_m = re.search(r"Your Active Troops:\s*\d+\s*\((.*?)\)", brief)
        if my_tr_m:
            items = [t.strip() for t in my_tr_m.group(1).split(",") if t.strip() and t.strip() != "None"]
            for it in items:
                lane = "right" if "right" in it.lower() else "left"
                card = detect_card_from_text(it)
                if card:
                    metrics[f"my_troops_{lane}"].append(card)

        last_opp_m = re.search(r"Last Enemy Deployment:\s*([a-zA-Z_]+)\s+on\s+([a-zA-Z_]+)", brief, re.IGNORECASE)
        if last_opp_m:
            c = detect_card_from_text(last_opp_m.group(1))
            if c:
                metrics["last_opp_card"] = c
                metrics["last_opp_lane"] = last_opp_m.group(2).lower()

        return metrics

    def _tactical_heuristics(self, skill: ClashSkillProfile, brief: str) -> Dict[str, Any]:
        """
        Pure Skill-Driven Decision Engine.
        Directly evaluates the participant's custom Markdown triggers, 8-card roster,
        archetype, and priority weights.
        """
        metrics = self._parse_brief_metrics(brief)
        elixir = metrics["elixir"]
        deck = [c for c in skill.deck if c in CARD_CATALOG]
        preferred_lane = skill.preferred_lane if skill.preferred_lane in ["left", "right"] else ("left" if random.random() < 0.5 else "right")

        opp_left_dead = metrics["opp_left"] <= 0
        opp_right_dead = metrics["opp_right"] <= 0

        # Determine lowest HP active enemy tower
        active_towers = []
        if not opp_left_dead:
            active_towers.append(("left", metrics["opp_left"]))
        if not opp_right_dead:
            active_towers.append(("right", metrics["opp_right"]))
        if (opp_left_dead or opp_right_dead) and metrics["opp_king"] > 0:
            active_towers.append(("left" if opp_left_dead else "right", metrics["opp_king"]))
        lowest_hp_lane = min(active_towers, key=lambda x: x[1])[0] if active_towers else preferred_lane

        # 1. EVALUATE CUSTOM TRIGGERS FROM SKILL FILE (IN STRICT PRIORITY ORDER)
        parsed_triggers = getattr(skill, "parsed_triggers", [])
        for trig in parsed_triggers:
            cond = trig.get("cond", {})
            action = trig.get("action", {})
            raw_text = trig.get("raw", "")

            # If trigger has no conditions recognized, skip to avoid unconditional loops
            if not cond:
                continue

            cond_met = True
            threat_lane = None

            # Min Elixir check
            if "min_elixir" in cond:
                if elixir < cond["min_elixir"]:
                    cond_met = False

            # Max Tower HP check (absolute HP)
            if cond_met and "max_tower_hp" in cond:
                max_hp = cond["max_tower_hp"]
                in_range = False
                if not opp_left_dead and metrics["opp_left"] <= max_hp:
                    in_range = True
                    threat_lane = "left"
                elif not opp_right_dead and metrics["opp_right"] <= max_hp:
                    in_range = True
                    threat_lane = "right"
                elif (opp_left_dead or opp_right_dead) and metrics["opp_king"] <= max_hp:
                    in_range = True
                    threat_lane = "left" if opp_left_dead else "right"
                if not in_range:
                    cond_met = False

            # Max Tower HP percentage check (e.g. < 10% of initial HP)
            if cond_met and "max_tower_hp_pct" in cond:
                pct = cond["max_tower_hp_pct"] / 100.0
                in_range = False
                if not opp_left_dead and metrics["opp_left"] <= (1400 * pct):
                    in_range = True
                    threat_lane = "left"
                elif not opp_right_dead and metrics["opp_right"] <= (1400 * pct):
                    in_range = True
                    threat_lane = "right"
                elif (opp_left_dead or opp_right_dead) and metrics["opp_king"] <= (2400 * pct):
                    in_range = True
                    threat_lane = "left" if opp_left_dead else "right"
                if not in_range:
                    cond_met = False

            # Specific Enemy Cards check
            if cond_met and "enemy_cards" in cond:
                matched_lanes = []
                for req_c in cond["enemy_cards"]:
                    if req_c in metrics.get("opp_troops_left", []):
                        matched_lanes.append("left")
                    if req_c in metrics.get("opp_troops_right", []):
                        matched_lanes.append("right")
                    if metrics.get("last_opp_card") == req_c:
                        matched_lanes.append(metrics.get("last_opp_lane", preferred_lane))
                if not matched_lanes:
                    cond_met = False
                else:
                    threat_lane = matched_lanes[0]

            # Enemy Tank check
            if cond_met and cond.get("enemy_tank"):
                tank_lanes = []
                for ln in ["left", "right"]:
                    if any(c in ["giant", "pekka", "hog_rider"] for c in metrics.get(f"opp_troops_{ln}", [])):
                        tank_lanes.append(ln)
                if not tank_lanes:
                    cond_met = False
                else:
                    threat_lane = tank_lanes[0]

            # Enemy Swarm check
            if cond_met and cond.get("enemy_swarm"):
                swarm_lanes = []
                for ln in ["left", "right"]:
                    if any(c in ["skeletons", "archers"] for c in metrics.get(f"opp_troops_{ln}", [])):
                        swarm_lanes.append(ln)
                if not swarm_lanes:
                    cond_met = False
                else:
                    threat_lane = swarm_lanes[0]

            # Friendly Card check (e.g. "our PEKKA is deployed")
            if cond_met and "friendly_card" in cond:
                f_card = cond["friendly_card"]
                f_lanes = []
                if f_card in metrics.get("my_troops_left", []):
                    f_lanes.append("left")
                if f_card in metrics.get("my_troops_right", []):
                    f_lanes.append("right")
                if not f_lanes:
                    cond_met = False
                else:
                    threat_lane = f_lanes[0]

            # Lane Clear check
            if cond_met and cond.get("lane_clear"):
                opp_left_count = len(metrics.get("opp_troops_left", []))
                opp_right_count = len(metrics.get("opp_troops_right", []))
                if opp_left_count > 0 and opp_right_count > 0:
                    cond_met = False

            # Enemy Attacks Lane check
            if cond_met and cond.get("enemy_left"):
                if len(metrics.get("opp_troops_left", [])) == 0 and metrics.get("last_opp_lane") != "left":
                    cond_met = False
                else:
                    threat_lane = "left"

            if cond_met and cond.get("enemy_right"):
                if len(metrics.get("opp_troops_right", [])) == 0 and metrics.get("last_opp_lane") != "right":
                    cond_met = False
                else:
                    threat_lane = "right"

            # If all conditions satisfied, check card and elixir!
            if cond_met:
                act_card = action.get("card")
                if not act_card or act_card not in deck:
                    sec_card = action.get("secondary_card")
                    if sec_card and sec_card in deck:
                        act_card = sec_card
                    else:
                        act_card = deck[0] if deck else "knight"

                # Check if card is affordable
                cost = CARD_CATALOG[act_card]["elixir"]
                if elixir >= cost:
                    # Determine target lane
                    req_lane = action.get("lane")
                    if req_lane == "opposite":
                        if threat_lane == "left":
                            target_lane = "right"
                        elif threat_lane == "right":
                            target_lane = "left"
                        else:
                            target_lane = "right" if preferred_lane == "left" else "left"
                    elif req_lane == "same":
                        target_lane = threat_lane or preferred_lane
                    elif req_lane == "lowest_hp_tower":
                        target_lane = lowest_hp_lane
                    elif req_lane in ["left", "right"]:
                        target_lane = req_lane
                    else:
                        target_lane = threat_lane or preferred_lane

                    # Anti-spam check: if we already have this defending troop active on that lane,
                    # check if a secondary card is available (e.g. "Deploy Baby Dragon and Skeletons"), otherwise let other rules/macro execute
                    sec_card = action.get("secondary_card")
                    if act_card in metrics.get(f"my_troops_{target_lane}", []):
                        if (sec_card and sec_card in deck
                            and elixir >= CARD_CATALOG[sec_card]["elixir"]
                            and sec_card not in metrics.get(f"my_troops_{target_lane}", [])):
                            act_card = sec_card
                        elif CARD_CATALOG[act_card].get("type") != "spell":
                            continue

                    return {
                        "card": act_card,
                        "lane": target_lane,
                        "thought": f"Directive Triggered: \"{raw_text}\" — Deploying {CARD_CATALOG[act_card]['name']} on {target_lane}.",
                        "taunt": skill.war_cry
                    }
                else:
                    # Condition met, but pooling elixir to play the designated counter!
                    # Do not waste elixir on a different random card; save up!
                    return {
                        "card": "none",
                        "lane": threat_lane or preferred_lane,
                        "thought": f"Saving elixir ({elixir:.1f}/{cost}e) for Directive: \"{raw_text}\".",
                        "taunt": ""
                    }

        # 2. DIRECT TOWER FINISHER WITH FIREBALL
        if "fireball" in deck and elixir >= 4.0:
            if not opp_left_dead and metrics["opp_left"] <= 380:
                return {
                    "card": "fireball",
                    "lane": "left",
                    "thought": f"Enemy left Princess Tower in lethal range ({metrics['opp_left']} HP) — Casting Fireball for the Crown!",
                    "taunt": skill.war_cry
                }
            if not opp_right_dead and metrics["opp_right"] <= 380:
                return {
                    "card": "fireball",
                    "lane": "right",
                    "thought": f"Enemy right Princess Tower in lethal range ({metrics['opp_right']} HP) — Casting Fireball for the Crown!",
                    "taunt": skill.war_cry
                }
            if (opp_left_dead or opp_right_dead) and metrics["opp_king"] <= 130:
                target_lane = "left" if opp_left_dead else "right"
                return {
                    "card": "fireball",
                    "lane": target_lane,
                    "thought": f"Enemy King Tower in lethal spell threshold ({metrics['opp_king']} HP). Firing for the 3-Crown KO!",
                    "taunt": "Victory is ours!"
                }

        # 3. DEFENSIVE RESPONSES TO INCOMING ENEMY THREATS
        for lane in ["left", "right"]:
            incoming = metrics.get(f"opp_troops_{lane}", [])
            if incoming:
                has_tank = any(c in ["giant", "pekka", "hog_rider"] for c in incoming)
                has_swarm = any(c in ["skeletons", "archers"] for c in incoming)

                if has_tank:
                    for defense_card in ["pekka", "skeletons", "musketeer", "knight"]:
                        if defense_card in deck and elixir >= CARD_CATALOG[defense_card]["elixir"]:
                            return {
                                "card": defense_card,
                                "lane": lane,
                                "thought": f"Interception order: Deploying {CARD_CATALOG[defense_card]['name']} on {lane} to neutralize incoming tank.",
                                "taunt": skill.war_cry
                            }

                if has_swarm:
                    for splash_card in ["baby_dragon", "fireball"]:
                        if splash_card in deck and elixir >= CARD_CATALOG[splash_card]["elixir"]:
                            return {
                                "card": splash_card,
                                "lane": lane,
                                "thought": f"Area suppression: Deploying {CARD_CATALOG[splash_card]['name']} to eliminate swarm on {lane}.",
                                "taunt": skill.war_cry
                            }

        # 4. FLANK COUNTER-ATTACKS
        opp_has_left = len(metrics.get("opp_troops_left", [])) > 0
        opp_has_right = len(metrics.get("opp_troops_right", [])) > 0
        counter_lane = None
        if opp_has_left and not opp_has_right and not opp_right_dead:
            counter_lane = "right"
        elif opp_has_right and not opp_has_left and not opp_left_dead:
            counter_lane = "left"

        if counter_lane:
            for flank_card in ["hog_rider", "goblin_barrel"]:
                if flank_card in deck and elixir >= CARD_CATALOG[flank_card]["elixir"]:
                    return {
                        "card": flank_card,
                        "lane": counter_lane,
                        "thought": f"Flank exploit: Opponent overcommitted. Blitzing {counter_lane} bridge with {CARD_CATALOG[flank_card]['name']}!",
                        "taunt": skill.war_cry
                    }

        # 5. MACRO PUSH BASED ON ARCHETYPE & DECK WEIGHTS
        target_push_lane = "right" if opp_left_dead and not opp_right_dead else ("left" if opp_right_dead and not opp_left_dead else preferred_lane)

        if elixir >= 7.5:
            if skill.archetype in ["beatdown", "balanced"] and "giant" in deck and elixir >= 5.0:
                return {
                    "card": "giant",
                    "lane": target_push_lane,
                    "thought": f"Macro Doctrine: {skill.archetype.upper()} push initiated with Giant on {target_push_lane}.",
                    "taunt": skill.war_cry
                }
            if skill.archetype in ["pekka_control", "control"] and "pekka" in deck and elixir >= 7.0:
                return {
                    "card": "pekka",
                    "lane": target_push_lane,
                    "thought": f"Macro Doctrine: Heavy armor advance with P.E.K.K.A on {target_push_lane}.",
                    "taunt": skill.war_cry
                }
            if "hog_rider" in deck and elixir >= 4.0:
                return {
                    "card": "hog_rider",
                    "lane": target_push_lane,
                    "thought": f"High tempo bridge charge with Hog Rider on {target_push_lane}.",
                    "taunt": skill.war_cry
                }

        # 6. CYCLE CHEAP CARDS
        if skill.archetype in ["cycle", "hog_cycle"] and elixir >= 4.0:
            for cheap in ["skeletons", "archers", "knight"]:
                if cheap in deck and elixir >= CARD_CATALOG[cheap]["elixir"]:
                    return {
                        "card": cheap,
                        "lane": target_push_lane,
                        "thought": f"Cycling {CARD_CATALOG[cheap]['name']} to sustain rotation cadence.",
                        "taunt": skill.war_cry
                    }

        # 7. HOLD ELIXIR
        if elixir < 4.0:
            return {
                "card": "none",
                "lane": target_push_lane,
                "thought": f"Pooling elixir ({elixir:.1f}/10) according to {skill.archetype} doctrine.",
                "taunt": ""
            }

        # 8. FALLBACK WEIGHTED PICK BASED ON CARD PRIORITIES
        affordable = [c for c in deck if CARD_CATALOG[c]["elixir"] <= elixir]
        if affordable:
            weights = [skill.card_priorities.get(c, 1.0) for c in affordable]
            chosen = random.choices(affordable, weights=weights, k=1)[0]
            return {
                "card": chosen,
                "lane": target_push_lane,
                "thought": f"Deploying {CARD_CATALOG[chosen]['name']} on {target_push_lane} per deck weighting ({skill.card_priorities.get(chosen, 0)*100:.0f}%).",
                "taunt": skill.war_cry
            }

        return {
            "card": "none",
            "lane": target_push_lane,
            "thought": "Holding position and saving elixir reserves.",
            "taunt": ""
        }

    def _sanitize_and_validate(self, text: str, skill: ClashSkillProfile, brief: str = "") -> Dict[str, Any]:
        tactical_order = self._tactical_heuristics(skill, brief)
        deck = [c for c in skill.deck if c in CARD_CATALOG]

        if not text or "ERROR:" in text:
            return tactical_order

        clean_text = text.strip()
        data = None

        try:
            data = json.loads(clean_text)
        except Exception:
            pass

        if not data:
            match = re.search(r"\{[\s\S]*\}", clean_text)
            if match:
                try:
                    data = json.loads(match.group(0))
                except Exception:
                    pass

        if not isinstance(data, dict):
            return self._heuristic_fallback(clean_text, skill, tactical_order)

        result = {}

        # Explicit tactical directive priority: if a participant's rule triggered, preserve it
        if tactical_order.get("thought", "").startswith("Directive Triggered:"):
            result["thought"] = tactical_order["thought"]
            result["card"] = tactical_order["card"]
            result["lane"] = tactical_order["lane"]
            result["taunt"] = tactical_order.get("taunt", skill.war_cry)
            return result

        raw_thought = str(data.get("thought", "")).strip()
        if raw_thought and len(raw_thought) > 10 and not any(bad in raw_thought.lower() for bad in ["json", "format", "here is", "i am an ai"]):
            result["thought"] = raw_thought[:130]
        else:
            result["thought"] = tactical_order["thought"]

        # Validate card strictly against the participant's deck!
        c = str(data.get("card", "none")).lower().strip()
        card_synonyms = {
            "hog": "hog_rider", "hogrider": "hog_rider",
            "dragon": "baby_dragon",
            "archer": "archers",
            "skeleton": "skeletons", "skarmy": "skeletons",
            "barrel": "goblin_barrel"
        }
        c = card_synonyms.get(c, c)

        # Ensure card is STRICTLY inside participant's 8-card deck!
        if c in deck:
            result["card"] = c
        elif c == "none":
            result["card"] = "none"
        else:
            result["card"] = tactical_order["card"]

        # Validate lane
        lane = str(data.get("lane", tactical_order["lane"])).lower().strip()
        result["lane"] = "right" if "right" in lane else "left"

        result["taunt"] = str(data.get("taunt", skill.war_cry))[:100]
        return result

    def _heuristic_fallback(self, text: str, skill: ClashSkillProfile, default: Dict[str, Any]) -> Dict[str, Any]:
        res = dict(default)
        t_low = text.lower()
        deck = [c for c in skill.deck if c in CARD_CATALOG]

        for card_id in deck:
            if card_id in t_low:
                res["card"] = card_id
                break

        if "right" in t_low:
            res["lane"] = "right"
        elif "left" in t_low:
            res["lane"] = "left"

        return res
