# Global WorldState object (stocks, relations, tick)
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Dict, List, Any
from .state import StateAgentData
from .communication import Message

class WorldState(BaseModel):
    """Starea globală a lumii; punctul unic de adevăr pentru simulare."""
    tick: int = 0
    states: Dict[str, StateAgentData] = Field(default_factory=dict)
    contracts: List[dict] = Field(default_factory=list)  # trade / treaties
    events: List[dict] = Field(default_factory=list)
    rng_seed: int = 42

    def snapshot(self) -> dict:
        """
        Tool: Get a snapshot of the current world state.
        Parameters:
            None
        Returns:
            dict: Dictionary containing tick, states, contracts, and events
        """
        return {
            "tick": self.tick,
            "states": {sid: {
                "traits": s.traits,
                "inventory": s.inventory,
                "population": s.population,
                "morale": s.morale,
                "army": s.army.dict(),
                "policies": s.policies,
                "relations": s.relations,
                "classes": list(s.classes.keys())
            } for sid, s in self.states.items()},
            "contracts": self.contracts[-10:],
            "events": self.events[-10:],
        }

    def apply_deltas(self, deltas: Dict[str, Any]) -> None:
        """
        Tool: Apply effects to states at the end of a tick.
        Parameters:
            deltas (Dict[str, Any]): Dictionary of changes per state
        Returns:
            None
        """
        for sid, changes in deltas.items():
            st = self.states.get(sid)
            if not st:
                continue
            inv = changes.get("inventory", {})
            for k, v in inv.items():
                st.add_resource(k, v)
            if "morale" in changes:
                st.adjust_morale(changes["morale"])

    def log_tick(self) -> dict:
        """
        Tool: Log the current tick's snapshot.
        Parameters:
            None
        Returns:
            dict: Snapshot of the world state for the current tick
        """
        snap = self.snapshot()
        return snap  # upstream: salvezi JSON; aici doar îl returnăm
