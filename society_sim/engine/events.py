"""
Evenimente:
- Cere evenimente candidate de la LLM (propuneri + probabilități)
- Face sampling Bernoulli
- Aplică efectele estimate folosind aceeași logică din interpret_actions
"""
from __future__ import annotations
import random
from typing import Any, Dict, List, Tuple
from . import interpret_actions as ia
from . import llm_adapter


def forecast(world_summary: Dict[str, Any]) -> Dict[str, Any]:
    return llm_adapter.events(world_summary)


def sample(events_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    chosen = []
    for ev in events_payload.get("events", []):
        p = max(0.0, min(1.0, float(ev.get("probability", 0.0))))
        if random.random() < p:
            chosen.append(ev)
    return chosen


def apply(world: Dict[str, Any], fired_events: List[Dict[str, Any]]) -> Dict[str, Any]:
    updated = world
    for ev in fired_events:
        eff = ev.get("expected_effects", {})
        if isinstance(eff, dict) and eff:
            updated = ia.apply_effects(updated, eff)
    return updated


def forecast_and_apply(world: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any], List[Dict[str, Any]]]:
    payload = forecast(world)
    fired = sample(payload)
    new_world = apply(world, fired)
    return new_world, payload, fired
