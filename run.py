# exemplu rapid (nu îl salva, doar ilustrativ)
from worldbuilder.core.world_state import WorldState
from worldbuilder.core.arbiter import ArbiterCore
from worldbuilder.core.state import StateAgentData
from worldbuilder.core.class_entity import ClassEntityData
from worldbuilder.core.individual import IndividualData, IndividualRole

world = WorldState()
arb = ArbiterCore()

s1 = arb.create_state(world, traits=["mercantil"])
s2 = arb.create_state(world, traits=["tehnologic"])

# clase
work = ClassEntityData(id=f"{s1}.WORK", state_id=s1, name="Workers")
pol  = ClassEntityData(id=f"{s1}.POL",  state_id=s1, name="Politicians")

world.states[s1].spawn_class(work)
world.states[s1].spawn_class(pol)

# indivizi
a1 = IndividualData(id=f"{s1}.WORK.a1", role=IndividualRole.WORKER, class_id=work.id, state_id=s1)
a2 = IndividualData(id=f"{s1}.POL.a1",  role=IndividualRole.POLITICIAN, class_id=pol.id,  state_id=s1)
work.spawn_agent(a1)
pol.spawn_agent(a2)

# agregare simplă pe clasă și efecte
demands = work.aggregate_demands()
lobby   = pol.aggregate_demands()
deltas = {s1: {"inventory": {"wheat": demands["output"]}, "morale": +0.01 - demands["pressure"]}}
world.apply_deltas(deltas)
world.tick += 1
print(world.log_tick())
