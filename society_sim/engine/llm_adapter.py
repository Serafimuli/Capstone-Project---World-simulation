from __future__ import annotations
import asyncio
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import jsonschema  
except Exception:
    jsonschema = None

try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
except Exception:
    pass

## ADK imports
from google.adk.agents.llm_agent import LlmAgent as Agent
from google.adk.runners import InMemoryRunner
from google.genai.types import Content, Part  # tipuri de mesaje (user/model)

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
CONTRACTS_DIR = Path(__file__).resolve().parent.parent / "contracts"


_PERCENT_RE = re.compile(r"^\s*([+-]?\d+(?:\.\d+)?)\s*%\s*$")
_NUM_RE     = re.compile(r"^\s*([+-]?\d+(?:\.\d+)?)\s*$")

def _deep_coerce_scalars(x: Any) -> Any:
    if isinstance(x, dict):
        return {k: _deep_coerce_scalars(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_deep_coerce_scalars(v) for v in x]
    if isinstance(x, str):
        s = x.strip()

        # Booleans (accept Python or JSON style)
        if s.lower() in ("true", "false"):
            return s.lower() == "true"

        # Percent -> float of the numeric part (e.g., "30.05%" -> 30.05)
        m = _PERCENT_RE.match(s)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                return x

        # Plain number with optional sign
        m = _NUM_RE.match(s)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                return x
    return x

def _normalize_evidence_ticks(obj: dict[str, Any]) -> dict[str, Any]:
    """
    Ensures evidence_ticks are 1-based and valid integers >= 1.
    If any 0s are present and there are no negatives, we assume zero-based indexing and bump all by +1.
    Otherwise we clamp each tick to at least 1.
    """
    chains = obj.get("cause_effect_chains")
    if not isinstance(chains, list):
        return obj

    # Detect if the author used 0-based indexing (presence of 0 and no negatives)
    has_zero = False
    has_negative = False
    for ch in chains:
        ticks = ch.get("evidence_ticks")
        if isinstance(ticks, list):
            for t in ticks:
                if isinstance(t, int):
                    if t == 0:
                        has_zero = True
                    elif t < 0:
                        has_negative = True

    zero_based = has_zero and not has_negative

    for ch in chains:
        ticks = ch.get("evidence_ticks")
        if not isinstance(ticks, list):
            continue

        normalized = []
        for t in ticks:
            try:
                ti = int(t)
            except Exception:
                continue  # drop non-integers silently

            if zero_based:
                ti = ti + 1  # shift to 1-based

            if ti < 1:
                ti = 1  # clamp to schema minimum

            normalized.append(ti)

        # Guarantee non-empty list to avoid accidental empties after filtering
        if not normalized:
            normalized = [1]

        ch["evidence_ticks"] = normalized

    return obj

## Helpers: IO + templating
def _coerce_scalar(v: Any) -> Any:
    if isinstance(v, (int, float, bool)) or v is None:
        return v
    s = str(v).strip()

    if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
        try:
            return json.loads(s)
        except Exception:
            pass

    if s.lower() in ("true", "false"):
        return s.lower() == "true"

    m = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)\s*%", s)
    if m:
        try:
            return float(m.group(1))
        except Exception:
            return s

    m = re.fullmatch(r"[+-]?\d+(?:\.\d+)?", s)
    if m:
        try:
            return float(s)
        except Exception:
            return s

    return s

def _parse_path(key: str) -> list[Any]:
    parts = [p for p in key.split(".") if p != ""]
    tokens: list[Any] = []
    for p in parts:
        if re.fullmatch(r"\d+", p):
            tokens.append(int(p))
        else:
            tokens.append(p)
    return tokens

def _assign_path(root: Any, path: list[Any], value: Any) -> Any:
    if not path:
        return value
    head, *tail = path

    if isinstance(head, int):
        if not isinstance(root, list):
            root = [] if root is None else []

        while len(root) <= head:
            root.append(None)
        root[head] = _assign_path(root[head], tail, value)
        return root

    if not isinstance(root, dict):
        root = {} if root is None else {}
    root[head] = _assign_path(root.get(head), tail, value)
    return root

def _kv_root_list_to_object_pathy(kv_list: list[dict[str, Any]]) -> dict[str, Any]:
    root: Any = {}
    for it in kv_list:
        if not isinstance(it, dict):
            continue
        k = str(it.get("key", "")).strip()
        if not k:
            continue
        v = _coerce_scalar(it.get("value"))
        path = _parse_path(k)
        root = _assign_path(root, path, v)

    if isinstance(root, dict) and "metrics" in root and isinstance(root["metrics"], dict):
        for g in ["resources", "society", "state", "economy", "risk_flags", "volatility"]:
            root["metrics"].setdefault(g, {})
    return root

def _ensure_list_of_strings(val: Any, min_items: int = 2, max_items: int = 5) -> list[str]:
    if isinstance(val, list):
        items = [str(x).strip() for x in val if str(x).strip()]
    elif isinstance(val, str):
        s = val.strip()
        try:
            as_json = json.loads(s)
            if isinstance(as_json, list):
                items = [str(x).strip() for x in as_json if str(x).strip()]
            else:
                raise ValueError
        except Exception:
            parts = re.split(r'(?<=[\.\!\?])\s+|[;\n]+', s)
            items = [p.strip() for p in parts if p and p.strip()]
    else:
        items = []

    if len(items) > max_items:
        items = items[:max_items]
    return items

def _load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")

def _load_schema(schema_file: Optional[str]) -> Optional[Dict[str, Any]]:
    if not schema_file:
        return None
    p = CONTRACTS_DIR / schema_file
    return json.loads(p.read_text(encoding="utf-8"))

def _fill(template: str, mapping: Dict[str, Any]) -> str:
    out = template
    for k, v in mapping.items():
        out = out.replace(f"{{{{{k}}}}}", v if isinstance(v, str) else json.dumps(v, ensure_ascii=False))
    return out

def _strip_code_fences(s: str) -> str:
    s = s.strip()
    fenced = re.match(r"^```(?:json)?\s*(.+?)\s*```$", s, flags=re.S)
    return fenced.group(1).strip() if fenced else s

def _json_from_text(s: str) -> Dict[str, Any]:
    s = _strip_code_fences(s)
    return json.loads(s)


def _open_object_to_kv_array(_node: Dict[str, Any]) -> Dict[str, Any]:
    """Transforms an object with free keys into a list of {key,value} (ADK/genai compatible)."""
    return {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "key":   {"type": "string"},
                "value": {"type": "string"}
            },
            "required": ["key", "value"]
        }
    }

def _kv_array_to_dict(val: Any) -> Any:
    if isinstance(val, list) and all(isinstance(it, dict) and "key" in it and "value" in it for it in val):
        return {str(it["key"]): it["value"] for it in val}
    return val

def _normalize_open_objects(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _normalize_open_objects(_kv_array_to_dict(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalize_open_objects(x) for x in obj]
    return obj

def _validate(obj: Dict[str, Any], schema: Optional[Dict[str, Any]]) -> None:
    if schema is None or jsonschema is None:
        return
    jsonschema.validate(instance=obj, schema=schema)


def _sanitize_schema_for_adk(schema: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(schema, dict):
        return schema

    DROP_KEYS = {
        "minItems", "maxItems",
        "patternProperties",
        "minLength", "maxLength", "pattern",
        "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
        "multipleOf", "format",
        "title", "description", "default", "examples", "$schema", "$id"
    }

    def _walk(node: Any) -> Any:
        if isinstance(node, dict):
            if node.get("type") == "object":
                ap = node.get("additionalProperties", None)
                # Only transform truly "open" objects
                if ap is True:
                    return _open_object_to_kv_array(node)

            out = {}
            for k, v in node.items():
                if k in DROP_KEYS:
                    continue
                if k == "additionalProperties":
                    # Drop it (ADK doesn't support it), but don't convert
                    # closed objects into KV arrays.
                    continue
                if k in ("properties", "definitions") and isinstance(v, dict):
                    out[k] = {pk: _walk(pv) for pk, pv in v.items()}
                elif k == "items":
                    out[k] = _walk(v)
                else:
                    out[k] = _walk(v)
            return out

        if isinstance(node, list):
            return [_walk(x) for x in node]
        return node

    return _walk(schema)

def _clamp_number(x, lower=None, upper=None):
    try:
        v = float(x)
    except Exception:
        return lower if lower is not None else 0.0
    if v != v:  # NaN
        v = 0.0
    if lower is not None and v < lower:
        v = lower
    if upper is not None and v > upper:
        v = upper
    return v

def _normalize_volatility(obj: dict) -> dict:
    m = obj.get("metrics")
    if not isinstance(m, dict):
        return obj
    vol = m.get("volatility")
    if not isinstance(vol, dict):
        return obj

    # Schema: morale_volatility in [0,1]; price_volatility >= 0
    if "morale_volatility" in vol:
        vol["morale_volatility"] = _clamp_number(vol["morale_volatility"], lower=0.0, upper=1.0)
    else:
        vol["morale_volatility"] = 0.0

    if "price_volatility" in vol:
        vol["price_volatility"] = _clamp_number(vol["price_volatility"], lower=0.0)
    else:
        vol["price_volatility"] = 0.0

    return obj


_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip()

_AGENT = Agent(
    model=_MODEL,
    name="society_root",
    description="Simulation JSON agent",
    instruction=(
        "You are a structured-output agent for a simulated world. "
        "ALWAYS return valid JSON that matches the provided schema. "
        "Do not add commentary."
    ),
    # tools=[...], 
)

_RUNNER = InMemoryRunner(agent=_AGENT, app_name="society-sim")

_SESSION_ID: Optional[str] = None

async def _get_session_id() -> str:
    global _SESSION_ID
    if _SESSION_ID is None:
        s = await _RUNNER.session_service.create_session(
            app_name="society-sim",
            user_id="society-sim-user",
        )
        _SESSION_ID = s.id
    return _SESSION_ID

def _augment_prompt_with_schema(prompt: str, schema_send: Optional[Dict[str, Any]]) -> str:
    if not schema_send:
        return prompt
    schema_txt = json.dumps(schema_send, ensure_ascii=False)
    addition = (
        "\n\nSTRICT OUTPUT CONSTRAINTS:\n"
        "Return ONLY valid JSON matching EXACTLY this schema (subset of JSON Schema):\n"
        "```json\n" + schema_txt + "\n```\n"
        "Do not add any commentary or Markdown outside the JSON object."
    )
    return prompt + addition


async def _adk_call_async(prompt: str, schema_send: Optional[Dict[str, Any]]) -> str:
    prompt = _augment_prompt_with_schema(prompt, schema_send)

    msg = Content(role="user", parts=[Part(text=prompt)])
    final_text = ""

    session_id = await _get_session_id()

    async for event in _RUNNER.run_async(
        session_id=session_id,
        user_id="society-sim-user",
        new_message=msg,
    ):
        if event.content and event.content.parts:
            final_text = "".join(getattr(p, "text", "") or "" for p in event.content.parts)
    return final_text


def _call_adk(prompt: str, schema_file: Optional[str] = None) -> Dict[str, Any]:
    schema_orig = _load_schema(schema_file)
    schema_send = _sanitize_schema_for_adk(schema_orig) if schema_orig else None

    text = asyncio.run(_adk_call_async(prompt, schema_send))

    try:
        obj = _json_from_text(text)
    except Exception:
        m = re.search(r"\{.*\}", text, flags=re.S)
        obj = json.loads(m.group(0)) if m else {}

    obj = _normalize_open_objects(obj)
    _validate(obj, schema_orig)
    return obj


def bootstrap(user_prompt: str) -> Dict[str, Any]:
    """
    Generates the initial world state and role specifications for the simulation.
    Uses prompts/bootstrap.txt and validates output against contracts/bootstrap.schema.json.

    Args:
        user_prompt (str): The initial prompt describing the simulation scenario.

    Returns:
        Dict[str, Any]: Dictionary containing year_estimate, region_guess, context_summary,
                        world_state_initial, and role_specs.
    """
    tpl = _load_text(PROMPTS_DIR / "bootstrap.txt")
    prompt = _fill(tpl, {"USER_PROMPT": user_prompt})
    return _call_adk(prompt, schema_file="bootstrap.schema.json")

def role_decision(role_spec: Dict[str, Any], world_summary: Dict[str, Any]) -> Dict[str, Any]:
    """
    Uses prompts/role_tick.txt + contracts/role_decision.schema.json.
    """
    tpl = _load_text(PROMPTS_DIR / "role_tick.txt")
    mapping = {
        "ROLE_NAME": role_spec.get("role_name", ""),
        "MANDATE": role_spec.get("mandate", ""),
        "INCENTIVES": role_spec.get("incentives", ""),
        "OBSERVABLES_LIST": ", ".join(role_spec.get("observables", []) or []),
        "WORLD_SUMMARY_JSON": world_summary,
    }
    prompt = _fill(tpl, mapping)
    return _call_adk(prompt, schema_file="role_decision.schema.json")

def events(world_summary: Dict[str, Any]) -> Dict[str, Any]:
    """
    Uses prompts/events.txt + contracts/events.schema.json.
    """
    tpl = _load_text(PROMPTS_DIR / "events.txt")
    prompt = _fill(tpl, {"WORLD_SUMMARY_JSON": world_summary})
    return _call_adk(prompt, schema_file="events.schema.json")

def analyze(payload: Dict[str, Any]) -> Dict[str, Any]:
    schema_orig = _load_schema("analysis.schema.json")

    tpl = _load_text(PROMPTS_DIR / "analysis.txt")
    prompt = _fill(tpl, payload)

    schema_send = _sanitize_schema_for_adk(schema_orig) if schema_orig else None
    text = asyncio.run(_adk_call_async(prompt, schema_send))

    try:
        obj = _json_from_text(text)
    except Exception:
        m = re.search(r"\{.*\}|\[.*\]", text, flags=re.S)
        obj = json.loads(m.group(0)) if m else {}

    obj = _normalize_open_objects(obj)
    obj = _deep_coerce_scalars(obj)         
    obj = _normalize_evidence_ticks(obj)     
    obj = _normalize_volatility(obj)   

    if isinstance(obj, list) and all(isinstance(it, dict) and "key" in it and "value" in it for it in obj):
        obj = _kv_root_list_to_object_pathy(obj)

    if "recommendations" in obj:
        obj["recommendations"] = _ensure_list_of_strings(obj["recommendations"], 2, 5)
    if "conclusions" in obj:
        obj["conclusions"] = _ensure_list_of_strings(obj["conclusions"], 3, 6)

    if isinstance(obj.get("cause_effect_chains"), str):
        try:
            obj["cause_effect_chains"] = json.loads(obj["cause_effect_chains"])
        except Exception:
            obj["cause_effect_chains"] = []

    if isinstance(obj.get("cause_effect_chains"), list):
        for ch in obj["cause_effect_chains"]:
            if isinstance(ch, dict) and isinstance(ch.get("evidence_ticks"), list):
                ch["evidence_ticks"] = [int(x) for x in ch["evidence_ticks"] if str(x).isdigit()]

    _validate(obj, schema_orig)
    return obj


def messaging_round(role_spec: Dict[str, Any], world_summary: Dict[str, Any], role_inbox_json: list[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Uses prompts/messaging_round.txt + contracts/messaging_round.schema.json.
    Called each tick for every role to decide 0–2 outbound messages.

    Args:
        role_spec: the role description from bootstrap (mandate, incentives, etc.)
        world_summary: current world snapshot (dict)
        role_inbox_json: messages visible to this role at the current tick

    Returns:
        Dict[str, Any]: validated output (outbox[], rationale, negotiation_notes)
    """
    tpl = _load_text(PROMPTS_DIR / "messaging_round.txt")
    mapping = {
        "ROLE_NAME": role_spec.get("role_name", ""),
        "MANDATE": role_spec.get("mandate", ""),
        "INCENTIVES": role_spec.get("incentives", ""),
        "WORLD_SUMMARY_JSON": world_summary,
        "ROLE_INBOX_JSON": role_inbox_json,
    }
    prompt = _fill(tpl, mapping)
    return _call_adk(prompt, schema_file="messaging_round.schema.json")


def coordinate(world_summary: Dict[str, Any], accepted_msgs_json: list[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Uses prompts/coordination.txt + contracts/coordination.schema.json.
    Called once per tick after message exchange, to produce coordinated actions.

    Args:
        world_summary: current world snapshot (dict)
        accepted_msgs_json: list of accepted/commit messages forming agreements

    Returns:
        Dict[str, Any]: validated output (coordinated_actions[])
    """
    tpl = _load_text(PROMPTS_DIR / "coordination.txt")
    mapping = {
        "WORLD_SUMMARY_JSON": world_summary,
        "ACCEPTED_MSGS_JSON": accepted_msgs_json,
    }
    prompt = _fill(tpl, mapping)
    return _call_adk(prompt, schema_file="coordination.schema.json")

