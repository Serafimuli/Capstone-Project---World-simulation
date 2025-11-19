"""
Orchestrator:
- Bootstrap: LLM decide context, world_state_initial, role_specs[]
- Pe fiecare tick:
    1) cere decizie de la fiecare rol (acțiuni inventate)
    2) PRIORITIZEAZĂ + verifică guardrails (estimare)
    3) aplică efecte (interpret_actions)
    4) evenimente: forecast + sampling + aplicare
    5) log
Configurează guardrails în config.yaml (ex: min_stability, min_legitimacy, min_food_stock)
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List
from society_sim.engine import llm_adapter, arbitration, interpret_actions as IA, events, logging_io as LIO



DEFAULT_GUARDRAILS = {
    "min_stability": 0.30,
    "min_legitimacy": 0.30,
    "min_food_stock": 50.0
}


def _world_summary(world: Dict[str, Any]) -> Dict[str, Any]:
    """Poți agrega/rotunji aici dacă vrei un rezumat mai compact."""
    return world


def run(user_prompt: str, ticks: int = 12, guardrails: Dict[str, Any] | None = None, runs_dir: str = "runs") -> Path:
    guardrails = guardrails or DEFAULT_GUARDRAILS
    run_dir = LIO.init_run_dir(Path(runs_dir))
    hist = run_dir / "history.jsonl"

    # 1) BOOTSTRAP
    boot = llm_adapter.bootstrap(user_prompt)
    world = boot["world_state_initial"]
    role_specs = boot["role_specs"]

    LIO.write_jsonl(hist, {"phase": "bootstrap", "payload": boot})
    # snapshot inițial
    LIO.write_json(run_dir / "world_initial.json", world)

    # 2) TICKS
    for t in range(1, ticks + 1):
        decisions_raw: List[Dict[str, Any]] = []
        previews: List[Dict[str, Any]] = []

        for spec in role_specs:
            dec = llm_adapter.role_decision(spec, _world_summary(world))
            preview_world = IA.apply_effects(world, dec.get("expected_effects", {}))
            decisions_raw.append(dec)
            previews.append({
                "role_name": dec.get("role_name"),
                "action_name": dec.get("action_name"),
                "pre_world": world,
                "post_world": preview_world
            })

        filtered = []
        for dec, pv in zip(decisions_raw, previews):
            if arbitration.violates_guardrails(pv["pre_world"], pv["post_world"], guardrails):
                continue
            filtered.append(dec)

        ordered = arbitration.order_actions(filtered)

        # aplică efectele în ordinea arbitrajului
        for dec in ordered:
            world = IA.apply_effects(world, dec.get("expected_effects", {}))

        # evenimente
        world_after_events, ev_payload, ev_fired = events.forecast_and_apply(world)
        world = world_after_events

        # log + snapshot pe tick
        LIO.write_jsonl(hist, {
            "phase": "tick",
            "tick": t,
            "decisions": decisions_raw,
            "filtered": [d.get("action_name") for d in filtered],
            "applied": [d.get("action_name") for d in ordered],
            "events_proposed": ev_payload,
            "events_fired": ev_fired,
            "world": world
        })
        LIO.write_json(run_dir / f"world_tick_{t}.json", world)

    # 3) FINAL
    LIO.write_json(run_dir / "world_final.json", world)

    # opțional: printează sumarul final pe consolă (scurt)
    try:
        print("[Final World] Resources:", world.get("Resources"))
        print("[Final World] Society  :", {k: world["Society"][k] for k in ("population","morale","inequality") if k in world["Society"]})
        print("[Final World] State    :", {k: world["State"][k] for k in ("stability","legitimacy") if k in world["State"]})
    except Exception:
        pass

    return run_dir



if __name__ == "__main__":
    # Exemplu de rulare (va ridica NotImplementedError până integrezi LLM):
    run("Simulează o lume de acum 1000 de ani", ticks=6)
