# StateAgent – resources, morale, population, politics
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Dict, List
from .class_entity import ClassEntityData

class ArmyData(BaseModel):
    soldiers: int = 0
    readiness: float = 0.5  # 0..1
    tech: float = 0.5       # 0..1

class StateAgentData(BaseModel):
    id: str                 # "S1"
    traits: List[str] = Field(default_factory=list)
    inventory: Dict[str, float] = Field(default_factory=dict)
    population: int = 0
    morale: float = 0.5
    army: ArmyData = ArmyData()
    policies: Dict[str, float] = Field(default_factory=dict)  # ex. {"tax": 0.12}
    relations: Dict[str, float] = Field(default_factory=dict) # ex. {"S2": 0.3}
    classes: Dict[str, ClassEntityData] = Field(default_factory=dict)

    def add_resource(self, item: str, qty: float) -> None:
        """
        Tool: Add a resource to the state's inventory.
        Parameters:
            item (str): Resource name
            qty (float): Quantity to add
        Returns:
            None
        """
        self.inventory[item] = self.inventory.get(item, 0.0) + qty

    def adjust_morale(self, delta: float) -> None:
        """
        Tool: Adjust the morale of the state.
        Parameters:
            delta (float): Change in morale
        Returns:
            None
        """
        self.morale = max(0.0, min(1.0, self.morale + delta))

    def spawn_class(self, class_entity: ClassEntityData) -> None:
        """
        Tool: Add a new class entity to the state.
        Parameters:
            class_entity (ClassEntityData): The class entity to add
        Returns:
            None
        """
        self.classes[class_entity.id] = class_entity

    def despawn_class(self, class_id: str) -> bool:
        """
        Tool: Remove a class entity from the state.
        Parameters:
            class_id (str): The ID of the class entity to remove
        Returns:
            bool: True if the class was removed, False otherwise
        """
        return self.classes.pop(class_id, None) is not None
