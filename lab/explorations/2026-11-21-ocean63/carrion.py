"""A versioned environmental extension: natural deaths leave drifting, edible bodies."""
import copy
import math

import numpy as np

from apparatus import Enclosure63, E38_INPUT, read, seed_from_adult
from lab.tools.ocean import difference
from lab.tools.ocean_material import MaterialOcean

SCHEMA = "threemind.ocean-carrion-state/1"


class Carrion63(MaterialOcean, Enclosure63):
    """Material enclosure /2 plus an explicit corpse and food ledger; no Core intervention."""
    def __init__(self, protocol, *, state=None, images=None, **kwargs):
        self.carcasses = {}
        self.dead_core_debits = {}
        self.carrion_contacts = {}
        self.carrion_received = {}
        if state is not None:
            if state.get("schema") != SCHEMA:
                raise ValueError("a complete carrion-world snapshot is required")
            self.carcasses = {int(k):v.copy() for k,v in state["carcasses"].items()}
            self.dead_core_debits = {int(k):v for k,v in state["dead_core_debits"].items()}
            self.carrion_contacts = {(a,b):t for a,b,t in state["contacts"]}
            self.carrion_received = {int(k):v for k,v in state["carrion_received"].items()}
            state = state["material"]
        super().__init__(protocol,state=state,images=images,**kwargs)
        self.totals.setdefault("carrion_heat",0.0)
        self.totals.setdefault("carrion_shell_heat",0.0)
        self.totals.setdefault("carrion_meals",0)

    def step(self, record=None):
        def death_records(row):
            for event in list(row["events"]):
                if event["kind"] != "consciousness_dead":
                    continue
                i = event["individual"]
                b = self.bodies[i]
                if b.consumed_by is not None:
                    continue  # already eaten alive; there is no second body
                if i in self.carcasses or i in self.dead_core_debits:
                    raise RuntimeError("duplicate death")
                reserve = self.engines[i].metrics()["energy"]["reserve"]
                self.carcasses[i] = dict(death_us=self.time_us, core_remaining=reserve)
                self.dead_core_debits[i] = 0.0
                row["events"].append(dict(kind="carcass_formed",time_us=self.time_us,individual=i,
                    position=b.position.copy(),body_reserve=b.storage,material=self.body_material[i],
                    core_remaining=reserve))
            if record:
                record(row)
        return super().step(death_records)

    def _predation(self, active):
        super()._predation(active)
        now,p = self.time_us,self.p
        contacts = {}
        for i,corpse in list(self.carcasses.items()):
            body = self.bodies[i]
            flow,_ = self.environment(body.position)
            body.position = ((np.asarray(body.position)+flow*(p.period_us/1e6)) % p.side_m).tolist()
            body.velocity = flow.tolist()
            body.angular_velocity = 0.0
            feeding = []
            for j in active:
                eater = self.bodies[j]
                if not eater.physical:
                    continue
                d = difference(body.position,eater.position,p.side_m)
                if float(d@d) > (2*(body.radius+eater.radius)+p.contact_skin_m)**2:
                    continue
                gap,_,_ = self.geometry(j,i)
                if gap > p.contact_skin_m:
                    continue
                eater.contact = 1.0
                start = self.carrion_contacts.get((i,j),now)
                contacts[i,j] = start
                if (i,j) not in self.carrion_contacts:
                    self.events.append(dict(kind="carcass_contact",time_us=now,individual=j,carcass=i))
                if now-start >= p.engulf_dwell_us*(1+p.shell_time_factor*body.shell):
                    feeding.append((start,j))
            # Longest uninterrupted contact first. Break simultaneous contacts by fixed ID.
            for _,j in sorted(feeding):
                ate = self._take_bite(j,i,corpse)
                if i not in self.carcasses:
                    break
                if ate:
                    contacts[i,j] = now
        self.carrion_contacts = {pair:t for pair,t in contacts.items() if pair[0] in self.carcasses}

    def _take_bite(self, eater_id, corpse_id, corpse):
        p = self.p
        eater,body = self.bodies[eater_id],self.bodies[corpse_id]
        reserve,material,core = body.storage,self.body_material[corpse_id],corpse["core_remaining"]
        available = reserve+material+core
        if available <= 0:
            return False
        barrier = p.shell_barrier_energy*body.shell*(body.radius/p.radius_m)**2
        if eater.storage < barrier:
            return False
        room = p.storage_capacity-(eater.storage-barrier)
        gross = min(available,p.nutrient_energy,max(0.0,room)/p.predation_efficiency)
        if gross <= 0:
            return False
        fraction = gross/available
        taken = (reserve*fraction,material*fraction,core*fraction)
        received = gross*p.predation_efficiency
        eater.storage += received-barrier
        body.storage = reserve-taken[0]
        self.body_material[corpse_id] = material-taken[1]
        corpse["core_remaining"] = core-taken[2]
        self.dead_core_debits[corpse_id] += taken[2]
        self.carrion_received[eater_id] = self.carrion_received.get(eater_id,0.0)+received
        self.totals["carrion_heat"] += gross-received
        self.totals["carrion_shell_heat"] += barrier
        self.totals["carrion_meals"] += 1
        self.events.append(dict(kind="carrion_meal",time_us=self.time_us,individual=eater_id,carcass=corpse_id,
            body_reserve=taken[0],body_material=taken[1],dead_core=taken[2],gross=gross,received=received,
            shell_cost=barrier,net_after_shell=received-barrier))
        if gross == available:
            del self.carcasses[corpse_id]
            self.events.append(dict(kind="carcass_consumed",time_us=self.time_us,individual=corpse_id))
        return True

    def capture(self):
        return dict(schema=SCHEMA,material=super().capture(),carcasses=copy.deepcopy(self.carcasses),
                    dead_core_debits=dict(self.dead_core_debits),carrion_received=dict(self.carrion_received),
                    contacts=[[i,j,t] for (i,j),t in sorted(self.carrion_contacts.items())])

    def metrics(self):
        m = super().metrics()
        # A dead Core is an immutable scientific record. Only its yet-unspent balance is
        # still physically available. Debit recovery from the world once, never rewrite the Core.
        m["energy_balance_error"] += (math.fsum(self.dead_core_debits.values())-
                                      self.totals["carrion_heat"]-self.totals["carrion_shell_heat"])
        for row in m["members"]:
            i=row["id"]
            row["carcass_present"]=i in self.carcasses
            row["carcass_core_remaining"]=self.carcasses.get(i,{}).get("core_remaining",0.0)
            row["carrion_received"]=self.carrion_received.get(i,0.0)
        return m


def new_habitat(block, candidate):
    p = read(E38_INPUT)
    p.update(schema="threemind.ocean-enclosure/2",body_material_fraction=.5,
             seed=p["seed"]+100*block,environment_seed=p["environment_seed"]+block)
    world = Carrion63(p)
    if candidate:
        seed_from_adult(world,candidate)
    world.configure({i:"candidate" if candidate and i<11 else "other" for i in world.bodies},
                    {"candidate":"core","other":"core"} if candidate else {"other":"core"})
    return world
