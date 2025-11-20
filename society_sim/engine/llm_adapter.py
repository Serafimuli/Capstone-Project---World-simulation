"""
Gemini integration (google-generativeai / Vertex AI) with Structured Output.

Provider selection via env:
    - GEMINI_PROVIDER=google  (default; uses `google-generativeai` package)
    - GEMINI_PROVIDER=vertex  (uses Vertex AI: `google-cloud-aiplatform`)

Requirements:
    - for google:  pip install google-generativeai
        env: GEMINI_API_KEY=...
    - for vertex:  pip install google-cloud-aiplatform
        env: GOOGLE_CLOUD_PROJECT=..., GOOGLE_CLOUD_LOCATION=us-central1 (or other region)
                 optional: GEMINI_MODEL=gemini-1.5-pro

JSON validation (optional):
    - pip install jsonschema
"""

from __future__ import annotations
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional

# === Optional JSON schema validation ===
try:
    import jsonschema  # type: ignore
except Exception:
    jsonschema = None

try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
except Exception:
    pass

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
CONTRACTS_DIR = Path(__file__).resolve().parent.parent / "contracts"

# --------- Helpers: IO + templating ----------

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

def _open_object_to_kv_array(node: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transforms an object with dynamic keys (object + additionalProperties)
    into a google-compatible representation: array of {key, value}.
    """
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

def _strip_code_fences(s: str) -> str:
    # acceptă ```json ... ``` sau ``` ... ```
    s = s.strip()
    fenced = re.match(r"^```(?:json)?\s*(.+?)\s*```$", s, flags=re.S)
    return fenced.group(1).strip() if fenced else s

def _json_from_text(s: str) -> Dict[str, Any]:
    s = _strip_code_fences(s)
    return json.loads(s)

def _kv_array_to_dict(val: Any) -> Any:
    """
    If val is an array of {key, value}, convert it to dict.
    Otherwise, return val unchanged.
    """
    if isinstance(val, list) and all(isinstance(it, dict) and "key" in it and "value" in it for it in val):
        return {str(it["key"]): it["value"] for it in val}
    return val

def _normalize_open_objects(obj: Any) -> Any:
    """
    Recursively traverses the response and transforms any fields that came
    as array of kv back into dict (e.g.: expected_effects).
    """
    if isinstance(obj, dict):
        return {k: _normalize_open_objects(_kv_array_to_dict(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalize_open_objects(x) for x in obj]
    return obj

def _validate(obj: Dict[str, Any], schema: Optional[Dict[str, Any]]) -> None:
    if schema is None or jsonschema is None:
        return
    jsonschema.validate(instance=obj, schema=schema)

# --------- Provider selection ----------

_PROVIDER = os.getenv("GEMINI_PROVIDER", "google").strip().lower()  # 'google' | 'vertex'
_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip()

# --- google-generativeai (client-side) ---
_google_model = None
def _ensure_google_model() -> Any:
    global _google_model
    if _google_model is not None:
        return _google_model
    import google.generativeai as genai  # type: ignore
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing for provider=google.")
    genai.configure(api_key=api_key)
    _google_model = genai.GenerativeModel(_MODEL)
    return _google_model

def _call_google(prompt: str, schema: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    model = _ensure_google_model()
    generation_config = {"response_mime_type": "application/json"}
    if schema:
        generation_config["response_schema"] = schema
    # retry simplu
    for i in range(4):
        try:
            resp = model.generate_content(
                prompt,
                generation_config=generation_config,
            )
            # `resp.text` ar trebui să fie JSON valid (datorită schema+mimetype)
            return _json_from_text(resp.text)
        except Exception as e:
            if i == 3:
                raise
            time.sleep(0.8 * (2 ** i))

def _sanitize_schema_for_google(schema: Dict[str, Any]) -> Dict[str, Any]:
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
            # special: object cu additionalProperties => kv array
            if node.get("type") == "object" and "additionalProperties" in node:
                # Păstrăm doar tipul valorilor (de regulă string) dacă există
                # dar pentru google revenim la value:string (generic)
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
                    # eliminăm, a fost tratat mai sus (kv-array)
                    continue
                else:
                    out[k] = _walk(v)
            return out
        elif isinstance(node, list):
            return [_walk(x) for x in node]
        else:
            return node

    return _walk(schema)



# --- Vertex AI (server-side) ---
_vertex_model = None
def _ensure_vertex_model() -> Any:
    global _vertex_model
    if _vertex_model is not None:
        return _vertex_model
    from vertexai import init  # type: ignore
    from vertexai.generative_models import GenerativeModel  # type: ignore

    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    if not project:
        raise RuntimeError("GOOGLE_CLOUD_PROJECT is missing for provider=vertex.")
    init(project=project, location=location)
    _vertex_model = GenerativeModel(_MODEL)
    return _vertex_model

def _call_vertex(prompt: str, schema: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    model = _ensure_vertex_model()
    generation_config = {"response_mime_type": "application/json"}
    if schema:
        generation_config["response_schema"] = schema
    for i in range(4):
        try:
            resp = model.generate_content(
                [prompt],
                generation_config=generation_config,
            )
            # Vertex AI: content may be in resp.text or in candidates; handle both
            text = getattr(resp, "text", None)
            if not text and hasattr(resp, "candidates") and resp.candidates:
                # Best-effort: extract text from the first candidate
                parts = getattr(resp.candidates[0].content, "parts", [])
                text = "".join(getattr(p, "text", "") for p in parts if getattr(p, "text", ""))
            if not text:
                raise RuntimeError("Empty response from Vertex AI.")
            return _json_from_text(text)
        except Exception:
            if i == 3:
                raise
            time.sleep(0.8 * (2 ** i))

# --------- Single entrypoint ----------

def _call_llm(prompt: str, schema_file: Optional[str] = None) -> Dict[str, Any]:
    # 1) încarcă schema originală (JSON Schema completă din contracts/)
    schema_orig = _load_schema(schema_file)

    # 2) pregătește schema pentru provider (sanitizată pt. google)
    if _PROVIDER == "vertex":
        schema_send = schema_orig
        obj = _call_vertex(prompt, schema_send)
    else:
        schema_send = _sanitize_schema_for_google(schema_orig) if schema_orig else None
        obj = _call_google(prompt, schema_send)

    # 3) normalizează formele „array de {key,value}” -> dict (map)
    obj = _normalize_open_objects(obj)

    # 4) validează LOCAL cu schema ORIGINALĂ (care permite object cu additionalProperties)
    _validate(obj, schema_orig)

    return obj



# --------- Public API used by simulator ----------

def bootstrap(user_prompt: str) -> Dict[str, Any]:
    """
    Uses prompts/bootstrap.txt + contracts/bootstrap.schema.json.
    Returns:
        { year_estimate, region_guess, context_summary,
            world_state_initial:{...}, role_specs:[...] }
    """
    tpl = _load_text(PROMPTS_DIR / "bootstrap.txt")
    prompt = _fill(tpl, {"USER_PROMPT": user_prompt})
    return _call_llm(prompt, schema_file="bootstrap.schema.json")

def role_decision(role_spec: Dict[str, Any], world_summary: Dict[str, Any]) -> Dict[str, Any]:
    """
    Uses prompts/role_tick.txt + contracts/role_decision.schema.json.
    `role_spec` comes from bootstrap (invented by LLM).
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
    return _call_llm(prompt, schema_file="role_decision.schema.json")

def events(world_summary: Dict[str, Any]) -> Dict[str, Any]:
    """
    Uses prompts/events.txt + contracts/events.schema.json.
    """
    tpl = _load_text(PROMPTS_DIR / "events.txt")
    prompt = _fill(tpl, {"WORLD_SUMMARY_JSON": world_summary})
    return _call_llm(prompt, schema_file="events.schema.json")
