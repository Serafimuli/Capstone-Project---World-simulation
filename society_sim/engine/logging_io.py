"""
Logging simplu: scrie un JSON/linie în runs/<timestamp>/history.jsonl
"""
from __future__ import annotations
import json, time
from pathlib import Path
from typing import Any, Dict, List


def _ts() -> str:
    return time.strftime("%Y-%m-%d_%H-%M-%S")


def init_run_dir(base: Path) -> Path:
    base.mkdir(parents=True, exist_ok=True)
    run_dir = base / _ts()
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def write_jsonl(path: Path, obj: Dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

def write_json(path: Path, obj: Dict[str, Any]) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
