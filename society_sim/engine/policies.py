# society_sim/engine/policies.py
from __future__ import annotations
from typing import Dict, Any, Tuple

# return ("accept" | "counter" | "reject", optional_counter_terms_dict | None)
def acceptance_policy(role_name: str, world: Dict[str, Any], message: Dict[str, Any]) -> Tuple[str, Dict[str, Any] | None]:
    """
    Ultra-simple defaults you can tune later.
    - avoid stability/legitimacy < 0.35
    - avoid food negative shock > 12%
    - if coinage cost > 12% and no compensating benefit, counter - reduce ask by half
    """
    state = (world.get("State") or {})
    resources = (world.get("Resources") or {})
    stability = float(state.get("stability", 0.5))
    legitimacy = float(state.get("legitimacy", 0.5))
    food = float(resources.get("food", 0.0))

    intent = message.get("intent", "")
    content = message.get("content", {}) or {}

    # quick guardrails
    if stability < 0.35 or legitimacy < 0.35:
        # during fragile times, reject threats or heavy requests
        if intent in ("threat", "request", "propose", "counter"):
            return "reject", None

    # protect food
    if any(k.lower().endswith("food") and v.startswith("-1") for k, v in content.items()):
        # crude check: "-1"x% or -100 .. -19
        return "reject", None

    # coinage heavy cost? counter to half
    coin_keys = [k for k in content.keys() if k.lower().endswith("coinage")]
    if coin_keys:
        for ck in coin_keys:
            val = str(content[ck]).replace(" ", "")
            if val.endswith("%") and val.startswith("-"):
                try:
                    pct = abs(float(val[:-1]))
                    if pct > 12.0:
                        # counter: halve the ask
                        new_pct = f"-{pct/2:.1f}%"
                        counter = dict(content)
                        counter[ck] = new_pct
                        return "counter", counter
                except Exception:
                    pass

    # default accept for inform/accept/commit if not violating obvious rules
    if intent in ("inform", "accept", "commit"):
        return "accept", None

    # default accept for mild proposes/requests
    return "accept", None
