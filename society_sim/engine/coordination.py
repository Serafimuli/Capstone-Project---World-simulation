# coordination.py
from typing import List, Dict, Any
import re

def _norm_val(v: Any) -> str:
    s = str(v).strip()
    # uniformizează procentele: "- 5 % " -> "-5%"
    s = re.sub(r"\s*", "", s)
    # "+05%" -> "+5%"
    s = re.sub(r"^([+-])0+(\d)", r"\1\2", s)
    return s

def _key_from_content(c: Dict[str, Any]) -> str:
    if not c:
        return ""
    items = sorted((str(k).strip(), _norm_val(v)) for k, v in c.items())
    return "|".join(f"{k}:{v}" for k, v in items)



def _msg_to_dict(m: Any) -> Dict[str, Any]:
    if isinstance(m, dict):
        return m
    # fallback pentru dataclass Message
    d = {
        "sender": getattr(m, "sender", None),
        "receivers": getattr(m, "receivers", None),
        "intent": getattr(m, "intent", None),
        "content": getattr(m, "content", None),
        "valid_until_tick": getattr(m, "valid_until_tick", None),
    }
    # filtrează None
    return {k: v for k, v in d.items() if v is not None}

def extract_accepted_agreements(messages: List[Any]) -> List[Dict[str, Any]]:
    messages = [_msg_to_dict(m) for m in messages]
    ProposeLike = ("propose", "request", "counter")
    CommitLike = ("commit",)
    AcceptLike = ("accept",)

    proposes: Dict[str, List[Dict[str, Any]]] = {}
    for m in messages:
        if m.get("intent") in ProposeLike:
            sig = _key_from_content(m.get("content", {}))
            proposes.setdefault(sig, []).append(m)

    agreements: List[Dict[str, Any]] = []
    for m in messages:
        intent = m.get("intent")
        content = m.get("content", {}) or {}
        if intent in CommitLike:
            agreements.append({"by": m.get("sender"),
                               "partners": m.get("receivers", []),
                               "terms": content})
        elif intent in AcceptLike:
            sig = _key_from_content(content)
            if sig in proposes:
                src = proposes[sig][-1]
                agreements.append({"by": src.get("sender"),
                                   "partners": src.get("receivers", []),
                                   "terms": src.get("content", {})})

    seen, uniq = set(), []
    for a in agreements:
        sig = (a["by"], tuple(sorted(a["partners"])),
               _key_from_content(a["terms"]))
        if sig not in seen:
            seen.add(sig)
            uniq.append(a)
    return uniq
