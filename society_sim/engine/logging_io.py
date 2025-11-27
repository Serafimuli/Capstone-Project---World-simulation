# society_sim/engine/logging_io.py
from __future__ import annotations
from pathlib import Path
import json
import time

def init_run_dir(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    d = root / ts
    d.mkdir(parents=True, exist_ok=True)
    return d

def write_jsonl(path: Path, obj: dict) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

def write_json(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
