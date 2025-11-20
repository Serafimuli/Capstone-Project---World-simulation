"""
Prepares the payload for the Analyst Agent:
- reads world_initial, world_tick_*.json, world_final.json
- reads history.jsonl to extract decisions and events per tick
- computes a few quick values (optional; final analysis is done by the LLM)
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List


def _read_json(p: Path) -> Any:
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _read_history_lines(history_path: Path) -> List[Dict[str, Any]]:
    out = []
    if not history_path.exists():
        return out
    for line in history_path.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except Exception:
            pass
    return out


def build_payload(run_dir: Path, ticks: int) -> Dict[str, Any]:
    world_initial = _read_json(run_dir / "world_initial.json")
    world_final   = _read_json(run_dir / "world_final.json")

    per_tick_world = []
    for t in range(1, ticks + 1):
        w = _read_json(run_dir / f"world_tick_{t}.json")
        if w is not None:
            per_tick_world.append(w)

    hist_lines = _read_history_lines(run_dir / "history.jsonl")
    per_tick_decisions, per_tick_events = [], []
    for h in hist_lines:
        if h.get("phase") == "tick":
            per_tick_decisions.append(h.get("decisions", []))
            per_tick_events.append({
                "proposed": h.get("events_proposed", {}),
                "fired": h.get("events_fired", [])
            })

    return {
        "TICKS": ticks,
        "WORLD_INITIAL_JSON": world_initial or {},
        "WORLD_FINAL_JSON": world_final or {},
        "PER_TICK_WORLD_JSON": per_tick_world,
        "PER_TICK_DECISIONS_JSON": per_tick_decisions,
        "PER_TICK_EVENTS_JSON": per_tick_events
    }
