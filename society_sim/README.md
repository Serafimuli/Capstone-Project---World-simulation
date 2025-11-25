# Society Simulation (LLM-driven World Model)

## 1. Problem description
#### Goal

Build a societal simulation where an LLM-powered “State” agent bootstraps a world (time, region, institutions, resources), creates other role agents (e.g., Monarch, Nobility, Clergy, Peasants, Merchant Guild, Party Bureaucrat, Mayor), and then runs multi-tick interactions. Each role agent:

* Observes a compact world summary + recent messages,
* Communicates with other agents (propose/request/counter/accept/commit/inform),
* Chooses one action per tick (invented by the agent, not from a fixed menu),
* Trades off impacts across qualified variables (e.g., Resources.coinage, Society.morale, State.stability),
* Triggers events and reacts to their consequences.

At the end, an Analyst Agent computes metrics (deltas, volatility, risk flags), extracts cause→effect chains, and produces conclusions & recommendations.


### Why this is useful
* Policy Design & Impact Forecasting
    * Governments and NGOs can test policy scenarios before implementing them:
    * Example: “What happens if we raise agricultural taxes but increase subsidies for irrigation?” → Agents (Farmers, State Treasury, Merchants) simulate negotiations; Analyst reports effects on food, morale, and stability.
    * Value: Qualitative forecasting + transparency about cause-effect reasoning (why outcomes happen).

* Education & Training - A powerful teaching tool for:

    * Political science and economics classes — to show feedback loops (e.g., inequality ↔ stability ↔ growth).
    * History and governance — to explore alternate outcomes (“What if the monarchy had accepted the merchant guild’s tax proposal?”).
    * Ethics and negotiation — students can roleplay as agents or modify incentives to see how cooperation or conflict emerges.

* Disaster Response & Resilience Modeling

    * Can test how societies respond to crises (famine, war, natural disasters):
    * Example: “How will morale and production react to a drought event if religious influence is high and trade routes are blocked?” → Agents adapt strategies (rationing, propaganda, alliances).
    * Value: Helps humanitarian planners design resilient systems and communication strategies.

* Multi-Agent Coordination Research - For AI researchers:
    * Enables experiments on A2A communication protocols, cooperation, and consensus formation.
    * Tracks metrics like acceptance rate, negotiation depth, and coordinated-action success.
    * Value: Benchmark for testing multi-agent reasoning and governance alignment.

* Urban Planning & Smart Cities
    * Simulates urban ecosystems with citizens, industries, utilities, and local governments as agents:
    * Example: “If public transport investment rises by 15%, what happens to pollution, morale, and productivity?” → Analyst Agent quantifies outcomes and suggests future policies.

* Game Design & Narrative Generation
    * Game studios and storytellers can use it to generate emergent societies:
    * NPC factions negotiate and evolve naturally instead of following static scripts.
    * Each simulation run creates a living world with its own history and economy.
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

Phases per tick (sequential loop):

1) Messaging: Each role reads its inbox and emits 0–2 messages (propose, request, counter, accept, commit, inform) via a Message Bus.
2) Coordination: Agreements are extracted from message pairs (e.g., propose↔accept/commit). A Coordinator can turn accepted agreements into coordinated actions with shared effects.
3) Role Decisions: Every role proposes exactly one action (free-form name, plan, expected effects, risks, justification).
4) Arbitration & Apply: Guardrails + negligible-change filter + priority ordering; apply resulting effects to the World State.
5) Events: LLM proposes potential events; engine evaluates triggers and applies fired events.
6) Logging & Snapshots: Persist tick history, messages, agreements, world snapshots.
7) Analysis (end): The Analyst Agent computes metrics, causal chains, conclusions, recommendations.

### Example Scenario - Run 20251125-094734 (Neolithic Village)

Full run artifacts: runs/20251125-094734/

#### 1. Scenario Bootstrap
* Year estimate: ~6000 BCE (Fertile Crescent, early settled agriculture).
* Community description: agrarian village with ritual authority, farmer and hunter collectives, artisans, and a small security cohort.
* Initial world highlights:
  * Resources: Food 10,000; Timber 5,000; Manpower 5,000
  * Society: Morale 0.50; Inequality 0.20; Religious Influence 0.60
  * Economy: Productivity 0.20; Trade Intensity 0.10; Tithe Rate 0.20
  * State & Infrastructure: Stability 0.50; Borders Threat 0.30; Fortifications 0.10
  * Environment: Harvest Quality 0.60; Disaster Risk 0.30

#### 2. Roles

| Role | Mandate | Core Incentives | Main Observables |
|------|---------|-----------------|------------------|
| Tribal Elder | Maintain cohesion, mediate disputes, steer resource allocation | Survival, harmony, low strife | Society.morale, Environment.harvest_quality, Resources.food |
| Shaman/Priest | Lead rituals, interpret omens, guard spiritual well-being | Raise religious devotion, avoid divine displeasure | Society.religious_influence, Society.morale, Environment.disaster_risk |
| Hunter-Gatherer Collective | Supplement food via hunting/foraging | Maximise haul, keep land access | Resources.food, Resources.manpower, Environment.harvest_quality |
| Farmer Family Unit | Cultivate land and deliver community surplus | Maximise yield, secure land rights | Resources.food, Environment.harvest_quality, Economy.rents_rate |
| Craftsman | Produce tools, pottery, clothing | Acquire timber, trade for necessities, improve craft | Resources.timber, Economy.productivity, Resources.food |
| Village Watch | Patrol borders, deter raids | Keep threat low, maintain readiness | State.borders_threat, Infrastructure.fortifications, Society.population |

#### 3. Tick Progression (World Snapshots)

| Tick | Food | Timber | Manpower | Morale | Inequality | Productivity | Trade Intensity | Stability | Market Access | Harvest Quality |
|------|------|--------|----------|--------|------------|-------------|-----------------|-----------|---------------|----------------|
| 0 (initial) | 10000.00 | 5000.00 | 5000.00 | 0.50 | 0.20 | 0.20 | 0.10 | 0.50 | 0.20 | 0.60 |
| 1 | 11246.45 | 4837.88 | 4282.60 | 0.61 | 0.19 | 0.30 | 0.10 | 0.52 | 0.20 | 0.72 |
| 2 | 18919.07 | 4453.62 | 3456.58 | 0.80 | 0.14 | 0.39 | 0.10 | 0.54 | 0.20 | 0.92 |
| 3 | 25692.03 | 4076.89 | 2622.46 | 1.00 | 0.08 | 0.57 | 0.10 | 0.59 | 0.20 | 1.00 |
| 4 | 50576.04 | 3315.87 | 1796.61 | 1.00 | 0.00 | 0.80 | 0.10 | 0.69 | 0.20 | 1.00 |

Key deltas (Tick 0 -> Tick 4):

* Food +405.8%
* Timber -33.7% (sustained consumption for crafts and fortifications)
* Manpower -64.1% (continuous labour burn)
* Morale +0.50 and Religious Influence +0.40 (capped at 1.0)
* Inequality -0.20 (fully equalised)
* Productivity +0.60; Tithe Rate +0.20 (ritual focus tightened)
* Stability +0.19; Borders Threat -0.30; Fortifications +0.25
* Disaster Risk -0.18 while Harvest Quality +0.40 (stacked rituals plus agronomy)

#### 4. Agreements & Coordination

* Tick 1: Single tithe-support pact (Tribal Elder <-> Shaman/Priest) boosts tithe rate by +0.05.
* Ticks 2-4: Repeated five-way compacts (Elder with Farmers, Hunters, Craftsman, Watch) delivering food surpluses, tool output, and patrol manpower in exchange for land guarantees and better barter rates.
* Acceptance/commitment rate: 100% (34 messages; 9 propose/accept/commit events each, per `analysis.json`).
* Coordinated actions mirror agreements: tithe escalation, surplus redistribution, fortification reinforcement, and productivity boosts executed every tick after acceptance.

#### 5. Representative Actions

* **Tick 1:** "Intensified Foraging Expedition" (+12% food, -8% manpower) and "Enhanced Patrols" (-0.05 borders threat) establish early growth and security footing while two events fire (local scarcity counteracting foraging windfall, craftsmanship advancement boosting productivity).
* **Tick 2:** "Resource Surplus Management" (+18% food, morale up) combines with land-assured farmer/forager contributions; events include "Excellent Harvest Yield" (+20% food, +0.10 harvest quality).
* **Tick 3:** Celebration cycle (Tribal Elder + Shaman) converts surplus into morale 1.0; intensive seasonal foraging and soil enrichment keep harvest quality pegged at 1.0; four positive events trigger, compounding abundance and reducing threat.
* **Tick 4:** Massive storage and crop diversification push food above 50k; craftsman enhancement drains timber; security optimisation plus events ("successful_security_enhancements", etc.) drive stability to 0.69 and borders threat to 0.0.

#### 6. Events Fired

| Tick | Events Fired | Main Effects |
|------|--------------|--------------|
| 1 | localized_resource_scarcity; craftsmanship_advancement | Food −3%, price +0.03; productivity +0.05, timber −3% |
| 2 | excellent_harvest_yield | Food +20%, harvest_quality +0.10, morale +0.08 |
| 3 | perfect_harvest_and_resource_abundance; craftsmanship_breakthrough; communal_celebration_of_prosperity; no_significant_threat_detected | Food +25% then −7%; productivity +0.10; borders_threat −0.05; morale +0.10 |
| 4 | community_harmony_and_celebration; major_craftsmanship_advancement; successful_security_enhancements; soil_enrichment_and_future_planning | Morale +0.10; productivity +0.10; stability +0.05; harvest_quality +0.07 |

Overall: a virtuous cycle of favourable harvest events and craftsmanship breakthroughs offsets heavy manpower use while fortification/security events eliminate border risk.

#### 7. Cause -> Effect Highlights

1. Farmer plus hunter agreements -> sustained +25% food contributions -> food stockpile quadruples despite ritual consumption.
2. Recurring "Increase Tithe Collection" plus "Blessing" rituals -> religious influence and morale saturate -> zero inequality after repeated redistribution.
3. Craftsman initiatives plus advancement events -> productivity from 0.20 -> 0.80, albeit consuming 1,684 timber units.
4. Security compacts with Village Watch -> borders_threat 0.30 -> 0.00 and fortifications 0.10 -> 0.35; stability rises despite manpower drain.
5. Ritual plus agronomic actions (seed preservation, soil enrichment, crop diversification) -> harvest_quality climbs to 1.0 and disaster_risk falls to 0.12.

#### 8. Emerging Risks

* Severe manpower drawdown (-64%) leaves little labour slack for future shocks.
* Timber stock trending down; continued craftsmanship pushes toward scarcity.
* Price level creeps upward with each tool initiative (+0.05 across ticks 1-4).
* Heavy reliance on ritual tithe increase (0.20 -> 0.40) could trigger discontent if conditions worsen.

#### 9. Performance Assessment

* Morale/religious cohesion at ceiling; inequality eliminated.
* Resource abundance masks structural labour shortage and timber depletion.
* Negotiation workflow extremely efficient (all proposals accepted and coordinated) but homogenised; future scenarios may need adversarial incentives to stress-test guardrails.

#### 10. JSON Examples

##### role_specs.json (excerpt)

```json
{
  "roles": [
    {
      "role_name": "Tribal Elder",
      "mandate": "Maintain community cohesion, resolve disputes, and guide resource allocation based on tradition and wisdom.",
      "incentives": "Maximize community survival and harmony, avoid internal strife.",
      "observables": [
        "Society.population",
        "Society.morale",
        "Environment.harvest_quality",
        "Resources.food"
      ]
    },
    {
      "role_name": "Shaman/Priest",
      "mandate": "Perform rituals, interpret divine will, and maintain spiritual well-being of the community.",
      "incentives": "Maximize societal religious devotion and cohesion, avoid spiritual disfavor.",
      "observables": [
        "Society.religious_influence",
        "Society.morale",
        "Environment.disaster_risk"
      ]
    },
    {
      "role_name": "Hunter-Gatherer Collective",
      "mandate": "Provide supplementary food and resources through hunting and gathering, respecting community land use.",
      "incentives": "Maximize individual and group resource acquisition, avoid conflict with farmers.",
      "observables": [
        "Resources.food",
        "Environment.harvest_quality",
        "Resources.manpower"
      ]
    }
  ]
}
```

##### agreements_tick_2.json (excerpt)

```json
{
  "accepted": [
    {
      "by": "Tribal Elder",
      "partners": ["Shaman/Priest"],
      "terms": {
        "tithe_support": "+5%"
      }
    },
    {
      "by": "Farmer Family Unit",
      "partners": ["Tribal Elder"],
      "terms": {
        "food_contribution": "+10%",
        "land_usage_rights": "guaranteed"
      }
    },
    {
      "by": "Hunter-Gatherer Collective",
      "partners": ["Tribal Elder"],
      "terms": {
        "food_contribution": "+15%",
        "land_access_guarantee": "maintained"
      }
    },
    {
      "by": "Craftsman",
      "partners": ["Tribal Elder"],
      "terms": {
        "tool_provision": "+10%",
        "food_exchange_rate": "-5%"
      }
    }
  ],
  "coordinated_actions": [
    {
      "by": "Tribal Elder",
      "partners": ["Shaman/Priest"],
      "action_name": "Increase Tithe Collection and Spiritual Support",
      "expected_effects": {
        "Economy.tithe_rate": "+0.05",
        "Society.religious_influence": "+0.05"
      }
    },
    {
      "by": "Farmer Family Unit",
      "partners": ["Tribal Elder"],
      "action_name": "Increased Food Contribution and Land Use Assurance",
      "expected_effects": {
        "Resources.food": "+10%",
        "Economy.rents_rate": "+0.01",
        "Society.inequality": "-0.01",
        "Resources.manpower": "-1%"
      }
    }
  ]
}
```
## 3. High-Level Flow

```text
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

## 6. Rate Limiting
Sleep calls inserted after high-frequency LLM invocations (messaging_round, role_decision). Central throttle can be added in llm_adapter._call_adk. Adjust to provider limits.

## 7. Setup

### Prerequisites
- Python 3.10+
- Google ADK + Gemini access (API key in environment)
- pip install -r requirements 

Example (Windows PowerShell):
```
python -m venv .venv
. .venv/Scripts/Activate.ps1
pip install -r requirements 
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
