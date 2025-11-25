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

### Example scenario - 5000 BC Scenario - Overview

Full scenario: /example_scenario_5000BC

#### 1. Scenario Bootstrap
- Era inferred: ~5000 BC (Early Neolithic / Fertile Crescent).
- Regional context: Small agrarian village with emerging specialization (farmers, hunter-gatherers, ritual authority, craftsmen).
- Initial world summary (key starting values):
  - Food 10,000; Timber 500; Manpower 2,000
  - Morale 0.60; Inequality 0.30; Religious Influence 0.70
  - Productivity 0.20; Trade Intensity 0.05; Tithe Rate 0.10
  - Stability 0.60; Legitimacy 0.70
  - Market Access 0.10; Harvest Quality 0.60

#### 2. Roles
| Role | Mandate | Core Incentives | Main Observables |
|------|---------|-----------------|------------------|
| Village Elder | Guide decisions & traditions | Harmony, respect | morale, inequality, food |
| Shaman/Priest | Rituals & spiritual guidance | Divine favor, influence | religious_influence, plague_pressure |
| Hunter-Gatherer Collective | Supplemental food | Max food, low effort | food, manpower, harvest_quality |
| Farmer Household | Cultivation & survival | Max production, avoid failure | food, productivity, harvest_quality |
| Craftsmen | Produce goods/tools | Tool output, trade access | timber, productivity, market_access |

#### 3. Tick Progression (World Snapshots)
| Tick | Food | Timber | Manpower | Morale | Inequality | Productivity | Trade Intensity | Stability | Market Access | Harvest Quality |
|------|------|--------|----------|--------|------------|-------------|-----------------|-----------|---------------|----------------|
| 0 (initial) | 10000 | 500.0 | 2000.0 | 0.60 | 0.30 | 0.20 | 0.05 | 0.60 | 0.10 | 0.60 |
| 1 | 11405.13 | 525.00 | 1681.88 | 0.73 | 0.25 | 0.29 | 0.05 | 0.60 | 0.11 | 0.68 |
| 2 | 12762.56 | 519.44 | 1177.25 | 0.99 | 0.17 | 0.42 | 0.14 | 0.62 | 0.20 | 0.68 |
| 3 | 14592.72 | 513.93 | 841.47 | 0.96 | 0.14 | 0.57 | 0.16 | 0.65 | 0.25 | 0.79 |
| 4 | 15875.93 | 468.41 | 548.59 | 1.00 | 0.14 | 0.75 | 0.18 | 0.68 | 0.33 | 0.81 |

Key deltas (Tick 0 → Tick 4):
- Food +58.8%
- Timber −6.3% (drawdown trend)
- Manpower −72.6% (major depletion)
- Morale +0.40 (near saturation)
- Inequality −0.16 (improved equity)
- Productivity +0.55 (strong growth)
- Trade Intensity +0.13 (driven by infrastructure + events)
- Market Access +0.23 (compound effects from tools + trade route event)
- Harvest Quality +0.21 (ritual & cultivation synergy)
- Tithe Rate reduced from 0.10 to 0.00 (progressive concession)

#### 4. Agreements & Coordination
Summary of accepted agreements per tick:
- Tick 1: None 
- Tick 2: 4 bilateral accepted (tithe −2%, food delivery +5%, surplus +3%, tools +2 units & barter −5%); 5 coordinated actions executed.
- Tick 3: 6 accepted; coordinated consolidation repeated; emphasis on recurring resource pooling.
- Tick 4: 7 accepted (adds aggregated multi-party agreement early); coordination maintained.
- Tick 5: 6 accepted including multi-party consolidation; pattern stabilizes.

Recurring multi-party pattern led by Village Elder:
“Community Resource Consolidation and Distribution” – always trades small % food/manpower for morale, trade intensity, slight stability uptick, inequality reduction (earlier tick), reinforcing social cohesion.

#### 5. Representative Actions (Tick 1–2 Highlights)
Tick 1 (bootstrap exploitation phase):
- Community Food Distribution: Food −5%, Morale +0.08, Inequality −0.05 (equity focus).
- Ritual for Harvest Blessing: Boost harvest quality & morale; manpower cost; disaster risk mitigation.
- Intensive Planting and Tending: Large food & productivity gains; manpower strain; minor morale trade-off.
- Expedition Foraged Goods: Additional food buffer; increased risk footprint.
- Tool Production and Resource Gathering: Productivity & timber scaling; labor drawdown.

Tick 2 (infrastructure + consolidation phase):
- Infrastructure Improvement (paths): Market access +0.03; modest morale bump; manpower diversion.
- Divination / Spiritual Oversight: Religious influence +0.05; modest plague pressure mitigation.
- Supplemental Food / Delivery Chains: Repeated food expansions (+4–8%) while steadily burning manpower.
- Coordinated Distribution: Aggregates agreements into morale +0.10, inequality −0.08, but consumes food (−6%) and manpower (−4%).
- Specialized Tool Production: Productivity leverage; timber consumption begins sustained depletion.

#### 6. Events
Events proposed Tick 2; one fired:
- Fired: “Minor Trade Route Expansion” → Trade Intensity +0.05, Market Access +0.03, Manpower −2%.
Effect: Reinforced ongoing tool/infrastructure synergy, accelerating economic integration at manpower cost.

No negative shock events fired early (risk buffers sustained); this allowed compounding agricultural & productivity gains.

#### 7. Cause → Effect Chains
1. Repeated coordinated redistribution (Village Elder) → Morale climbs toward 1.0 → Higher morale supports stability improvements despite manpower erosion.
2. Tithe reduction (from 0.10 to 0.08 then to 0.00) + Ritual & Divination → Religious Influence rises to 1.0 → Sustains community cohesion → Enables acceptance rates for multi-party agreements.
3. Specialized tools + trade route event + incremental path improvements → Market Access up (0.10 → 0.33) → Trade Intensity improves (0.05 → 0.18) → Productivity accelerates (0.20 → 0.75).
4. Intensive farming & foraging cycles → Food stock expansion (+58.8%) but severe manpower depletion (−72.6%) → Emerging labor scarcity risk for future defense / infrastructure.
5. Equity-focused distributions & reduced tithe → Inequality down (0.30 → 0.14) → Maintains legitimacy and stability plateaus (0.60 → 0.68) without needing coercive measures.

#### 8. Emerging Risks
- Manpower collapse: 2000 → 548.6 threatens capacity for future construction, defense, disease response.
- Timber drawdown: Gradual decline; crafting may become bottleneck if not replenished.
- Price level static (1.0) but latent resource diversification absent (no iron) limits technological trajectory.
- Over-optimization of morale (saturated) yields diminishing returns; future actions should rebalance toward resilience/defense.

#### 9. Performance Assessment
Strengths:
- High morale & low inequality reduce internal friction.
- Productivity and harvest quality gains compound resource security.
- Successful early economic proto-integration (market access).

Weaknesses:
- Labor exhaustion trajectory unsustainable.
- Resource portfolio narrow (no coinage, metals absent).
- Repeated food withdrawals for coordination risk future buffers if shocks occur.

#### 10. JSON Examples
##### role_specs.json
``` {
  "roles": [
    {
      "role_name": "Village Elder",
      "mandate": "Guide community decisions, resolve disputes, and maintain traditions.",
      "incentives": "Maximize community well-being, preserve social harmony, gain respect.",
      "observables": [
        "Society.population",
        "Society.morale",
        "Society.inequality",
        "Environment.harvest_quality",
        "Resources.food"
      ]
    },
    {
      "role_name": "Shaman/Priest",
      "mandate": "Perform religious rituals, interpret omens, and provide spiritual guidance.",
      "incentives": "Maximize divine favor, increase personal influence, ensure community's spiritual health.",
      "observables": [
        "Society.religious_influence",
        "Environment.plague_pressure",
        "Environment.disaster_risk"
      ],
      "notes": "Religious influence is high due to lack of scientific understanding."
    },
    {
      "role_name": "Hunter-Gatherer Collective",
      "mandate": "Provide supplementary food and resources through hunting and foraging.",
      "incentives": "Maximize individual food intake, minimize personal effort, avoid danger.",
      "observables": [
        "Resources.food",
        "Resources.manpower",
        "Environment.harvest_quality",
        "Environment.disaster_risk"
      ]
    },
    {
      "role_name": "Farmer Household",
      "mandate": "Cultivate crops and tend to livestock for subsistence and potential surplus.",
      "incentives": "Maximize food production, secure own family's survival, avoid crop failure.",
      "observables": [
        "Resources.food",
        "Economy.productivity",
        "Environment.harvest_quality",
        "Environment.winter_severity"
      ]
    },
    {
      "role_name": "Craftsmen",
      "mandate": "Produce tools, pottery, and other essential goods for the community.",
      "incentives": "Maximize creation of useful items, gain recognition for skill, trade for necessities.",
      "observables": [
        "Resources.timber",
        "Resources.iron",
        "Economy.productivity",
        "Infrastructure.market_access"
      ],
      "notes": "Iron is not yet widely available; focus is on stone and bone tools."
    }
  ]
}
```

##### agreements_tick_2.json
```
{
  "accepted": [
    {
      "by": "Shaman/Priest",
      "partners": [
        "Village Elder"
      ],
      "terms": {
        "tithe": "-2%"
      }
    },
    {
      "by": "Hunter-Gatherer Collective",
      "partners": [
        "Village Elder"
      ],
      "terms": {
        "food_delivery": "+5%"
      }
    },
    {
      "by": "Farmer Household",
      "partners": [
        "Village Elder"
      ],
      "terms": {
        "food_surplus_contribution": "+3%"
      }
    },
    {
      "by": "Craftsmen",
      "partners": [
        "Village Elder"
      ],
      "terms": {
        "tool_provision": "+2 units",
        "food_barter": "-5%"
      }
    }
  ],
  "coordinated_actions": [
    {
      "by": "Village Elder",
      "partners": [
        "Shaman/Priest",
        "Hunter-Gatherer Collective",
        "Farmer Household",
        "Craftsmen"
      ],
      "action_name": "Community Resource Management and Distribution",
      "goal": "Oversee the collection and equitable distribution of community resources, ensuring social harmony and well-being.",
      "operational_plan": "The Village Elder will coordinate the collection of the agreed-upon tithe reduction from the Shaman/Priest, the food delivery from the Hunter-Gatherer Collective, the surplus contribution from Farmer Households, and the tool provision/food barter from Craftsmen. This will be followed by a general distribution to maintain community morale.",
      "expected_effects": {
        "Society.morale": "+0.10",
        "Resources.food": "-6%",
        "Society.inequality": "-0.08",
        "Economy.trade_intensity": "+0.02",
        "Resources.manpower": "-4%",
        "State.stability": "+0.01"
      },
      "risk_notes": "Depletion of food stores, requiring careful management. Potential for disputes during distribution if perceived as unfair. Manpower is consumed in coordination and distribution.",
      "justification": "This action aggregates multiple agreements to maintain social cohesion and ensure resource flow. It directly addresses the Village Elder's mandate to guide decisions and preserve harmony, leveraging the various contributions to enhance community well-being."
    },
    {
      "by": "Shaman/Priest",
      "partners": [
        "Village Elder"
      ],
      "action_name": "Tithes Adjustment and Spiritual Oversight",
      "goal": "Adjust tithe collection as agreed and maintain community spiritual health.",
      "operational_plan": "Acknowledge the agreed tithe reduction of 2% as finalized with the Village Elder. Continue performing religious rituals and providing spiritual guidance to the community, ensuring the continued flow of divine favor.",
      "expected_effects": {
        "Society.religious_influence": "+0.05",
        "Economy.tithe_rate": "-0.02",
        "Society.morale": "+0.02"
      },
      "risk_notes": "Maintaining current levels of spiritual activity may require careful resource allocation from the accepted tithe.",
      "justification": "This action formalizes the tithe adjustment agreed upon with the Village Elder and ensures ongoing spiritual services. It aligns with the incentive to maximize divine favor and community spiritual health."
    },
    {
      "by": "Hunter-Gatherer Collective",
      "partners": [
        "Village Elder"
      ],
      "action_name": "Food Delivery and Resource Acquisition",
      "goal": "Deliver agreed-upon food resources and continue supplementary food acquisition.",
      "operational_plan": "Deliver the committed 5% food contribution to the Village Elder as agreed. Simultaneously, continue foraging and hunting activities to maximize individual food intake and minimize personal effort.",
      "expected_effects": {
        "Resources.food": "+4%",
        "Resources.manpower": "-3%",
        "Society.morale": "+0.02"
      },
      "risk_notes": "Expending manpower on delivery and continued foraging increases risk of exposure to dangers and reduces immediate availability for other community tasks.",
      "justification": "This action fulfills the agreed food delivery to the Village Elder and continues the collective's primary mandate. It balances community contribution with the incentive to maximize personal food intake."
    },
    {
      "by": "Farmer Household",
      "partners": [
        "Village Elder"
      ],
      "action_name": "Food Surplus Contribution and Cultivation",
      "goal": "Contribute surplus food and continue intensive crop cultivation for survival.",
      "operational_plan": "Deliver the agreed 3% food surplus contribution to the Village Elder. Continue intensive cultivation efforts to maximize food production and secure the family's survival.",
      "expected_effects": {
        "Resources.food": "+5%",
        "Economy.productivity": "+0.03",
        "Resources.manpower": "-4%",
        "Society.morale": "+0.01"
      },
      "risk_notes": "Reduced manpower due to intensive farming impacts other potential contributions. Over-reliance on current methods may not account for unforeseen environmental shifts.",
      "justification": "This action formalizes the surplus contribution to the Village Elder and continues the household's focus on maximizing food production. It directly supports the incentive to secure family survival and avoid crop failure."
    },
    {
      "by": "Craftsmen",
      "partners": [
        "Village Elder"
      ],
      "action_name": "Tool Provision and Barter",
      "goal": "Provide essential tools to the community and secure necessary resources through barter.",
      "operational_plan": "Deliver the agreed 2 units of tools to the Village Elder. In return, receive the agreed-upon food barter, which will be utilized to acquire other necessities. Continue tool production and resource gathering for future needs.",
      "expected_effects": {
        "Infrastructure.market_access": "+0.01",
        "Resources.food": "-2%",
        "Economy.productivity": "+0.02",
        "Resources.manpower": "-3%",
        "Resources.timber": "+2%"
      },
      "risk_notes": "Consumption of food resources for barter reduces immediate community stores. Manpower is utilized for delivery and production, potentially limiting other contributions.",
      "justification": "This action fulfills the agreement with the Village Elder, providing essential tools and securing vital food resources. It supports the craftsman's incentives to create useful items and trade for necessities, thereby increasing market access and productivity."
    }
  ]
}
```
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
