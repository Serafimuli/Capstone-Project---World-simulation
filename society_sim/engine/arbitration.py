# society_sim/engine/arbitration.py
from __future__ import annotations
from typing import Dict, Any, List, Tuple

# priority: bigger number = earlier
PRIORITY = {
    "Resources.food": 100,
    "State.stability": 95,
    "State.legitimacy": 90,
    "Economy.price_level": 70,
    "Economy.trade_intensity": 60,
}

def _score_action(effects: Dict[str, str]) -> int:
    # simple: sum max priority key present, fallback 50
    score = 0
    for k in effects.keys():
        score = max(score, PRIORITY.get(k, 50))
    return score

def order_actions(decisions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(decisions, key=lambda d: _score_action(d.get("expected_effects", {})), reverse=True)

def violates_guardrails(pre_world: Dict[str, Any], post_world: Dict[str, Any], guards: Dict[str, Any]) -> bool:
    # simple checks
    s = post_world.get("State", {})
    r = post_world.get("Resources", {})
    if s.get("stability", 1.0) < guards["min_stability"]:
        return True
    if s.get("legitimacy", 1.0) < guards["min_legitimacy"]:
        return True
    # crude food floor: 20 days equivalent or > 0?
    if r.get("food", 0.0) <= guards["min_food"]:
        return True
    return False

def is_negligible_change(pre_world: Dict[str, Any], post_world: Dict[str, Any], min_stock_pct: float = 0.005) -> bool:
    def get(d, path):
        cur = d
        for p in path.split("."):
            cur = cur.get(p, {})
        return cur if isinstance(cur, (int, float)) else None

    stocks = ["Resources.food", "Resources.coinage", "Resources.manpower", "Resources.timber", "Resources.iron"]
    for p in stocks:
        a = get(pre_world, p); b = get(post_world, p)
        if a is not None and b is not None and abs(b - a) >= abs(a) * min_stock_pct:
            return False
    ranges = ["Society.morale", "State.stability", "State.legitimacy", "Economy.trade_intensity", "Economy.price_level"]
    for p in ranges:
        a = get(pre_world, p); b = get(post_world, p)
        if a is not None and b is not None and abs(b - a) >= 0.01:
            return False
    return True
