# society_sim/engine/simulate.py
from __future__ import annotations
from asyncio import sleep
from pathlib import Path
import random
from typing import Dict, Any, List, Tuple
import time

from society_sim.engine import llm_adapter, arbitration, interpret_actions as IA, events, logging_io as LIO
from society_sim.engine.message_bus import MessageBus, Message
from society_sim.engine import coordination as COORD

DEFAULT_GUARDRAILS = {
    "min_stability": 0.30,
    "min_legitimacy": 0.30,
    "min_food": 1.0,  # floor in absolute units
}

def _world_summary(world: Dict[str, Any]) -> Dict[str, Any]:
    # keep summary small; you can tailor this to your world schema
    keys = ["Resources", "Society", "State", "Economy", "Infrastructure", "Environment"]
    return {k: world.get(k) for k in keys if k in world}

def _maybe_llm(fn_name: str):
    # Lazy access to optional LLM entrypoints
    return getattr(llm_adapter, fn_name, None)

def run(user_prompt: str, ticks: int = 8, guardrails: Dict[str, Any] | None = None, runs_dir: str = "runs") -> Path:
    guardrails = guardrails or DEFAULT_GUARDRAILS
    run_dir = LIO.init_run_dir(Path(runs_dir))
    hist = run_dir / "history.jsonl"

    # --- Bootstrap
    boot = llm_adapter.bootstrap(user_prompt)
    world = boot["world_state_initial"]
    role_specs = boot["role_specs"]

    LIO.write_jsonl(hist, {"phase": "bootstrap", "payload": boot})
    LIO.write_json(run_dir / "world_initial.json", world)
    LIO.write_json(run_dir / "role_specs.json", {"roles": role_specs})

    # message bus per run
    bus = MessageBus()

    # check optional LLM entrypoints
    f_msg_round = _maybe_llm("messaging_round")      # optional
    f_coord     = _maybe_llm("coordinate")           # optional

    # --- Ticks
    for t in range(1, ticks + 1):
        # =====================
        # Phase 0: GC messages
        # =====================
        bus.gc(t)

        # =====================
        # Phase 1: Messaging
        # =====================
        outboxes_all: Dict[str, List[Dict[str, Any]]] = {}
        inboxes_all: Dict[str, List[Dict[str, Any]]] = {}

        if f_msg_round:
            for spec in role_specs:
                role = spec.get("role_name", "")
                inbox = bus.inbox(role, t)
                inbox_json = bus.to_jsonable(inbox)
                inboxes_all[role] = inbox_json

                # LLM generates up to 2 messages
                payload = {
                    "ROLE_NAME": role,
                    "MANDATE": spec.get("mandate", ""),
                    "INCENTIVES": spec.get("incentives", ""),
                    "WORLD_SUMMARY_JSON": _world_summary(world),
                    "ROLE_INBOX_JSON": inbox_json
                }
                try:
                    res = f_msg_round(spec, _world_summary(world), inbox_json)  # if you implemented this signature
                except TypeError:
                    # fallback to prompt fill if your messaging_round expects a dict payload
                    from society_sim.engine.llm_adapter import _load_text, _fill  # local helper if exposed
                    tpl = _load_text(Path(__file__).resolve().parents[1] / "prompts" / "messaging_round.txt")
                    prompt = _fill(tpl, payload)
                    res = llm_adapter._call_adk(prompt, schema_file="messaging_round.schema.json")  # internal call

                outbox = res.get("outbox", []) if isinstance(res, dict) else []
                outboxes_all[role] = outbox

                # post to bus
                msgs = []
                for m in outbox:
                    msgs.append(Message(
                        sender=m["sender"],
                        receivers=m["receivers"],
                        intent=m["intent"],
                        content=m.get("content", {}) or {},
                        valid_until_tick=t + random.randint(1, 3)
                    ))
                bus.post_many(msgs)
                time.sleep(30)  # small pause between messaging_round calls

        LIO.write_json(run_dir / f"messages_tick_{t}.json", {
            "inboxes": inboxes_all,
            "outboxes": outboxes_all,
            "all_messages_visible": bus.to_jsonable(bus.all_for_tick(t))
        })
    
        # =====================
        # Phase 2: Coordination (agreements -> coordinated actions)
        # =====================
        coordinated_actions: List[Dict[str, Any]] = []
        accepted = COORD.extract_accepted_agreements(bus.all_for_tick(t))
        if f_coord and accepted:
            try:
                res = f_coord(_world_summary(world), accepted)  # if implemented as function
            except TypeError:
                # fallback: build prompt explicitly if your coordinate expects templated input
                from society_sim.engine.llm_adapter import _load_text, _fill
                tpl = _load_text(Path(__file__).resolve().parents[1] / "prompts" / "coordination.txt")
                prompt = _fill(tpl, {
                    "WORLD_SUMMARY_JSON": _world_summary(world),
                    "ACCEPTED_MSGS_JSON": accepted
                })
                res = llm_adapter._call_adk(prompt, schema_file="coordination.schema.json")
            coordinated_actions = res.get("coordinated_actions", []) if isinstance(res, dict) else []
        LIO.write_json(run_dir / f"agreements_tick_{t}.json", {"accepted": accepted, "coordinated_actions": coordinated_actions})
        # =====================
        # Phase 3: Role Decisions (each role proposes ONE action)
        # =====================
        decisions_raw: List[Dict[str, Any]] = []
        previews: List[Dict[str, Any]] = []
        for spec in role_specs:
            dec = llm_adapter.role_decision(spec, _world_summary(world))
            decisions_raw.append(dec)
            preview_world = IA.apply_effects(world, dec.get("expected_effects", {}))
            previews.append({"role_name": dec.get("role_name"), "action_name": dec.get("action_name"),
                             "pre_world": world, "post_world": preview_world})
            time.sleep(30)  # small pause between role_decision calls

        # add coordinated actions as if they were role decisions
        for ca in coordinated_actions:
            decisions_raw.append({
                "role_name": ca.get("by", "Coordinator"),
                "action_name": ca.get("action_name", "coordinated_action"),
                "goal": ca.get("goal", ""),
                "operational_plan": ca.get("operational_plan", ""),
                "expected_effects": ca.get("expected_effects", {}),
                "risk_notes": ca.get("risk_notes", ""),
                "justification": ca.get("justification", "")
            })

        # =====================
        # Phase 4: Arbitration & Apply
        # =====================
        filtered = []
        for dec, pv in zip(decisions_raw, previews + [None] * max(0, len(decisions_raw) - len(previews))):
            # recompute preview for coordinated items (pv may be None)
            if pv is None:
                preview_world = IA.apply_effects(world, dec.get("expected_effects", {}))
                pv = {"pre_world": world, "post_world": preview_world}
            if arbitration.violates_guardrails(pv["pre_world"], pv["post_world"], guardrails):
                continue
            if arbitration.is_negligible_change(pv["pre_world"], pv["post_world"], min_stock_pct=0.005):
                continue
            filtered.append(dec)

        ordered = arbitration.order_actions(filtered)

        for dec in ordered:
            world = IA.apply_effects(world, dec.get("expected_effects", {}))
        # =====================
        # Phase 5: Events
        # =====================
        world_after_events, ev_payload, ev_fired = events.forecast_and_apply(world)
        world = world_after_events

        # =====================
        # Phase 6: Log + snapshot
        # =====================
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
        time.sleep(20)  # to avoid rate limits
        
        

    # --- Final
    LIO.write_json(run_dir / "world_final.json", world)

    if hasattr(llm_adapter, "analyze"):
        from society_sim.engine import analyst
        analysis_payload = analyst.build_payload(run_dir, ticks)
        analysis = llm_adapter.analyze(analysis_payload)
        LIO.write_json(run_dir / "analysis.json", analysis)

    return run_dir

if __name__ == "__main__":
    run("World before 5000 BC", ticks=5)
