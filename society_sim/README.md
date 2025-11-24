# Society Simulation (LLM-driven World Model)

## 1. Problem
Simulate a small stylized world (resources, economy, state, society) over discrete ticks. Multiple institutional roles propose actions; exogenous events may occur. Need:
- Structured LLM outputs (no free-form text parsing pain).
- Deterministic application of numerical effects.
- Guardrails to prevent runaway collapse.
- Post-run analysis synthesizing trends.

## 2. Solution Overview
LLM acts as constrained JSON generator for:
- bootstrap (initial world + role_specs)
- per-role decision (expected_effects)
- messaging round (inter-role negotiation messages)
- coordination (aggregate accepted agreements into joint actions)
- events forecast (probabilistic exogenous events)
- final analysis (summarize run)

Local Python engine:
- Applies effects deterministically.
- Arbitrates actions (ordering, guardrail filtering, negligible-change pruning).
- Logs every tick (history.jsonl + world snapshots).
- Assembles analyst payload for final structured summary.

## 3. High-Level Flow

```
+---------+        +----------------+        +------------------+
|  Start  |----->  |  bootstrap()   |----->  |  role_specs[]    |
+---------+        +----------------+        +------------------+
                         | world_state_initial
                         v
                  +------------------+
                  |  Tick Loop (t)   |
                  +------------------+
      ┌────────────────────────────────────────────────────────────────┐
      │ 0. GC expired messages                                         │
      │ 1. messaging_round(): per role -> outbox messages              │
      │ 2. coordinate(): optional aggregated coordinated_actions       │
      │ 3. role_decision(): per role action with numeric effects       │
      │ 4. arbitration: guardrails + ordering + apply effects          │
      │ 5. events: forecast + sample + apply                          │
      │ 6. log: history.jsonl + world_tick_t.json                     │
      └────────────────────────────────────────────────────────────────┘
                         |
                         v
                  +------------------+
                  | world_final.json |
                  +------------------+
                         |
                         v
                  +------------------+
                  |  analyze()       |
                  +------------------+
                         |
                         v
                  +------------------+
                  | analysis.json    |
                  +------------------+
```

## 4. Core Modules

| Module | Responsibility |
|--------|----------------|
| engine/simulate.py | Orchestrates tick lifecycle |
| engine/llm_adapter.py | Prompt templating, schema loading, ADK calls |
| engine/interpret_actions.py | Parse & apply expected_effects safely (range clamping) |
| engine/arbitration.py | Prioritize & guardrail checks |
| engine/events.py | Event proposal sampling & application |
| engine/message_bus.py | Inter-role messaging with expiry |
| engine/coordination.py | Extract accepted agreements + build coordinated actions |
| engine/analyst.py | Aggregates per-tick data into analysis payload |
| engine/logging_io.py | Run directory + JSON/JSONL persistence |
| contracts/*.json | JSON Schemas enforcing structured output |
| prompts/*.txt | Fillable prompt templates with placeholders |

## 5. Data Contracts (Selected Keys)
- world dictionaries have top-level sections: Resources, Society, State, Economy, Infrastructure, Environment.
- expected_effects: { "Section.var": "+5" | "-2" | "+10%" } → parsed into deltas.
- Messages: { sender, receivers[], intent, content{}, valid_until_tick }.
- Events: { name, probability, expected_effects }.

## 6. Guardrails
Configured via DEFAULT_GUARDRAILS:
- min_stability
- min_legitimacy
- min_food
arbitration.violates_guardrails() blocks actions whose preview world drops below thresholds.

## 7. Rate Limiting
Sleep calls inserted after high-frequency LLM invocations (messaging_round, role_decision). Central throttle can be added in llm_adapter._call_adk. Adjust to provider limits.

## 8. Setup

### Prerequisites
- Python 3.10+
- Google ADK + Gemini access (API key in environment)
- pip install -r requirements (create if missing)

Example (Windows PowerShell):
```
python -m venv .venv
. .venv/Scripts/Activate.ps1
pip install google-genai google-adk jsonschema
```

### Environment
Create `.env` or set env vars:
```
GEMINI_API_KEY=your_key
GEMINI_MODEL=gemini-2.5-flash
```

### Run Simulation
```
python -m society_sim.engine.simulate "A future world after an AI revolution" --ticks 5
```
Outputs in runs/<timestamp>/:
- world_initial.json, world_tick_*.json, world_final.json
- history.jsonl (chronological events & decisions)
- analysis.json (final structured summary)
