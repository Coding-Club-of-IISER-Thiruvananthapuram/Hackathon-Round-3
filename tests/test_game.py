"""
Comprehensive test suite for Clash Royale 1v1 Autonomous Arena.
Verifies:
1. Game state initialization (King Tower 2400 HP, Princess Towers 1400 HP, 5 Elixir)
2. Elixir regeneration and Double Elixir activation
3. Card deployment and Elixir deduction
4. 2-Lane bridge marching & troop movement
5. Princess & King tower defense targeting
6. Princess Tower destruction & Crown awards & King activation
7. Instant 3-Crown KO on King Tower destruction
8. Direct spell strikes (Fireball)
9. Knockout tournament progression
10. Markdown skill & deck parsing
11. Server health check and API endpoints
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.config import CARD_CATALOG, MAX_ELIXIR
from engine.game_state import ClashGameState, ClashTroop
from engine.battle_simulator import ClashBattleSimulator
from engine.tournament_manager import TournamentManager
from engine.skill_loader import load_kingdom_skill_file, list_available_kingdom_skills, validate_kingdom_skill_content
from engine.match_orchestrator import MatchOrchestrator
from engine.llm_commander import LLMCommander
from server.app import get_skills, health_check, validate_skill, SkillValidateRequest, get_cards

class TestClashRoyaleArena(unittest.TestCase):

    def test_01_initial_arena_state(self):
        state = ClashGameState()
        self.assertEqual(state.status, "not_started")
        self.assertEqual(state.players["red"].elixir, 5.0)
        self.assertEqual(state.players["blue"].elixir, 5.0)
        self.assertEqual(state.players["red"].crowns, 0)

        # Check Towers
        red_towers = state.players["red"].towers
        self.assertEqual(red_towers["king"]["hp"], 2400)
        self.assertFalse(red_towers["king"]["active"])  # King sleeps until attacked or princess falls
        self.assertEqual(red_towers["left_princess"]["hp"], 1400)
        self.assertEqual(red_towers["right_princess"]["hp"], 1400)

    def test_02_elixir_and_card_deployment(self):
        state = ClashGameState()
        sim = ClashBattleSimulator(state)
        state.status = "running"

        # Red plays Giant (cost 5) on left lane
        # Blue plays Knight (cost 3) on right lane
        sim.execute_round(
            {"card": "giant", "lane": "left"},
            {"card": "knight", "lane": "right"},
            round_delta_seconds=1.0
        )

        # 5 elixir - 5 + 0.5 regen = 0.5 for Red
        self.assertAlmostEqual(state.players["red"].elixir, 0.5, delta=0.1)
        # 5 elixir - 3 + 0.5 regen = 2.5 for Blue
        self.assertAlmostEqual(state.players["blue"].elixir, 2.5, delta=0.1)

        # Troops spawned in lanes
        self.assertEqual(len(state.troops), 2)
        red_troops = [t for t in state.troops if t.team == "red"]
        blue_troops = [t for t in state.troops if t.team == "blue"]
        self.assertEqual(red_troops[0].card_id, "giant")
        self.assertEqual(red_troops[0].lane, "left")
        self.assertEqual(blue_troops[0].card_id, "knight")
        self.assertEqual(blue_troops[0].lane, "right")

    def test_03_troop_movement_across_bridges(self):
        state = ClashGameState()
        sim = ClashBattleSimulator(state)
        state.status = "running"

        # Spawn red troop on left lane
        red_hog = ClashTroop("hog_rider", "red", "left", 28.0)
        state.troops.append(red_hog)

        # Step forward
        sim.execute_round({"card": "none"}, {"card": "none"}, round_delta_seconds=2.0)

        # Red hog should have moved DOWN the lane towards blue towers
        self.assertGreater(red_hog.y, 28.0)

    def test_04_tower_attacks_and_princess_fall(self):
        state = ClashGameState()
        sim = ClashBattleSimulator(state)
        state.status = "running"

        # Position low-HP blue princess tower
        state.players["blue"].towers["left_princess"]["hp"] = 50

        # Place red attacker right at the blue princess tower
        attacker = ClashTroop("knight", "red", "left", 78.0)
        state.troops.append(attacker)

        sim.execute_round({"card": "none"}, {"card": "none"}, round_delta_seconds=1.0)

        # Left princess tower should be destroyed
        self.assertTrue(state.players["blue"].towers["left_princess"]["destroyed"])
        # Red should be awarded 1 Crown
        self.assertEqual(state.players["red"].crowns, 1)
        # Blue King tower should now be activated!
        self.assertTrue(state.players["blue"].towers["king"]["active"])

    def test_05_instant_3_crown_ko(self):
        state = ClashGameState()
        sim = ClashBattleSimulator(state)
        state.status = "running"

        # Blue King Tower has low HP and left princess is already down
        state.players["blue"].towers["left_princess"]["destroyed"] = True
        state.players["blue"].towers["king"]["hp"] = 80
        state.players["blue"].towers["king"]["active"] = True

        # Red Giant attacks King Tower (positioned at King Tower x=50.0, y=92.0)
        giant = ClashTroop("giant", "red", "left", 92.0, x_pos=50.0)
        state.troops.append(giant)

        sim.execute_round({"card": "none"}, {"card": "none"}, round_delta_seconds=1.0)

        self.assertEqual(state.status, "finished")
        self.assertEqual(state.winner, "red")
        self.assertEqual(state.players["red"].crowns, 3)
        self.assertIn("3-CROWN", state.win_reason)

    def test_06_fireball_spell_direct_strike(self):
        state = ClashGameState()
        sim = ClashBattleSimulator(state)
        state.status = "running"
        state.players["red"].elixir = 8.0

        initial_hp = state.players["blue"].towers["left_princess"]["hp"]

        # Red casts Fireball on blue left tower
        sim.execute_round(
            {"card": "fireball", "lane": "left"},
            {"card": "none"},
            round_delta_seconds=1.0
        )

        # Tower should take direct spell damage
        self.assertLess(state.players["blue"].towers["left_princess"]["hp"], initial_hp)

    def test_07_double_elixir_activation(self):
        state = ClashGameState()
        sim = ClashBattleSimulator(state)
        state.status = "running"
        state.elapsed_seconds = 125.0  # Past 120s

        sim.execute_round({"card": "none"}, {"card": "none"}, round_delta_seconds=1.0)
        self.assertTrue(state.is_double_elixir)

    def test_08_deck_and_skill_parsing(self):
        skills = list_available_kingdom_skills("skills")
        self.assertGreaterEqual(len(skills), 4)

        hog_profile = load_kingdom_skill_file("skills/hog_cycle.md")
        self.assertEqual(hog_profile.archetype, "hog_cycle")
        self.assertIn("hog_rider", hog_profile.deck)

        prompt = hog_profile.generate_system_prompt("red")
        self.assertIn("HOG_CYCLE", prompt)
        self.assertIn("hog_rider", prompt)

    def test_09_tournament_bracket_progression(self):
        tm = TournamentManager("Clash Knockout Cup")
        bracket = tm.create_knockout_bracket(["hog_cycle.md", "giant_beatdown.md", "spell_bait.md", "pekka_control.md"])

        self.assertIn("semi_1", bracket["matches"])
        self.assertIn("final_1", bracket["matches"])

        tm.record_match_result(
            "semi_1",
            winner_file="hog_cycle.md",
            winner_name="The Hog Master",
            loser_file="giant_beatdown.md",
            scorecard={"red_crowns": 2, "blue_crowns": 1, "winner": "red"}
        )
        self.assertEqual(tm.matches["final_1"].team_a_file, "hog_cycle.md")

    def test_10_server_api_health_and_skills(self):
        h = health_check()
        self.assertEqual(h["status"], "healthy")

        cards = get_cards()
        self.assertIsInstance(cards, dict)
        self.assertEqual(len(cards), 10)
        self.assertIn("hog_rider", cards)
        self.assertIn("pekka", cards)

        s = get_skills()
        self.assertIsInstance(s, list)
        self.assertGreaterEqual(len(s), 4)

        val = validate_skill(SkillValidateRequest(content="# Deck Name: Test Deck\n## 8-Card Battle Deck\n- hog_rider: 50%"))
        self.assertTrue(val["valid"])

    def test_11_skill_file_custom_trigger_execution(self):
        from engine.skill_loader import parse_clash_skill
        from engine.llm_commander import LLMCommander

        custom_md = """# Deck Name: Lightning Counter
# Player: Cyber Valkyrie
# War Cry: Thunder Strikes!
## Archetype
pekka_control
## 8-Card Battle Deck
- P.E.K.K.A: 40%
- Goblin Barrel: 20%
- Baby Dragon: 10%
- Musketeer: 10%
- Knight: 10%
- Skeletons: 5%
- Archers: 5%
- Fireball: 0%
## Preferred Lane
right
## Tactical Triggers
1. IF enemy deploys Giant or Hog -> Drop P.E.K.K.A immediately!
2. IF Elixir >= 8 -> Deploy Goblin Barrel!
"""
        skill = parse_clash_skill(custom_md)
        self.assertEqual(skill.deck[0], "pekka")
        self.assertEqual(skill.deck[1], "goblin_barrel")
        self.assertEqual(len(skill.parsed_triggers), 2)

        brief_threat = """CLASH ARENA BRIEF (BLUE):
Time: 40s / 180s
Your Elixir: 8.0/10 | Crowns: 0
Your Towers: Left Princess=1400HP, Right Princess=1400HP, King=2400HP
Enemy Towers: Left Princess=1400HP, Right Princess=1400HP, King=2400HP
Your Active Troops: 0 (None)
Enemy Incoming Troops: 1 (Giant on left)
Available Cards in Deck: pekka, goblin_barrel, baby_dragon, musketeer, knight, skeletons, archers, fireball"""

        cmd = LLMCommander()
        order = cmd._generate_order_sync(skill, "blue", brief_threat)
        self.assertEqual(order["card"], "pekka")
        self.assertEqual(order["lane"], "left")
        self.assertIn("Thunder Strikes!", order["taunt"])
        self.assertIn("Directive Triggered", order["thought"])

    def test_12_deck_roster_adherence(self):
        from engine.skill_loader import parse_clash_skill
        from engine.llm_commander import LLMCommander

        # Deck without Hog Rider or Giant
        custom_md = """# Deck Name: Swarm & Siege
## 8-Card Battle Deck
- Skeletons: 50%
- Archers: 20%
- Knight: 10%
- Musketeer: 10%
- Baby Dragon: 10%
- Fireball: 0%
- Goblin Barrel: 0%
- P.E.K.K.A: 0%
"""
        skill = parse_clash_skill(custom_md)
        cmd = LLMCommander()
        brief = "Your Elixir: 5.0/10 | Enemy Incoming Troops: 0 (None)"
        order = cmd._generate_order_sync(skill, "red", brief)
        self.assertIn(order["card"], skill.deck)

    def test_13_diagonal_king_pathing(self):
        state = ClashGameState()
        sim = ClashBattleSimulator(state)
        state.status = "running"

        # Blue Left Princess is destroyed
        state.players["blue"].towers["left_princess"]["destroyed"] = True

        # Red Hog Rider starts in left lane (x=25.0, y=70.0)
        hog = ClashTroop("hog_rider", "red", "left", 70.0)
        self.assertEqual(hog.x, 25.0)
        state.troops.append(hog)

        # Advance simulation
        sim.execute_round({"card": "none"}, {"card": "none"}, round_delta_seconds=1.0)

        # Hog Rider should have steered diagonally inward towards King Tower at x=50.0!
        self.assertGreater(hog.x, 25.0)
        self.assertGreater(hog.y, 70.0)

    def test_14_tower_physical_collision_buffer(self):
        import math
        from engine.config import KING_TOWER_RADIUS
        state = ClashGameState()
        sim = ClashBattleSimulator(state)
        state.status = "running"

        # Blue Princess towers already down, Blue Hog Rider marches onto Red King Tower
        state.players["red"].towers["left_princess"]["destroyed"] = True
        state.players["red"].towers["king"]["active"] = True

        # Blue Hog Rider starts close to Red King Tower (50.0, 7.0)
        hog = ClashTroop("hog_rider", "blue", "left", 20.0, x_pos=50.0)
        state.troops.append(hog)

        # Run several rounds of movement & attacks
        for _ in range(5):
            sim.execute_round({"card": "none"}, {"card": "none"}, round_delta_seconds=1.0)

        king = state.players["red"].towers["king"]
        dist_to_king = math.hypot(hog.x - king["x"], hog.y - king["y"])

        # Hog Rider MUST maintain a physical standoff distance outside the King Keep radius
        self.assertGreaterEqual(dist_to_king, KING_TOWER_RADIUS)
        self.assertGreater(hog.y, king["y"])  # Blue attacker stays in front/south of Red King Tower

    def test_15_naked_hog_balance_cannot_solo_kill_tower(self):
        state = ClashGameState()
        sim = ClashBattleSimulator(state)
        state.status = "running"

        # Blue deploys a naked Hog Rider at the river bridge (left lane, y=50.0)
        hog = ClashTroop("hog_rider", "blue", "left", 50.0)
        state.troops.append(hog)

        # Simulate until Hog Rider dies or 15 seconds pass
        for _ in range(15):
            sim.execute_round({"card": "none"}, {"card": "none"}, round_delta_seconds=1.0)
            if hog.hp <= 0 or hog not in state.troops:
                break

        red_tower = state.players["red"].towers["left_princess"]

        # The Hog Rider MUST be eliminated by the tower!
        self.assertLessEqual(hog.hp, 0)
        # The 1400 HP Princess Tower MUST survive (taking chip damage, but NOT destroyed!)
        self.assertFalse(red_tower["destroyed"])
        self.assertGreater(red_tower["hp"], 500)

    def test_16_defending_troops_intercept_combat_attackers(self):
        state = ClashGameState()
        sim = ClashBattleSimulator(state)
        state.status = "running"

        tower = state.players["red"].towers["left_princess"]
        tower_initial_hp = tower["hp"]

        # Blue Knight is right at Red Left Princess Tower (reach is 4.5 + 3.0 = 7.5; y=27.0)
        blue_knight = ClashTroop("knight", "blue", "left", 27.0)
        state.troops.append(blue_knight)

        # Red drops a defending Knight in front of the tower (y=26.5)
        red_knight = ClashTroop("knight", "red", "left", 26.5)
        state.troops.append(red_knight)

        # Execute 1 round
        sim.execute_round({"card": "none"}, {"card": "none"}, round_delta_seconds=1.0)

        # Blue Knight should engage Red Knight, NOT the tower!
        self.assertEqual(tower["hp"], tower_initial_hp)
        self.assertLess(red_knight.hp, red_knight.max_hp)


if __name__ == "__main__":
    unittest.main()
