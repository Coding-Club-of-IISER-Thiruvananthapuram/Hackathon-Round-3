"""
Automated Card Balance & Monte Carlo Rollout Benchmark Test Suite.
Tests:
1. Monte Carlo Deck vs Deck Rollout Simulations
2. Elixir Trade Ratios and Card Efficiency
3. Head-to-Head Card Matchups
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.config import CARD_CATALOG
from engine.game_state import ClashGameState
from engine.battle_simulator import ClashBattleSimulator
from engine.skill_loader import load_kingdom_skill_file
from server.app import simulate_rollout, RolloutSimRequest

class TestClashBalanceBenchmark(unittest.TestCase):

    def test_01_monte_carlo_rollout_endpoint(self):
        """Tests that fast-forward Monte Carlo simulation computes win rates without error."""
        req = RolloutSimRequest(
            red_skill_file="hog_cycle.md",
            blue_skill_file="giant_beatdown.md",
            num_simulations=5,
            max_duration_seconds=60
        )
        res = simulate_rollout(req)
        self.assertEqual(res["num_simulations"], 5)
        self.assertIn("win_rate_red", res)
        self.assertIn("win_rate_blue", res)
        self.assertEqual(res["red_wins"] + res["blue_wins"] + res["draws"], 5)

    def test_02_card_catalog_elixir_costs(self):
        """Verifies that all 10 catalog cards have valid non-zero elixir costs."""
        for card_id, proto in CARD_CATALOG.items():
            self.assertGreater(proto["elixir"], 0, f"Card {card_id} has invalid elixir cost!")
            if proto.get("type") != "spell":
                self.assertIn("hp", proto)
            self.assertIn("damage", proto)

    def test_03_head_to_head_duel_sim(self):
        """Runs a 1v1 automated battle between P.E.K.K.A Control and Hog Cycle."""
        state = ClashGameState(max_duration_seconds=30)
        state.status = "running"
        sim = ClashBattleSimulator(state)

        for _ in range(15):
            sim.execute_round(
                {"card": "pekka", "lane": "left"},
                {"card": "hog_rider", "lane": "right"},
                round_delta_seconds=1.0
            )

        self.assertGreater(state.elapsed_seconds, 0)
        self.assertIn(state.status, ["running", "finished"])

if __name__ == "__main__":
    unittest.main()
