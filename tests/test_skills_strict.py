"""
Strict Individual Skill Adherence Test Suite.
Validates that:
1. Red and Blue commanders execute strictly according to their individually assigned/uploaded skill files.
2. Custom triggers from user-uploaded dossiers (Binary Brains, Ravis Descendants, etc.) parse and trigger accurately.
3. Target reference cards in action phrases (e.g. 'lane in which Pekka is deployed', 'onto enemy hog rider')
   are NOT extracted as secondary friendly deployment cards.
4. Friendly vs. enemy card attribution is isolated (e.g. 'my elixir >= 8 and enemy drops pekka' recognizes pekka as enemy).
5. Bridge-crossing conditions and tower HP percentage rules trigger accurately.
6. Each side strictly deploys only cards belonging to its own 8-card roster.
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.skill_loader import load_kingdom_skill_file, parse_tactical_trigger_rule
from engine.game_state import ClashGameState
from engine.battle_simulator import ClashBattleSimulator
from engine.llm_commander import LLMCommander
from engine.match_orchestrator import MatchOrchestrator

class TestStrictSkillAdherence(unittest.TestCase):

    def test_01_binary_brains_triggers_parsing(self):
        """Verifies that Binary Brains GODS AURA dossier parses all custom rules with correct targets."""
        skill = load_kingdom_skill_file("skills/Binary_Brains_GODS_AURA_.md")
        self.assertEqual(skill.name, "GODS_AURA")
        self.assertEqual(skill.author, "Binary_Brains")
        self.assertEqual(skill.preferred_lane, "left")
        self.assertEqual(len(skill.deck), 8)
        self.assertIn("pekka", skill.deck)
        self.assertIn("goblin_barrel", skill.deck)
        self.assertIn("fireball", skill.deck)

        # Rule 5: 'If opponent deploys PEKKA on a Lane -> Deploy Hog Rider on opposite Lane'
        # Secondary card MUST NOT be pekka (pekka was enemy target)
        r5 = next(t for t in skill.parsed_triggers if "Hog Rider on opposite Lane" in t["raw"])
        self.assertEqual(r5["action"]["card"], "hog_rider")
        self.assertIsNone(r5["action"].get("secondary_card"))
        self.assertEqual(r5["action"]["lane"], "opposite")

        # Rule 10: Tower under 10% HP triggers Fireball
        r10 = next(t for t in skill.parsed_triggers if "10%" in t["raw"])
        self.assertEqual(r10["cond"]["max_tower_hp_pct"], 10)
        self.assertEqual(r10["action"]["card"], "fireball")

    def test_02_ravis_descendants_triggers_parsing(self):
        """Verifies that Team ravidescendants dossier parses with bridge crossing and target awareness."""
        skill = load_kingdom_skill_file("skills/ravisdescendants.md")
        self.assertEqual(skill.name, "Hog rider control")
        self.assertEqual(skill.author, "Team ravidescendants")

        # Rule 5: 'IF Pekka deployed by the enemy -> Deploy Hog Rider on the opposite lane of the lane in which Pekka is deployed'
        r5 = next(t for t in skill.parsed_triggers if "Pekka deployed by the enemy" in t["raw"])
        self.assertEqual(r5["action"]["card"], "hog_rider")
        self.assertIsNone(r5["action"].get("secondary_card"))
        self.assertEqual(r5["action"]["lane"], "opposite")

        # Rule 8: 'IF Hog rider is deployed -> Deploy skeletons directly on to the enemy hog rider after it crosses the bridge'
        r8 = next(t for t in skill.parsed_triggers if "enemy hog rider after it crosses" in t["raw"])
        self.assertEqual(r8["action"]["card"], "skeletons")
        self.assertIsNone(r8["action"].get("secondary_card"))
        self.assertTrue(r8["cond"].get("cross_bridge"))

        # Rule 9: 'IF my elixer is greater than 8 -> Drop Hog rider and Baby dragon in the side of the enemy princess tower with the least HP'
        r9 = next(t for t in skill.parsed_triggers if "greater than 8" in t["raw"])
        self.assertEqual(r9["cond"]["min_elixir"], 8.0)
        self.assertEqual(r9["action"]["card"], "hog_rider")
        self.assertEqual(r9["action"]["secondary_card"], "baby_dragon")
        self.assertEqual(r9["action"]["lane"], "lowest_hp_tower")

    def test_03_friendly_vs_enemy_attribution_isolation(self):
        """Ensures 'my elixir' does not falsely mark enemy units as friendly."""
        rule = parse_tactical_trigger_rule("IF my elixir >= 7 and enemy drops pekka -> deploy pekka on same lane")
        self.assertNotIn("friendly_card", rule["cond"])
        self.assertEqual(rule["cond"]["enemy_cards"], ["pekka"])
        self.assertTrue(rule["cond"]["enemy_tank"])
        self.assertEqual(rule["cond"]["min_elixir"], 7.0)
        self.assertEqual(rule["action"]["card"], "pekka")

    def test_04_head_to_head_individual_commander_execution(self):
        """Runs a dual-commander simulation verifying both Red and Blue follow strictly their respective dossiers."""
        orchestrator = MatchOrchestrator()
        orchestrator.setup_match(
            "skills/Binary_Brains_GODS_AURA_.md",
            "skills/ravisdescendants.md",
            max_duration_seconds=60
        )

        red_skill = orchestrator.red_skill
        blue_skill = orchestrator.blue_skill

        self.assertEqual(red_skill.name, "GODS_AURA")
        self.assertEqual(blue_skill.name, "Hog rider control")

        cmd = LLMCommander()

        # Test Red reaction to enemy Knight: Binary Brains Rule 1 says deploy Skeletons
        red_brief = """CLASH ARENA BRIEF (RED):
Time: 10s / 60s
Your Elixir: 5.0/10 | Crowns: 0
Your Towers: Left Princess=1400HP, Right Princess=1400HP, King=2400HP
Enemy Towers: Left Princess=1400HP, Right Princess=1400HP, King=2400HP
Your Active Troops: 0 (None)
Enemy Incoming Troops: 1 (Knight on left [crossed bridge])
Available Cards in Deck: pekka, goblin_barrel, baby_dragon, fireball, hog_rider, skeletons, knight, musketeer"""

        red_order = cmd._generate_order_sync(red_skill, "red", red_brief)
        self.assertEqual(red_order["card"], "skeletons")
        self.assertIn("Directive Triggered", red_order["thought"])

        # Test Blue reaction when elixir > 8: Ravis Descendants Rule 9 says Drop Hog rider on least HP tower
        blue_brief = """CLASH ARENA BRIEF (BLUE):
Time: 20s / 60s
Your Elixir: 9.0/10 | Crowns: 0
Your Towers: Left Princess=1400HP, Right Princess=1400HP, King=2400HP
Enemy Towers: Left Princess=800HP, Right Princess=1400HP, King=2400HP
Your Active Troops: 0 (None)
Enemy Incoming Troops: 0 (None)
Available Cards in Deck: hog_rider, musketeer, knight, fireball, skeletons, giant, baby_dragon, pekka"""

        blue_order = cmd._generate_order_sync(blue_skill, "blue", blue_brief)
        self.assertEqual(blue_order["card"], "hog_rider")
        self.assertEqual(blue_order["lane"], "left")  # 800 HP vs 1400 HP
        self.assertIn("Directive Triggered", blue_order["thought"])

    def test_05_deck_roster_containment(self):
        """Verifies that commanders never deploy cards outside their 8-card roster."""
        orchestrator = MatchOrchestrator()
        orchestrator.setup_match(
            "skills/Binary_Brains_GODS_AURA_.md",
            "skills/ravisdescendants.md",
            max_duration_seconds=30
        )

        cmd = LLMCommander()
        state = orchestrator.state
        sim = orchestrator.simulator
        state.status = "running"

        # Run 20 rounds of autonomous execution
        for _ in range(20):
            r_brief = state.get_situational_brief("red")
            b_brief = state.get_situational_brief("blue")

            r_order = cmd._generate_order_sync(orchestrator.red_skill, "red", r_brief)
            b_order = cmd._generate_order_sync(orchestrator.blue_skill, "blue", b_brief)

            if r_order["card"] != "none":
                self.assertIn(r_order["card"], orchestrator.red_skill.deck)
            if b_order["card"] != "none":
                self.assertIn(b_order["card"], orchestrator.blue_skill.deck)

            sim.execute_round(r_order, b_order, round_delta_seconds=1.0)

if __name__ == "__main__":
    unittest.main()
