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

## Helpers: IO + templating

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
    """
    ADK uses under the hood a schema representation similar to genai,
    which does NOT accept all of JSON Schema. We clean and transform "additionalProperties".
    """
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
            if node.get("type") == "object" and "additionalProperties" in node:
                return _open_object_to_kv_array(node)
            out = {}
            for k, v in node.items():
                if k in DROP_KEYS:
                    continue
                if k in ("properties", "definitions") and isinstance(v, dict):
                    out[k] = {pk: _walk(pv) for pk, pv in v.items()}
                elif k == "items":
                    out[k] = _walk(v)
                elif k == "required" and isinstance(v, list):
                    out[k] = v
                elif k == "enum" and isinstance(v, list):
                    out[k] = v
                elif k == "additionalProperties":
                    continue  # already handled above
                else:
                    out[k] = _walk(v)
            return out
        if isinstance(node, list):
            return [_walk(x) for x in node]
        return node

    return _walk(schema)


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
    """
    Uses prompts/analysis.txt + contracts/analysis.schema.json.
    """
    tpl = _load_text(PROMPTS_DIR / "analysis.txt")
    prompt = _fill(tpl, payload)
    return _call_adk(prompt, schema_file="analysis.schema.json")
