# Social class entities (managers)
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from .individual import IndividualData, IndividualRole

class ClassEntityData(BaseModel):
    """Entitate de clasă socială: administrează cohorta de indivizi."""
    id: str              # ex: "S1.WORK"
    state_id: str
    name: str            # eticheta clasei (Workers, Politicians etc.)
    doctrine: Dict[str, float] = Field(default_factory=dict)  # ex. strike_threshold
    budget: float = 0.0
    satisfaction: float = 0.5
    influence: float = 0.5
    agents: Dict[str, IndividualData] = Field(default_factory=dict)

    def spawn_agent(self, agent: IndividualData) -> None:
        """
        Tool: Add a new agent to the class cohort.
        Parameters:
            agent (IndividualData): The agent to add
        Returns:
            None
        """
        self.agents[agent.id] = agent

    def retire_agent(self, agent_id: str) -> bool:
        """
        Tool: Remove an agent from the class cohort.
        Parameters:
            agent_id (str): The ID of the agent to remove
        Returns:
            bool: True if the agent was removed, False otherwise
        """
        return self.agents.pop(agent_id, None) is not None

    def aggregate_demands(self) -> Dict[str, float]:
        """
        Tool: Aggregate social pressures, lobbying, covert impact, and output for the class cohort.
        Parameters:
            None
        Returns:
            Dict[str, float]: Dictionary with keys 'pressure', 'lobby', 'covert', 'output'
        """
        if not self.agents:
            return {"pressure": 0.0, "lobby": 0.0, "covert": 0.0, "output": 0.0}

        pressure = sum(a.protest_pressure() for a in self.agents.values()) / max(1, len(self.agents))
        lobby = sum(a.lobby_weight() for a in self.agents.values()) / max(1, len(self.agents))
        covert = sum(a.covert_impact() for a in self.agents.values()) / max(1, len(self.agents))
        output = sum(a.produce_output() for a in self.agents.values())  # total, nu medie

        # satisfacția clasei – foarte grosier
        self.satisfaction = max(0.0, min(1.0, 1.0 - pressure + 0.3 * lobby))
        return {"pressure": pressure, "lobby": lobby, "covert": covert, "output": output}
