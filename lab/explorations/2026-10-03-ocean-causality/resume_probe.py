"""Explicit continuation after one zero-reserve birth died in a probe."""
import json
import time
from experiment import WORK
from lab.tools.ocean_cli import write_json,read_json
from probe import run
from analyze_probes import analyze
from birth_probe import execute

folder=WORK/'probes/g0-core-600'
failure=folder/'failure.json'
if not failure.exists():
    worker=read_json(folder/'worker.json')
    write_json(failure,{'reason':'original birth died; replay attempted later input and correctly received Core rejection',
        'scope':'probe only; source world and awake intervention data unchanged',
        'wall_seconds_upper_bound':time.time()-worker['started_epoch']})
run('g0-core',600,suffix='-retry1')
analyze(WORK/'probes/g0-core-600-retry1')
execute(0,600,probe_suffix='-retry1')
write_json(WORK/'followups-0.json',{'status':'complete','probe_correction':'g0-core-600-retry1; failed original retained'})
