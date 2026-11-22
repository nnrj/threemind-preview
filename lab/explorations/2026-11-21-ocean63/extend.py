"""Longer environmental selection on fresh carrion habitats after legacy replication."""
from apparatus import *
from registration import directory,exclusive_json
from execution import SECOND,run_case
from baseline import supply_fork
from carrion import new_habitat


def run_long():
    for code in ("30","28","38"):
        if not (directory(code)/"calculation-complete.json").exists():
            raise RuntimeError("legacy water worlds must be completed before the new habitat")
    work = directory("39C")
    source = directory("38")/"selected-parent.tmspecies"
    candidate = source if source.exists() else None
    exclusive_json(work/"founders.json",dict(candidate_sha256=sha(source) if candidate else None,
        selected_from="OCEAN63-38 parent-search",candidate_founders=11 if candidate else 0,
        independent_environment_seeds=[382101,382102]))
    for g in range(2):
        common = run_case("39C",f"world-{g}-common",lambda:new_habitat(g,candidate),300)
        if not common["alive"] or common["time_us"]!=300*SECOND:
            continue
        for mode,interval in (("original",SECOND),("reduced",2*SECOND)):
            run_case("39C",f"world-{g}-{mode}",lambda:supply_fork(work/common["end_snapshot"],interval),
                     2400,milestones=(600,900,1500))
