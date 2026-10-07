"""
Knockout Tournament Manager.
Manages single-elimination brackets, match seeding, automatic progression,
and match scoring.
"""
import os
import json
import uuid
from typing import Dict, List, Any, Optional

class TournamentMatch:
    def __init__(
        self,
        match_id: str,
        round_name: str,  # e.g., "Quarterfinal 1", "Semifinal 1", "Championship Final"
        team_a_file: Optional[str] = None,
        team_b_file: Optional[str] = None,
        next_match_id: Optional[str] = None,
        next_slot: int = 0  # 0 for team A in next match, 1 for team B
    ):
        self.match_id = match_id
        self.round_name = round_name
        self.team_a_file = team_a_file
        self.team_b_file = team_b_file
        self.winner_file: Optional[str] = None
        self.loser_file: Optional[str] = None
        self.winner_name: Optional[str] = None
        self.status = "scheduled"  # "scheduled", "in_progress", "completed"
        self.next_match_id = next_match_id
        self.next_slot = next_slot
        self.scorecard: Dict[str, Any] = {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "match_id": self.match_id,
            "round_name": self.round_name,
            "team_a_file": self.team_a_file,
            "team_b_file": self.team_b_file,
            "winner_file": self.winner_file,
            "loser_file": self.loser_file,
            "winner_name": self.winner_name,
            "status": self.status,
            "next_match_id": self.next_match_id,
            "next_slot": self.next_slot,
            "scorecard": self.scorecard
        }


class TournamentManager:
    def __init__(self, tournament_name: str = "Arena Championship"):
        self.tournament_id = f"tourney_{uuid.uuid4().hex[:8]}"
        self.tournament_name = tournament_name
        self.matches: Dict[str, TournamentMatch] = {}
        self.champion: Optional[str] = None
        self.rounds_order: List[str] = []

    def create_knockout_bracket(self, participant_files: List[str]) -> Dict[str, Any]:
        """
        Creates a balanced single-elimination bracket for 2, 4, or 8 participants.
        Automatically sets up Quarterfinals, Semifinals, and Grand Finals.
        """
        self.matches = {}
        self.champion = None
        n = len(participant_files)

        if n < 2:
            raise ValueError("Need at least 2 participants for a knockout tournament.")

        # 2 Participants: Direct Grand Championship Final
        if n == 2:
            final_id = "final_1"
            self.matches[final_id] = TournamentMatch(
                final_id, "Grand Championship Final",
                team_a_file=participant_files[0],
                team_b_file=participant_files[1]
            )
            self.rounds_order = [final_id]

        # 3 Participants: 1 Semifinal + 1 Bye into Final
        elif n == 3:
            final_id = "final_1"
            semi1_id = "semi_1"
            self.matches[final_id] = TournamentMatch(
                final_id, "Grand Championship Final",
                team_a_file=participant_files[0]
            )
            self.matches[semi1_id] = TournamentMatch(
                semi1_id, "Semifinal 1",
                team_a_file=participant_files[1],
                team_b_file=participant_files[2],
                next_match_id=final_id,
                next_slot=1
            )
            self.rounds_order = [semi1_id, final_id]

        # 4 Participants: 2 Semifinals -> 1 Final
        elif n <= 4:
            final_id = "final_1"
            self.matches[final_id] = TournamentMatch(final_id, "Grand Championship Final")

            semi1_id = "semi_1"
            semi2_id = "semi_2"
            
            p0 = participant_files[0] if len(participant_files) > 0 else None
            p1 = participant_files[1] if len(participant_files) > 1 else None
            p2 = participant_files[2] if len(participant_files) > 2 else None
            p3 = participant_files[3] if len(participant_files) > 3 else None

            self.matches[semi1_id] = TournamentMatch(
                semi1_id, "Semifinal 1", team_a_file=p0, team_b_file=p1,
                next_match_id=final_id, next_slot=0
            )
            self.matches[semi2_id] = TournamentMatch(
                semi2_id, "Semifinal 2", team_a_file=p2, team_b_file=p3,
                next_match_id=final_id, next_slot=1
            )
            self.rounds_order = [semi1_id, semi2_id, final_id]

        else:
            # 8-team Quarterfinals -> Semifinals -> Finals
            final_id = "final_1"
            self.matches[final_id] = TournamentMatch(final_id, "Grand Championship Final")

            semi1_id = "semi_1"
            semi2_id = "semi_2"
            self.matches[semi1_id] = TournamentMatch(semi1_id, "Semifinal 1", next_match_id=final_id, next_slot=0)
            self.matches[semi2_id] = TournamentMatch(semi2_id, "Semifinal 2", next_match_id=final_id, next_slot=1)

            # 4 Quarterfinals
            q_ids = ["qf_1", "qf_2", "qf_3", "qf_4"]
            for i, qid in enumerate(q_ids):
                target_semi = semi1_id if i < 2 else semi2_id
                target_slot = i % 2
                idx_a = i * 2
                idx_b = i * 2 + 1
                pa = participant_files[idx_a] if idx_a < len(participant_files) else None
                pb = participant_files[idx_b] if idx_b < len(participant_files) else None
                self.matches[qid] = TournamentMatch(
                    qid, f"Quarterfinal {i+1}", team_a_file=pa, team_b_file=pb,
                    next_match_id=target_semi, next_slot=target_slot
                )

            self.rounds_order = q_ids + [semi1_id, semi2_id, final_id]

        return self.to_dict()

    def record_match_result(
        self,
        match_id: str,
        winner_file: str,
        winner_name: str,
        loser_file: str,
        scorecard: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Records the winner of a knockout match and advances them to the next bracket round!
        """
        if match_id not in self.matches:
            raise KeyError(f"Match not found: {match_id}")

        match = self.matches[match_id]
        match.status = "completed"
        match.winner_file = winner_file
        match.winner_name = winner_name
        match.loser_file = loser_file
        match.scorecard = scorecard

        # Advance winner to next match in bracket
        if match.next_match_id and match.next_match_id in self.matches:
            next_m = self.matches[match.next_match_id]
            if match.next_slot == 0:
                next_m.team_a_file = winner_file
            else:
                next_m.team_b_file = winner_file
        elif match_id == "final_1":
            # Grand Champion crowned!
            self.champion = winner_name

        return self.to_dict()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tournament_id": self.tournament_id,
            "tournament_name": self.tournament_name,
            "champion": self.champion,
            "rounds_order": self.rounds_order,
            "matches": {k: v.to_dict() for k, v in self.matches.items()}
        }

    def export_to_file(self, filepath: str = "tournament_state.json"):
        """Saves bracket state to JSON so organizers can transfer results between laptops."""
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    def import_from_dict(self, data: Dict[str, Any]):
        """Loads bracket state directly from dictionary."""
        self.tournament_id = data.get("tournament_id", self.tournament_id)
        self.tournament_name = data.get("tournament_name", self.tournament_name)
        self.champion = data.get("champion")
        self.rounds_order = data.get("rounds_order", [])
        self.matches = {}

        for mid, mdata in data.get("matches", {}).items():
            m = TournamentMatch(
                match_id=mdata["match_id"],
                round_name=mdata["round_name"],
                team_a_file=mdata.get("team_a_file"),
                team_b_file=mdata.get("team_b_file"),
                next_match_id=mdata.get("next_match_id"),
                next_slot=mdata.get("next_slot", 0)
            )
            m.winner_file = mdata.get("winner_file")
            m.loser_file = mdata.get("loser_file")
            m.winner_name = mdata.get("winner_name")
            m.status = mdata.get("status", "scheduled")
            m.scorecard = mdata.get("scorecard", {})
            self.matches[mid] = m

    def import_from_file(self, filepath: str = "tournament_state.json"):
        """Loads bracket state from JSON."""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Tournament file not found: {filepath}")
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.import_from_dict(data)
