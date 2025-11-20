from __future__ import annotations
import copy
import re
from typing import Any, Dict, Tuple, Optional


RANGE01_KEYS = {
    ("Society", "morale"), ("Society", "inequality"),
    ("Society", "religious_influence"), ("Society", "urbanization"), ("Society", "education"),
    ("Economy", "tax_rate"), ("Economy", "rents_rate"), ("Economy", "tithe_rate"),
    ("Economy", "trade_intensity"), ("Economy", "price_level"), ("Economy", "productivity"),
    ("State", "legitimacy"), ("State", "stability"), ("State", "borders_threat"), ("State", "corruption"),
    ("Infrastructure", "roads_quality"), ("Infrastructure", "fortifications"), ("Infrastructure", "market_access"),
    ("Environment", "harvest_quality"), ("Environment", "plague_pressure"),
    ("Environment", "winter_severity"), ("Environment", "disaster_risk"),
}

STOCK_KEYS = {
    ("Resources", "food"), ("Resources", "coinage"), ("Resources", "timber"),
    ("Resources", "iron"), ("Resources", "manpower"), ("Infrastructure", "granaries_capacity"),
    ("Society", "population")
}


def _find_path(world: Dict[str, Any], key: str) -> Optional[Tuple[str, str]]:
    if "." in key:
        sec, var = key.split(".", 1)
        return (sec, var) if sec in world and var in world[sec] else None
    for sec, section in world.items():
        if isinstance(section, dict) and key in section:
            return sec, key
    return None


def _parse_effect(value: str, current: float) -> float:
    s = value.strip().replace(" ", "")
    m = re.fullmatch(r"([+-]?\d*\.?\d+)%", s)
    if m:
        pct = float(m.group(1)) / 100.0
        return current * pct
    try:
        return float(s)
    except Exception:
        return 0.0


def apply_effects(world: Dict[str, Any], expected_effects: Dict[str, str]) -> Dict[str, Any]:
    out = copy.deepcopy(world)
    for key, val in expected_effects.items():
        path = _find_path(out, key)
        if not path:
            continue
        sec, var = path
        cur = out[sec][var]
        delta = _parse_effect(val, float(cur) if isinstance(cur, (int, float)) else 0.0)

        if (sec, var) in RANGE01_KEYS:
            new_val = max(0.0, min(1.0, float(cur) + delta))
        elif (sec, var) in STOCK_KEYS:
            new_val = max(0.0, float(cur) + delta)
        else:
            try:
                new_val = float(cur) + delta
            except Exception:
                continue
        out[sec][var] = new_val
    return out
