"""
Prepares the payload for the Analyst Agent:
- reads world_initial, world_tick_*.json, world_final.json
- reads history.jsonl to extract decisions and events per tick
- (NEW) reads messages_tick_*.json and agreements_tick_*.json if present
- returns a single dict matching the placeholders used by prompts/analysis.txt
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List


def _read_json(p: Path) -> Any:
    """Return parsed JSON or None if file does not exist or is invalid."""
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    except Exception:
        return None


def _read_history_lines(history_path: Path) -> List[Dict[str, Any]]:
    """Read history.jsonl line by line into a list of dicts."""
    out: List[Dict[str, Any]] = []
    if not history_path.exists():
        return out
    try:
        for line in history_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                # ignore malformed lines
                pass
    except Exception:
        pass
    return out


def build_payload(run_dir: Path, ticks: int) -> Dict[str, Any]:
    """
    Build the full LLM payload for analysis.

    Structure returned:
    {
      "TICKS": int,
      "WORLD_INITIAL_JSON": {},
      "WORLD_FINAL_JSON": {},
      "PER_TICK_WORLD_JSON": [ {}, ... ],
      "PER_TICK_DECISIONS_JSON": [ [decisions...], ... ],
      "PER_TICK_EVENTS_JSON": [ {"proposed": {...}, "fired": [...]}, ... ],
      # Optional (if files exist):
      "PER_TICK_MESSAGES_JSON": [ {inboxes,outboxes,all_messages_visible}, ... ],
      "PER_TICK_COORD_JSON": [ {accepted, coordinated_actions}, ... ]
    }
    """
    # --- Core snapshots
    world_initial = _read_json(run_dir / "world_initial.json")
    world_final = _read_json(run_dir / "world_final.json")

    per_tick_world: List[Dict[str, Any]] = []
    for t in range(1, ticks + 1):
        w = _read_json(run_dir / f"world_tick_{t}.json")
        if w is not None:
            per_tick_world.append(w)

    # --- Optional messaging & coordination snapshots
    per_tick_messages: List[Dict[str, Any]] = []
    per_tick_coord: List[Dict[str, Any]] = []
    for t in range(1, ticks + 1):
        m = _read_json(run_dir / f"messages_tick_{t}.json")
        if m is not None:
            # You can reduce the payload here if needed, e.g., keep only counts:
            # m = {"all_messages_visible": m.get("all_messages_visible", [])}
            per_tick_messages.append(m)

        c = _read_json(run_dir / f"agreements_tick_{t}.json")
        if c is not None:
            per_tick_coord.append(c)

    # --- History rollup (decisions & events) from history.jsonl
    hist_lines = _read_history_lines(run_dir / "history.jsonl")
    per_tick_decisions: List[List[Dict[str, Any]]] = []
    per_tick_events: List[Dict[str, Any]] = []
    for h in hist_lines:
        if h.get("phase") == "tick":
            per_tick_decisions.append(h.get("decisions", []))
            per_tick_events.append({
                "proposed": h.get("events_proposed", {}) or {},
                "fired": h.get("events_fired", []) or []
            })

    payload: Dict[str, Any] = {
        "TICKS": ticks,
        "WORLD_INITIAL_JSON": world_initial or {},
        "WORLD_FINAL_JSON": world_final or {},
        "PER_TICK_WORLD_JSON": per_tick_world,
        "PER_TICK_DECISIONS_JSON": per_tick_decisions,
        "PER_TICK_EVENTS_JSON": per_tick_events
    }

    if per_tick_messages:
        payload["PER_TICK_MESSAGES_JSON"] = per_tick_messages
    if per_tick_coord:
        payload["PER_TICK_COORD_JSON"] = per_tick_coord

    return payload

