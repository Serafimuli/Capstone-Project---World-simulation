# ArbiterAgent – controls creation/deletion of states
from __future__ import annotations
from pydantic import BaseModel
from typing import Dict, List, Optional
from .state import StateAgentData
from .class_entity import ClassEntityData
from .individual import IndividualData
from .world_state import WorldState

class ArbiterCore(BaseModel):
    """Arbitru la nivel de domeniu (fără LLM) – creează/șterge state, aplică evenimente globale."""
    allowed_prefix: str = "S"
    next_state_index: int = 1

    def create_state(self, world: "WorldState", traits: Optional[List[str]] = None) -> str:
        """
        Tool: Create a new state in the world.
        Parameters:
            world (WorldState): The world state object
            traits (Optional[List[str]]): List of traits for the new state
        Returns:
            str: The ID of the newly created state
        """
        sid = f"{self.allowed_prefix}{self.next_state_index}"
        self.next_state_index += 1
        world.states[sid] = StateAgentData(id=sid, traits=traits or [], population=500_000)
        return sid

    def delete_state(self, world: "WorldState", state_id: str) -> bool:
        """
        Tool: Delete a state from the world.
        Parameters:
            world (WorldState): The world state object
            state_id (str): The ID of the state to delete
        Returns:
            bool: True if the state was deleted, False otherwise
        """
        return world.states.pop(state_id, None) is not None

    def apply_world_event(self, world: "WorldState", event_type: str, payload: dict) -> None:
        """
        Tool: Apply a global event to all states in the world.
        Parameters:
            world (WorldState): The world state object
            event_type (str): Type of event (e.g., 'pandemic', 'embargo')
            payload (dict): Event data
        Returns:
            None
        """
        # exemplu: {"type": "pandemic", "morale_delta": -0.05}
        if event_type == "pandemic":
            for s in world.states.values():
                s.adjust_morale(payload.get("morale_delta", -0.05))
        elif event_type == "embargo":
            for s in world.states.values():
                # embargo -> reducere resurse comerciale (foarte simplificat)
                for k in list(s.inventory.keys()):
                    s.inventory[k] *= 0.98
        world.events.append({"tick": world.tick, "type": event_type, "payload": payload})
