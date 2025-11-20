"""
Interprets *relative* effects (e.g.: "morale":"+0.05", "coinage":"-0.02", "food":"+10%")
and transforms them into numeric deltas on the world.
- Simple heuristics: variables 0..1 (additive), stocks (proportional), % respects current base
- If an effect key does not include the section, it is searched in all sections
"""
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
    # Accepts "Society.morale" or just "morale"
    if "." in key:
        sec, var = key.split(".", 1)
        return (sec, var) if sec in world and var in world[sec] else None
    # searches for the variable in all sections
    for sec, section in world.items():
        if isinstance(section, dict) and key in section:
            return sec, key
    return None


        """
        Returns numeric delta (not the final value).
        Accepts:
            "+0.05" -> +0.05 (additive)
            "-0.02" -> -0.02
            "+10%"  -> current * 0.10
            "-20%"  -> current * -0.20
        """
    s = value.strip().replace(" ", "")
    m = re.fullmatch(r"([+-]?\d*\.?\d+)%", s)
    if m:
        pct = float(m.group(1)) / 100.0
        return current * pct
    # simplu numeric
    try:
        return float(s)
    except Exception:
        # fallback conservator
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
            # default: doar adună
            try:
                new_val = float(cur) + delta
            except Exception:
                continue
        out[sec][var] = new_val
    return out
