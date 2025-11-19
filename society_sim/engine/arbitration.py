"""
Arbitraj + guardrails:
- Prioritizare simplă în funcție de numele acțiunii (pattern-uri)
- Filtrare acțiuni care ar încălca guardrails (după estimarea numerică preliminară)
"""
from __future__ import annotations
from typing import Any, Dict, List, Tuple


def _priority(action_name: str) -> int:
    a = action_name.lower()
    # 0 = producție/logistică, 1 = piețe, 2 = guvernare/legi/fiscal, 3 = securitate, 4 = comunicare/cultură
    if any(k in a for k in ["produce", "harvest", "plant", "repair", "build", "irrig"]):
        return 0
    if any(k in a for k in ["trade", "price", "market", "caravan", "transport"]):
        return 1
    if any(k in a for k in ["tax", "law", "appoint", "budget", "land", "edict"]):
        return 2
    if any(k in a for k in ["defend", "raid", "guard", "suppress", "army", "fortif"]):
        return 3
    return 4


def order_actions(role_actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(role_actions, key=lambda r: _priority(r.get("action_name", "")))


def violates_guardrails(pre_world: Dict[str, Any], post_world: Dict[str, Any], guardrails: Dict[str, Any]) -> bool:
    # așteptăm chei precum: min_stability, min_legitimacy, min_food_buffer
    min_st = float(guardrails.get("min_stability", 0.0))
    min_leg = float(guardrails.get("min_legitimacy", 0.0))
    min_food = float(guardrails.get("min_food_stock", 0.0))
    st = _get(post_world, "State.stability")
    lg = _get(post_world, "State.legitimacy")
    fd = _get(post_world, "Resources.food")
    if st is not None and st < min_st:
        return True
    if lg is not None and lg < min_leg:
        return True
    if fd is not None and fd < min_food:
        return True
    return False


def _get(world: Dict[str, Any], path: str):
    cur = world
    for p in path.split("."):
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
        else:
            return None
    return cur
