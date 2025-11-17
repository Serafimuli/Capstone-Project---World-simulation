"""
world_simulation.py
====================

This module contains a set of classes that together implement a simple,
hierarchical simulation of socio‑economic agents using Google's Agent
Development Kit (ADK).  The simulation is deliberately kept lightweight
so that you can extend and customise it for more sophisticated
scenarios.  The architecture follows a four‑layer hierarchy:

* **ArbiterAgent** – the top‑level orchestrator.  It controls the
  progression of time, creates and destroys nations, and injects
  world‑wide events into the simulation.  It sits at the root of the
  agent tree and delegates to its nation agents.
* **NationAgent** – represents a sovereign state.  A nation manages
  multiple guilds, collects aggregate statistics (e.g. population) and
  may enact policies that affect its guilds.  Nations can
  communicate with each other (e.g. for trade or diplomacy) by
  writing to the shared session state.
* **GuildAgent** – models a social group within a nation such as a
  profession, industry or social class.  Guilds manage a dynamic set
  of individuals and may create new individuals as the simulation
  progresses.  They also coordinate interactions between their
  members and other guilds within the same nation.
* **IndividualAgent** – represents a single person within the
  simulation.  Each individual keeps track of their own age and
  occupation and can update their personal state on each tick of the
  simulation.

The ADK encourages a multi‑agent architecture because composing
distinct `BaseAgent` instances into a hierarchy improves modularity
and clarity.  The official documentation notes that multi‑agent
systems allow complex applications to be broken down into smaller,
specialised agents that cooperate to achieve a larger goal【767960234285879†L221-L234】.  This simulation
mirrors that design: the arbiter delegates work down to nations,
nations delegate to guilds, and so on.  For truly complex workflows
you can subclass `BaseAgent` and override `_run_async_impl` to build
custom execution logic beyond the predefined `SequentialAgent`,
`ParallelAgent` or `LoopAgent` patterns【397522334317042†L213-L233】.

To use this script you will need to install the `google-adk` Python
package and configure any required API keys (e.g. for Gemini models)
according to the ADK documentation.  This example focuses on the
orchestration logic and uses simple placeholders rather than LLM
calls.  The simulation is asynchronous: each agent's execution is
implemented as an `async` generator to comply with the ADK runtime.

"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import AsyncGenerator, Dict, List, Optional, Any, Tuple

# Global reference to the arbiter used by management tools.  This is
# assigned in `run_simulation` when the simulation starts.
GLOBAL_ARBITER: Optional["ArbiterAgent"] = None

try:
    # These imports require the google-adk package.  They are kept inside
    # a try/except block so that this module can be imported for
    # illustration even if ADK is not installed.  When running the
    # simulation you must install google‑adk and remove the fallback
    # definitions.
    from google.adk.agents import BaseAgent
    from google.adk.runtime import Runner, Session, InvocationContext
    # Import the tool decorator if available.  Function tools allow agents
    # to expose custom Python functions to the underlying model.  When
    # imported successfully this decorator annotates our functions so ADK
    # automatically generates a tool schema for them.  In fallback mode
    # below we simply define a pass‑through decorator.
    from google.adk.tools import tool
except ImportError:
    # Fallback stubs for documentation and type checking only.
    class BaseAgent:
        """Minimal stand‑in for the ADK BaseAgent when ADK is unavailable."""

        def __init__(self, name: str, description: Optional[str] = None, sub_agents: Optional[List['BaseAgent']] = None) -> None:
            self.name = name
            self.description = description or ""
            self.sub_agents = sub_agents or []

        async def run_async(self, ctx: "InvocationContext") -> AsyncGenerator[object, None]:
            async for event in self._run_async_impl(ctx):
                yield event

        async def _run_async_impl(self, ctx: "InvocationContext") -> AsyncGenerator[object, None]:  # pragma: no cover
            if False:
                yield None
            return

    class Session:
        """Stub Session that holds a mutable state dictionary."""
        def __init__(self) -> None:
            self.state: Dict[str, any] = {}

    class InvocationContext:
        """Stub InvocationContext used by the fallback Runner."""
        def __init__(self, session: Session) -> None:
            self.session = session

    class Runner:
        """Fallback runner that simply invokes the agent's async generator."""
        async def run_async(self, agent: BaseAgent, user_message: str = "", max_iters: int = 1) -> AsyncGenerator[object, None]:
            # Create a basic session and context.  In real ADK usage the runner
            # handles sessions, events and state persistence.
            ctx = InvocationContext(Session())
            # Propagate a maximum iteration count into session state so the
            # ArbiterAgent can terminate.
            ctx.session.state["max_rounds"] = max_iters
            # Optionally record the initial user message (not used in this example).
            ctx.session.state["user_message"] = user_message
            async for event in agent.run_async(ctx):
                yield event

    # Fallback tool decorator used when the ADK is not installed.  It simply
    # returns the original function unchanged.  The real decorator from
    # google.adk.tools automatically inspects the function signature and
    # docstring to build a schema for LLMs【729359203937950†L252-L262】.
    def tool(func: Any) -> Any:
        return func


@dataclass
class Individual:
    """Simple data container representing a person in the simulation."""

    name: str
    age: int
    profession: str
    guild_name: str


class IndividualAgent(BaseAgent):
    """An agent representing a single individual.

    Individuals update their internal state (e.g. age) on each invocation.
    They can also write information into the shared session state for
    consumption by higher‑level agents.  This class intentionally does
    not perform LLM operations; instead it provides a scaffold for
    extended behaviour such as responding to prompts or using tools.
    """

    def __init__(self, name: str, age: int, profession: str, guild_name: str) -> None:
        super().__init__(name=name, description=f"Individual {name}")
        self.age = age
        self.profession = profession
        self.guild_name = guild_name
        # Track a simple wealth metric for each individual.  This could be
        # interpreted as income or savings.  Individuals earn wealth
        # through guild production and spend it to meet consumption needs.
        self.wealth: float = 0.0

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[object, None]:
        """Advance the individual's state by one time step.

        This implementation increments the individual's age and appends a
        textual update into the session state.  It yields no events of
        its own; however, you could extend it to yield ADK `Event`
        objects if you wish to surface intermediate updates in the
        runtime.

        Parameters
        ----------
        ctx : InvocationContext
            The invocation context provided by the ADK runtime.  Use
            `ctx.session.state` to persist information across agents.

        Yields
        ------
        object
            Currently yields nothing, but the generator is left in
            place to satisfy the ADK interface.
        """
        # Increment age as a simple state update.
        self.age += 1

        # Collect per‑individual resource consumption needs from global
        # simulation settings.  Each agent consumes a fixed amount of each
        # resource per time step.  The consumption values are stored in
        # session state by the arbiter when the simulation starts.  If not
        # present, default to an empty dict.
        consumption_rate: Dict[str, float] = ctx.session.state.get("individual_consumption", {})
        guild_consumption_log: Dict[str, float] = ctx.session.state.setdefault("guild_resource_consumed", {})
        # Deduct consumed resources from the guild's tally.  The nation
        # aggregates these values later to inform policy decisions.
        for resource, amount in consumption_rate.items():
            # Add up consumption for this guild.  Use setdefault to
            # initialise zero if not present.  Multiply by 1 because
            # consumption per individual.  If a guild runs out of a
            # resource, this could reduce individual health; in this
            # simple model we only track aggregate usage.
            total_used = guild_consumption_log.get(self.guild_name + ":" + resource, 0.0)
            total_used += amount
            guild_consumption_log[self.guild_name + ":" + resource] = total_used
        ctx.session.state["guild_resource_consumed"] = guild_consumption_log

        # Write a summary of this update into the session state.  Use
        # `setdefault` to ensure lists and dicts are initialised.
        updates: List[str] = ctx.session.state.setdefault("individual_updates", [])
        updates.append(f"{self.name} is now {self.age} years old (profession: {self.profession}).")
        ctx.session.state["individual_updates"] = updates

        # If you wish to incorporate more complex behaviour (e.g. using
        # LLMs or tools), this is where you would call them.  For
        # example, you might create a FunctionTool that simulates a
        # conversation or writes a log entry.  See the ADK docs for
        # guidance on custom tools.

        # This branch ensures the function is treated as an async
        # generator even though it yields nothing at runtime.
        if False:
            yield None
        return


# ----------------------------------------------------------------------------
# Tool definitions
#
# The functions below implement core mechanics of the socio‑economic
# simulation.  They are annotated with the `tool` decorator so that ADK
# automatically exposes them to LLM agents when available.  In fallback
# mode the decorator is a no‑op.  These tools calculate resource
# production and consumption, population dynamics (births and deaths)
# and trade between nations.

@tool
def produce_resources(guild_type: str, num_individuals: int, productivity: float = 1.0) -> Dict[str, float]:
    """Compute resource output for a guild.

    The amount and type of resources produced depends on the guild's
    profession.  For example, farmers produce food, miners produce
    materials, engineers produce energy and materials, and merchants
    generate wealth.  Production scales linearly with the number of
    individuals in the guild and can be adjusted by a productivity
    multiplier (e.g. due to technology or a world event).

    Args:
        guild_type: Name of the guild type (e.g. "Farmers", "Miners").
        num_individuals: Number of members in the guild.
        productivity: Multiplier applied to base production rates.

    Returns:
        Dict[str, float]: Amount of each resource produced.
    """
    # Base production rates per individual per timestep.  These values
    # reflect simplified productivity for illustrative purposes and
    # could be made more sophisticated by factoring in skills or
    # technology.
    base_rates: Dict[str, Dict[str, float]] = {
        "Farmers": {"food": 2.0},
        "Miners": {"materials": 2.0},
        "Engineers": {"energy": 1.0, "materials": 1.0},
        "Merchants": {"wealth": 3.0},
    }
    # Default to no production if unknown guild type.
    rates = base_rates.get(guild_type, {})
    production: Dict[str, float] = {}
    for resource, rate in rates.items():
        production[resource] = rate * num_individuals * productivity
    return production


@tool
def simulate_births_and_deaths(population: int, birth_rate: float = 0.02, death_rate: float = 0.01) -> Tuple[int, int]:
    """Simulate births and deaths within a population.

    This function applies simple proportional birth and death rates to
    a guild's population.  The number of births and deaths are
    calculated by multiplying the current population by their
    respective rates and rounding to the nearest integer.  It is
    inspired by population models where births and deaths are
    proportional to the current population size【454046116652781†L200-L216】.  A higher
    birth rate results in population growth, while a higher death rate
    results in decline.

    Args:
        population: Current number of individuals in the group.
        birth_rate: Fraction of the population giving birth per time step.
        death_rate: Fraction of the population dying per time step.

    Returns:
        Tuple[int, int]: A tuple of (births, deaths).
    """
    births = int(population * birth_rate)
    deaths = int(population * death_rate)
    return births, deaths


@tool
def consume_resources(num_individuals: int, consumption_rates: Dict[str, float]) -> Dict[str, float]:
    """Calculate total resources consumed by a population.

    Each individual consumes a fixed amount of various resources
    (food, materials, energy) per time step.  This helper multiplies
    the per‑individual consumption rates by the number of individuals
    to obtain aggregate consumption.  Nations can use this
    information to determine if they have enough resources and to
    inform policy decisions.

    Args:
        num_individuals: The size of the consuming population.
        consumption_rates: Mapping of resource name to per‑person consumption.

    Returns:
        Dict[str, float]: Total resources consumed.
    """
    total_consumption: Dict[str, float] = {}
    for resource, per_person in consumption_rates.items():
        total_consumption[resource] = per_person * num_individuals
    return total_consumption


@tool
def conduct_trade(nation_resources: Dict[str, Dict[str, float]], desired_threshold: float = 0.0) -> Dict[str, Dict[str, float]]:
    """Redistribute resources among nations to address surpluses and deficits.

    This simple trade algorithm averages each resource across all
    participating nations and then redistributes the surplus or
    deficit evenly so that each nation ends up with the same amount
    (above a desired threshold).  It is not meant to be an exact
    economic model but rather to illustrate how nations can trade to
    balance their resource levels.  Nations with more than the
    average supply provide resources to those below the average.

    Args:
        nation_resources: Mapping from nation name to its resources
            (each a mapping of resource name to quantity).
        desired_threshold: Minimum quantity of each resource that each
            nation should retain before trading surplus.  A value of
            zero means all available resources can be shared.

    Returns:
        Updated mapping of nation resources after trade.  The input
        dictionary is not mutated; a new dictionary is returned.
    """
    # Compute average amounts per resource across all nations.
    aggregated: Dict[str, float] = {}
    counts = len(nation_resources) if nation_resources else 1
    for resources in nation_resources.values():
        for resource, amount in resources.items():
            aggregated[resource] = aggregated.get(resource, 0.0) + amount
    average: Dict[str, float] = {res: total / counts for res, total in aggregated.items()}

    # Create a copy of nation_resources to avoid mutating the original.
    new_resources: Dict[str, Dict[str, float]] = {n: dict(res) for n, res in nation_resources.items()}

    for resource, avg_amount in average.items():
        # Compute total amount available for trading (supply above threshold).
        total_available = 0.0
        # Surpluses and deficits per nation for this resource.
        surpluses: Dict[str, float] = {}
        deficits: Dict[str, float] = {}
        for nation, resources in new_resources.items():
            qty = resources.get(resource, 0.0)
            # Only trade amounts exceeding the threshold.
            if qty > avg_amount and qty > desired_threshold:
                surplus = qty - max(avg_amount, desired_threshold)
                surpluses[nation] = surplus
                total_available += surplus
            elif qty < avg_amount:
                deficits[nation] = avg_amount - qty
        # Distribute available surplus proportionally to deficits.
        for nation, deficit in deficits.items():
            if total_available > 0:
                transfer = min(deficit, total_available * (deficit / sum(deficits.values())))
            else:
                transfer = 0.0
            new_resources[nation][resource] = new_resources[nation].get(resource, 0.0) + transfer
            total_available -= transfer
        # Deduct transferred amounts from surplus nations.
        for nation, surplus in surpluses.items():
            deduction = min(surplus, average[resource] - new_resources[nation].get(resource, 0.0))
            new_resources[nation][resource] = max(desired_threshold, new_resources[nation].get(resource, 0.0) - deduction)

    return new_resources


# -----------------------------------------------------------------------------
# Entity management tools
#
# The following tools allow guilds, nations and the arbiter to create and
# delete agents dynamically.  They operate on the global `GLOBAL_ARBITER`
# instance and modify the simulation structure at runtime.  These tools
# return descriptive strings so that an agent can relay confirmation or
# errors back to the user or other agents.

@tool
def create_individual_agent(guild_name: str, name: str, age: int, profession: str) -> Dict[str, str]:
    """Create a new individual agent within a specified guild.

    The function looks up the guild by name across all nations registered
    under the global arbiter and invokes its `create_individual` method.

    Args:
        guild_name: Name of the guild to add the individual to.
        name: Name of the individual.
        age: Starting age of the individual.
        profession: Profession or role of the individual.

    Returns:
        Dict[str, str]: A dictionary containing a status message.
    """
    if GLOBAL_ARBITER is None:
        return {"status": "error", "message": "Arbiter not initialised."}
    # Find the guild in any nation.
    for nation in GLOBAL_ARBITER.nations.values():
        guild = nation.guilds.get(guild_name)
        if guild is not None:
            guild.create_individual(name, age, profession)
            return {"status": "success", "message": f"Created individual {name} in guild {guild_name}."}
    return {"status": "error", "message": f"Guild {guild_name} not found."}


@tool
def delete_individual_agent(guild_name: str, individual_name: str) -> Dict[str, str]:
    """Delete an individual agent from a specified guild.

    Args:
        guild_name: Name of the guild to remove the individual from.
        individual_name: Name of the individual to delete.

    Returns:
        Dict[str, str]: A dictionary containing a status message.
    """
    if GLOBAL_ARBITER is None:
        return {"status": "error", "message": "Arbiter not initialised."}
    for nation in GLOBAL_ARBITER.nations.values():
        guild = nation.guilds.get(guild_name)
        if guild is not None:
            for i, ind in enumerate(guild.individuals):
                if ind.name == individual_name:
                    guild.individuals.pop(i)
                    return {"status": "success", "message": f"Deleted individual {individual_name} from guild {guild_name}."}
            return {"status": "error", "message": f"Individual {individual_name} not found in guild {guild_name}."}
    return {"status": "error", "message": f"Guild {guild_name} not found."}


@tool
def create_guild_agent(nation_name: str, guild_name: str) -> Dict[str, str]:
    """Create a new guild within a specified nation.

    Args:
        nation_name: Name of the nation to add the guild to.
        guild_name: Name of the new guild.

    Returns:
        Dict[str, str]: A dictionary containing a status message.
    """
    if GLOBAL_ARBITER is None:
        return {"status": "error", "message": "Arbiter not initialised."}
    nation = GLOBAL_ARBITER.nations.get(nation_name)
    if nation is None:
        return {"status": "error", "message": f"Nation {nation_name} not found."}
    if guild_name in nation.guilds:
        return {"status": "error", "message": f"Guild {guild_name} already exists in nation {nation_name}."}
    nation.create_guild(guild_name)
    return {"status": "success", "message": f"Created guild {guild_name} in nation {nation_name}."}


@tool
def delete_guild_agent(nation_name: str, guild_name: str) -> Dict[str, str]:
    """Delete a guild from a specified nation.

    Args:
        nation_name: Name of the nation to remove the guild from.
        guild_name: Name of the guild to delete.

    Returns:
        Dict[str, str]: A dictionary containing a status message.
    """
    if GLOBAL_ARBITER is None:
        return {"status": "error", "message": "Arbiter not initialised."}
    nation = GLOBAL_ARBITER.nations.get(nation_name)
    if nation is None:
        return {"status": "error", "message": f"Nation {nation_name} not found."}
    if guild_name not in nation.guilds:
        return {"status": "error", "message": f"Guild {guild_name} not found in nation {nation_name}."}
    del nation.guilds[guild_name]
    return {"status": "success", "message": f"Deleted guild {guild_name} from nation {nation_name}."}


@tool
def create_nation_agent(nation_name: str) -> Dict[str, str]:
    """Create a new nation under the arbiter.

    Args:
        nation_name: Name of the new nation.

    Returns:
        Dict[str, str]: A dictionary containing a status message.
    """
    if GLOBAL_ARBITER is None:
        return {"status": "error", "message": "Arbiter not initialised."}
    if nation_name in GLOBAL_ARBITER.nations:
        return {"status": "error", "message": f"Nation {nation_name} already exists."}
    GLOBAL_ARBITER.create_nation(nation_name)
    return {"status": "success", "message": f"Created nation {nation_name}."}


@tool
def delete_nation_agent(nation_name: str) -> Dict[str, str]:
    """Delete a nation from the arbiter.

    Args:
        nation_name: Name of the nation to delete.

    Returns:
        Dict[str, str]: A dictionary containing a status message.
    """
    if GLOBAL_ARBITER is None:
        return {"status": "error", "message": "Arbiter not initialised."}
    if nation_name not in GLOBAL_ARBITER.nations:
        return {"status": "error", "message": f"Nation {nation_name} does not exist."}
    GLOBAL_ARBITER.destroy_nation(nation_name)
    return {"status": "success", "message": f"Deleted nation {nation_name}."}


class GuildAgent(BaseAgent):
    """Represents a guild (social group) within a nation.

    Each guild holds a collection of individuals.  On each run it
    delegates to its individual agents and may create new individuals
    according to simple probabilistic rules.  Guilds also write
    aggregate data into the session state so that nations and the
    arbiter can monitor demographic trends.
    """

    def __init__(self, name: str, nation_name: str) -> None:
        super().__init__(name=name, description=f"Guild {name}")
        self.nation_name = nation_name
        self.individuals: List[IndividualAgent] = []
        # Keep an internal counter to assign unique names for new
        # individuals created by this guild.  This ensures that new
        # individuals have deterministic names across runs.
        self._spawn_count: int = 0
        # Track local resource stockpile for the guild.  Nations
        # aggregate these values later.  Keys are resource names,
        # values are floats.
        self.resources: Dict[str, float] = {}

    def create_individual(self, name: str, age: int, profession: str) -> IndividualAgent:
        """Create a new individual and add them to this guild.

        Parameters
        ----------
        name : str
            Name of the new individual.
        age : int
            Starting age of the new individual.
        profession : str
            Occupation of the new individual.

        Returns
        -------
        IndividualAgent
            The newly created individual agent.
        """
        new_individual = IndividualAgent(name, age, profession, self.name)
        self.individuals.append(new_individual)
        return new_individual

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[object, None]:
        """Run all individuals in this guild and possibly create new ones.

        On each invocation, the guild runs each individual agent in
        sequence and yields any events they produce.  After updating
        existing members, the guild may create a new individual with a
        small probability to simulate births or new entrants into the
        profession.  The guild then records its current population
        within the session state under `guild_population`.
        """
        # Run each individual in sequence, propagating events up the hierarchy.
        for individual in list(self.individuals):
            async for event in individual.run_async(ctx):
                # Pass through any events yielded by the individual.
                yield event

        # ---------------------------------------------------------------------
        # Resource production and consumption
        #
        # Compute resources produced by this guild based on its type and
        # number of individuals.  Productivity may be modified by
        # global events, which the arbiter can store in
        # `ctx.session.state["productivity_modifiers"]` as a mapping
        # {guild_type: multiplier}.  If not specified, assume 1.0.
        modifiers: Dict[str, float] = ctx.session.state.get("productivity_modifiers", {})
        productivity = modifiers.get(self.name, 1.0)
        production = produce_resources(self.name, len(self.individuals), productivity=productivity)
        # Update the guild's local stockpile and record production in session state.
        for resource, amount in production.items():
            self.resources[resource] = self.resources.get(resource, 0.0) + amount
        guild_resources = ctx.session.state.setdefault("guild_resources", {})
        guild_resources[self.name] = dict(self.resources)
        ctx.session.state["guild_resources"] = guild_resources

        # Compute aggregate consumption for this guild.  Use the per‑person
        # consumption rates stored in session state.  If absent, default to
        # an empty dict (no consumption).
        per_person_consumption: Dict[str, float] = ctx.session.state.get("individual_consumption", {})
        consumption = consume_resources(len(self.individuals), per_person_consumption)
        # Deduct consumption from the guild's stockpile, ensuring
        # resources do not go negative.  If insufficient resources are
        # available, individuals may lose health or die in a more
        # sophisticated simulation; here we simply cap at zero.
        for resource, amount in consumption.items():
            self.resources[resource] = max(0.0, self.resources.get(resource, 0.0) - amount)
        # Record consumption in session state.
        guild_consumption_log = ctx.session.state.setdefault("guild_consumption", {})
        guild_consumption_log[self.name] = consumption
        ctx.session.state["guild_consumption"] = guild_consumption_log

        # ---------------------------------------------------------------------
        # Population dynamics
        #
        # Determine births and deaths for this guild based on rates in
        # session state.  Nations or the arbiter can set these
        # parameters.  Use reasonable defaults if they are missing.
        birth_rate = ctx.session.state.get("birth_rate", 0.02)
        death_rate = ctx.session.state.get("death_rate", 0.01)
        births, deaths = simulate_births_and_deaths(len(self.individuals), birth_rate=birth_rate, death_rate=death_rate)

        # Create new individuals for each birth via the management tool.
        # Use the guild's internal spawn counter to generate unique names.
        # Assign profession based on the guild type (singular form).
        for _ in range(births):
            self._spawn_count += 1
            new_person_name = f"{self.name}_Person_{self._spawn_count}"
            profession_name = self.name[:-1] if self.name.endswith("s") else self.name
            result = create_individual_agent(self.name, new_person_name, 0, profession_name)
            # Log the result into guild events.  The tool returns a dict with a status message.
            events: List[str] = ctx.session.state.setdefault("guild_events", [])
            events.append(result.get("message", f"Created individual {new_person_name} in guild {self.name}."))
            ctx.session.state["guild_events"] = events

        # Remove individuals for each death via the management tool.  If there
        # are fewer individuals than deaths, just remove all remaining.
        deaths = min(deaths, len(self.individuals))
        for _ in range(deaths):
            # Choose a random individual to die.
            victim = random.choice(self.individuals)
            result = delete_individual_agent(self.name, victim.name)
            # Log the death event.
            death_events: List[str] = ctx.session.state.setdefault("guild_events", [])
            death_events.append(result.get("message", f"Deleted individual {victim.name} from guild {self.name}."))
            ctx.session.state["guild_events"] = death_events

        # Record current guild population into the session state for monitoring.
        guild_pop = ctx.session.state.setdefault("guild_population", {})
        guild_pop[self.name] = len(self.individuals)
        ctx.session.state["guild_population"] = guild_pop

        # Print a summary of the guild's activities for this timestep.  This
        # output includes production, consumption, births, deaths and
        # current population to provide a clear step‑by‑step trace of the
        # simulation.
        try:
            print(
                f"Guild {self.name} (Nation {self.nation_name}) — produced {production}, consumed {consumption}, "
                f"births {births}, deaths {deaths}, population {len(self.individuals)}"
            )
        except Exception:
            # Printing may fail in some async contexts; ignore errors.
            pass

        if False:
            yield None
        return


class NationAgent(BaseAgent):
    """Represents a nation within the simulation.

    Nations manage multiple guilds and collect aggregate metrics such as
    total population.  They may implement policies that influence
    guild behaviour or interact with other nations.  The example
    provided here simply runs each guild sequentially and records
    population statistics.  You can extend it to include complex
    policy logic, diplomatic interactions or economic modelling.
    """

    def __init__(self, name: str) -> None:
        super().__init__(name=name, description=f"Nation {name}")
        self.guilds: Dict[str, GuildAgent] = {}
        self.policies: Dict[str, Any] = {}
        self.population_history: List[int] = []
        # Aggregate resource holdings for this nation.  Keys are resource
        # names; values are floats.  Guilds update their own stockpiles;
        # the nation sums them after running guilds.
        self.resources: Dict[str, float] = {}
        # Internal counter to assign unique names to dynamically created guilds.
        self._guild_spawn_count: int = 0

    def create_guild(self, name: str) -> GuildAgent:
        """Create a new guild within this nation."""
        guild = GuildAgent(name, nation_name=self.name)
        self.guilds[name] = guild
        return guild

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[object, None]:
        """Run all guilds in this nation and collect statistics.

        The nation sequentially invokes each guild's `run_async` method
        and yields any events returned by the guilds.  After all guilds
        have run, the nation computes its total population and writes
        this figure into the session state.  This method could be
        extended to implement policy adjustments (e.g. taxation,
        subsidies) or to react to international events.
        """
        # Run each guild sequentially.
        for guild in list(self.guilds.values()):
            async for event in guild.run_async(ctx):
                yield event

        # Aggregate current population across all guilds.
        total_population = sum(len(guild.individuals) for guild in self.guilds.values())
        self.population_history.append(total_population)

        # Write the population into session state so the arbiter can read it.
        nation_pop = ctx.session.state.setdefault("nation_population", {})
        nation_pop[self.name] = total_population
        ctx.session.state["nation_population"] = nation_pop

        # Aggregate resources from guild stockpiles.  Reset the
        # nation's resource dictionary and sum each guild's resources.
        self.resources = {}
        for guild in self.guilds.values():
            for resource, amount in guild.resources.items():
                self.resources[resource] = self.resources.get(resource, 0.0) + amount
        # Write nation resources into session state for global use.
        nation_res = ctx.session.state.setdefault("nation_resources", {})
        nation_res[self.name] = dict(self.resources)
        ctx.session.state["nation_resources"] = nation_res

        # Simple policy logic: adjust global birth and death rates based on
        # per‑capita food availability.  If food per capita is low,
        # decrease birth rate and increase death rate; if food is
        # abundant, encourage growth.  Nations could define their own
        # policy by overriding this code or by setting values in
        # `self.policies`.  Default rates come from the session state.
        global_birth = ctx.session.state.get("birth_rate", 0.02)
        global_death = ctx.session.state.get("death_rate", 0.01)
        food = self.resources.get("food", 0.0)
        per_capita_food = food / total_population if total_population > 0 else 0.0
        if per_capita_food < 1.0:
            # Scarcity: raise death rate and lower birth rate.
            global_birth = max(0.0, global_birth * 0.8)
            global_death = global_death * 1.2
        else:
            # Abundance: encourage births and reduce deaths slightly.
            global_birth = global_birth * 1.1
            global_death = max(0.0, global_death * 0.9)
        ctx.session.state["birth_rate"] = global_birth
        ctx.session.state["death_rate"] = global_death

        # Delete any guilds that have no members.  Use the deletion tool
        # to ensure proper cleanup.  Iterate over a copy of the
        # dictionary to avoid modification while iterating.
        for guild_name in list(self.guilds.keys()):
            guild = self.guilds[guild_name]
            if len(guild.individuals) == 0:
                result = delete_guild_agent(self.name, guild_name)
                # Log deletion event if successful.
                if result.get("status") == "success":
                    events: List[str] = ctx.session.state.setdefault("nation_events", [])
                    events.append(result.get("message"))
                    ctx.session.state["nation_events"] = events

        # Create a new guild if the average size of existing guilds
        # exceeds 10 and the nation has fewer than 5 guilds.  This
        # encourages diversification of professions as the population
        # grows.  Use the creation tool and assign a unique name.
        if self.guilds:
            avg_size = total_population / len(self.guilds)
            if avg_size > 10 and len(self.guilds) < 5:
                self._guild_spawn_count += 1
                new_guild_name = f"{self.name}_Guild_{self._guild_spawn_count}"
                result = create_guild_agent(self.name, new_guild_name)
                if result.get("status") == "success":
                    events: List[str] = ctx.session.state.setdefault("nation_events", [])
                    events.append(result.get("message"))
                    ctx.session.state["nation_events"] = events

        # Print a summary of the nation's state for this timestep.
        try:
            print(
                f"Nation {self.name} — population {total_population}, resources {self.resources}, "
                f"birth_rate {global_birth:.4f}, death_rate {global_death:.4f}, guilds {list(self.guilds.keys())}"
            )
        except Exception:
            pass

        # Placeholder for inter‑nation communication or policy logic.  For
        # example, nations could read other nations' population from
        # `ctx.session.state["nation_population"]` and decide to form
        # alliances or trade agreements.  Such logic would likely involve
        # setting additional keys in the session state or even creating
        # new sub‑agents on the fly.

        if False:
            yield None
        return


class ArbiterAgent(BaseAgent):
    """The top‑level agent controlling the simulation.

    The arbiter maintains a dictionary of nations and a list of
    world‑wide events.  On each invocation it advances the global time
    by one unit, possibly creates or destroys nations, and then runs
    each nation agent.  After running the nations it collects
    statistics and writes them into the session state.  The arbiter
    demonstrates how to implement a custom agent: it overrides
    `_run_async_impl` to define its own asynchronous control flow
    rather than using one of the predefined workflow agents【397522334317042†L213-L233】.
    """

    def __init__(self, name: str = "WorldArbiter") -> None:
        super().__init__(name=name, description="Master controller of the simulated world.")
        self.nations: Dict[str, NationAgent] = {}
        self.global_events: List[str] = []
        self.timestep: int = 0

    def create_nation(self, name: str) -> NationAgent:
        """Instantiate a new nation and register it under the arbiter."""
        nation = NationAgent(name)
        self.nations[name] = nation
        return nation

    def destroy_nation(self, name: str) -> None:
        """Remove a nation from the simulation.

        This method deletes the nation from the arbiter's registry and
        records the destruction as a global event.  If the nation does
        not exist a `ValueError` is raised.
        """
        if name not in self.nations:
            raise ValueError(f"Nation {name} does not exist and cannot be destroyed.")
        del self.nations[name]
        self.global_events.append(f"Nation {name} was destroyed.")

    def add_global_event(self, description: str) -> None:
        """Add an event that affects all nations."""
        self.global_events.append(description)

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[object, None]:
        """Advance the simulation by several discrete time steps.

        This method retrieves the number of rounds to simulate from the
        session state (key `max_rounds`), defaulting to one if not
        present.  For each round it increments the world clock, may
        inject global events, runs all nation agents, then writes
        accumulated global events into the session state.  Events from
        nation/guild/individual agents are yielded up to the runner.
        """
        max_rounds = int(ctx.session.state.get("max_rounds", 1))
        for _ in range(max_rounds):
            self.timestep += 1

            # Initialise default simulation parameters on the first iteration.
            # These defaults define per‑individual consumption and base birth
            # and death rates.  They can be overridden by nations or
            # external events.
            if self.timestep == 1:
                ctx.session.state.setdefault("individual_consumption", {"food": 1.0, "materials": 0.1, "energy": 0.2})
                ctx.session.state.setdefault("birth_rate", 0.02)
                ctx.session.state.setdefault("death_rate", 0.01)
                ctx.session.state.setdefault("productivity_modifiers", {})

            # Update global time in the session state.  This could be used
            # by nations or guilds to plan long‑term strategies.
            current_time = ctx.session.state.get("world_time", 0) + 1
            ctx.session.state["world_time"] = current_time

            # Determine if a global event occurs this timestep.  Every 5
            # timesteps we trigger a random event that modifies
            # productivity or demographic rates.  Events are permanent in
            # this simple model; more sophisticated simulations could
            # store event durations and revert changes when they expire.
            if self.timestep % 5 == 0:
                # Randomly choose an event type.
                event_types = ["drought", "tech_boom", "baby_boom", "pandemic"]
                event = random.choice(event_types)
                description: str
                # Retrieve current modifiers and rates.
                prod_mods: Dict[str, float] = ctx.session.state.setdefault("productivity_modifiers", {})
                birth_rate = ctx.session.state.get("birth_rate", 0.02)
                death_rate = ctx.session.state.get("death_rate", 0.01)
                if event == "drought":
                    # Reduce farmers' productivity.
                    prod_mods["Farmers"] = prod_mods.get("Farmers", 1.0) * 0.5
                    description = f"Drought reduces food production in all nations at timestep {self.timestep}."
                elif event == "tech_boom":
                    # Increase productivity for engineers and miners.
                    prod_mods["Engineers"] = prod_mods.get("Engineers", 1.0) * 1.2
                    prod_mods["Miners"] = prod_mods.get("Miners", 1.0) * 1.2
                    description = f"Technological breakthrough boosts production at timestep {self.timestep}."
                elif event == "baby_boom":
                    # Increase birth rate globally.
                    birth_rate *= 1.5
                    description = f"Baby boom increases birth rates at timestep {self.timestep}."
                else:  # pandemic
                    death_rate *= 1.5
                    description = f"Pandemic increases death rates at timestep {self.timestep}."
                # Update session state with modified values.
                ctx.session.state["productivity_modifiers"] = prod_mods
                ctx.session.state["birth_rate"] = birth_rate
                ctx.session.state["death_rate"] = death_rate
                self.add_global_event(description)

            # Create or destroy nations at random to illustrate dynamic
            # changes in the world.  This logic can be customised or
            # removed entirely.  Use small probabilities to avoid
            # destabilising the simulation.
            if random.random() < 0.05:
                # Create a new nation with a unique name via the tool.  The
                # global arbiter manages unique naming implicitly in the tool.
                nation_name = f"Nation_{len(self.nations) + 1}"
                result = create_nation_agent(nation_name)
                self.global_events.append(result.get("message", f"Created nation {nation_name}"))

            if self.nations and random.random() < 0.02:
                # Randomly destroy a nation via the tool.
                victim = random.choice(list(self.nations.keys()))
                result = delete_nation_agent(victim)
                self.global_events.append(result.get("message", f"Deleted nation {victim}"))

            # Run each nation agent.  Collect and propagate any events.
            for nation in list(self.nations.values()):
                # Nations may modify the session state, which is shared
                # across the entire simulation.  They can also yield
                # events; propagate them upwards.
                async for event in nation.run_async(ctx):
                    yield event

            # After all nations have run, perform a simple trade to
            # redistribute resources among nations.  This call uses the
            # conduct_trade tool defined earlier.  The session state
            # contains `nation_resources` keyed by nation name.
            nation_resources: Dict[str, Dict[str, float]] = ctx.session.state.get("nation_resources", {})
            if nation_resources:
                traded = conduct_trade(nation_resources, desired_threshold=0.0)
                ctx.session.state["nation_resources"] = traded
                # Update each nation's resource holdings with the traded values.
                for name, resources in traded.items():
                    if name in self.nations:
                        self.nations[name].resources = dict(resources)
                        # Also update each guild's local stockpile proportionally.
                        # Here we distribute the nation's resources evenly among its guilds
                        # for simplicity.  A more realistic model would allocate
                        # according to productivity or need.
                        guilds = list(self.nations[name].guilds.values())
                        if guilds:
                            for guild in guilds:
                                for res, qty in resources.items():
                                    guild.resources[res] = qty / len(guilds)

            # After all nations have run and trade is complete, record global events into
            # session state and then clear the event list.
            if self.global_events:
                global_event_log = ctx.session.state.setdefault("global_events", [])
                global_event_log.extend(self.global_events)
                ctx.session.state["global_events"] = global_event_log
                # Print global events for this timestep
                try:
                    print(f"Arbiter timestep {self.timestep} — global events: {self.global_events}")
                except Exception:
                    pass
                self.global_events.clear()

            # Print a summary of the arbiter's view at the end of each timestep.
            try:
                nation_names = list(self.nations.keys())
                print(
                    f"Arbiter timestep {self.timestep} — nations {nation_names}, world time {ctx.session.state.get('world_time')}, "
                    f"nation resources {ctx.session.state.get('nation_resources', {})}"
                )
            except Exception:
                pass

        if False:
            yield None
        return


async def run_simulation(num_steps: int = 10) -> None:
    """Helper coroutine to run the world simulation for a number of steps.

    This function initialises the arbiter and a few default nations and
    guilds, then uses the ADK runner to execute the simulation.  It
    prints out the session state after the simulation completes so you
    can inspect how the state evolved.  In a real application you
    would likely integrate this with a user interface or persist the
    state to a database.

    Parameters
    ----------
    num_steps : int
        Number of discrete time steps to simulate.  This value is
        stored in the session state under `max_rounds` and read by
        the ArbiterAgent.
    """
    arbiter = ArbiterAgent()
    # Register the arbiter in the global variable so that management tools
    # can access it.  Without this assignment the management tools will
    # report an error.
    global GLOBAL_ARBITER
    GLOBAL_ARBITER = arbiter

    # Create some initial nations and guilds to seed the simulation.
    nation_a = arbiter.create_nation("Alpha")
    guild_a1 = nation_a.create_guild("Farmers")
    guild_a1.create_individual("Alice", 30, "Farmer")
    guild_a1.create_individual("Bob", 25, "Farmer")
    guild_a2 = nation_a.create_guild("Engineers")
    guild_a2.create_individual("Charlie", 40, "Engineer")

    nation_b = arbiter.create_nation("Beta")
    guild_b1 = nation_b.create_guild("Miners")
    guild_b1.create_individual("Dana", 35, "Miner")
    guild_b1.create_individual("Eve", 20, "Miner")

    # Use the ADK runner to execute the simulation.  The runner
    # initialises a session and an invocation context, then streams
    # events as the arbiter runs.  We pass the desired number of
    # iterations via the `max_rounds` key in the session state.  A
    # real application might supply a user message here to prime the
    # conversation; this example does not need one.
    runner = Runner()
    async for _ in runner.run_async(agent=arbiter, user_message="", max_iters=num_steps):
        # Ignore intermediate events.  They would normally be handled
        # by the ADK runtime and surfaced to a user interface.
        pass

    # After completion, retrieve the final session state for
    # inspection.  Note: when using the real ADK runner the session
    # lives inside the context; the fallback runner stores the
    # session on its internal context object.
    # The following is specific to the fallback runner defined above.
    # In production you would access the session via the Runner or
    # within the agents themselves.
    # This check avoids mypy/linters complaining about missing attributes.
    if isinstance(runner, Runner) and hasattr(runner, "run_async"):
        # In the fallback runner we can't easily extract the session.
        # Instead, you might modify the fallback Runner to expose
        # session state or adapt this example to your environment.
        pass


if __name__ == "__main__":
    import asyncio
    # Run a short simulation when executed as a script.  The default
    # number of steps (10) can be adjusted as needed.
    asyncio.run(run_simulation(num_steps=10))