import csv
import io
import math

import pytest
from test_api import client_for

from threemind_core import Stimulus
from threemind_kernels.registry import resolve_kernel
from threemind_lab.configuration import default_spec
from threemind_runtime import create_engine


@pytest.mark.parametrize("kernel_id", ["threemind.continuous-memory/4", "threemind.continuous-memory/5"])
@pytest.mark.parametrize("backend", ["reference", "native"])
@pytest.mark.parametrize("energy_model", ["local-field", "global-ledger"])
def test_local_checkpoint_energy_and_spatial_observation_preserve_raw_state(database, kernel_id, backend, energy_model):
    LocalConfig = type(resolve_kernel(kernel_id).configuration())
    config = LocalConfig(
        energy_simulation_enabled=True,
        energy_model=energy_model,
        energy_initial_reserve=0.6,
        energy_direct_cost=0,
        energy_associative_cost=0,
        energy_inhibition_cost=0,
        energy_maintenance_cost_per_node=0,
        energy_maintenance_cost_per_edge=0,
        spatial_embedding=True,
        spatial_radius=4,
    )
    engine = create_engine(config, kernel_id=kernel_id, backend=backend)
    engine.inject(Stimulus(0, ((1, 0.8), (2, 0.6))))
    engine.advance_to(10000)
    image = engine.capture_state()
    state = image.to_dict()
    assert "state_time_us" not in state
    assert "parameters" not in state["energy"]
    assert "settled_state_time_us" not in state["energy"]
    reserve = (
        math.fsum([amount for _, amount in state["pools"]] + [node["reserve"] for node in state["nodes"]])
        if energy_model == "local-field"
        else state["energy"]["reserve"]
    )
    if energy_model == "local-field":
        assert state["energy"]["reserve"] == 0 and reserve > 0

    with client_for(database) as client:
        project = client.post("/api/v2/projects", json={"name": "Local observation compatibility"}).json()["id"]
        spec = default_spec(kernel_id=kernel_id) | {"environment": "manual", "config": config.to_dict()}
        created = client.post(
            f"/api/v2/projects/{project}/runs",
            json={
                "name": "Checkpoint boundary projection",
                "spec": spec,
                "execution": {"backend": backend},
                "start_immediately": False,
            },
        )
        assert created.status_code == 201, created.text
        run = created.json()["id"]
        base = f"/api/v2/projects/{project}/runs/{run}"
        database.save_checkpoint(
            project,
            run,
            image,
            expected_revision=0,
            status="paused",
            observations=[engine.metrics()],
            context={"protocol": spec},
        )
        energy_response = client.get(f"{base}/energy")
        assert energy_response.status_code == 200, energy_response.text
        evidence = energy_response.json()
        assert evidence["latest"]["reserve"] == pytest.approx(reserve)
        assert evidence["latest"]["parameters"]["energy_model"] == energy_model
        assert evidence["latest"]["settled_state_time_us"] == state["time_us"]
        assert evidence["rows"][0]["energy"]["reserve"] == pytest.approx(reserve)
        exported = client.get(f"{base}/energy/export?format=csv")
        assert exported.status_code == 200, exported.text
        csv_rows = list(csv.DictReader(io.StringIO(exported.content.decode("utf-8-sig"))))
        assert len(csv_rows) == 1 and float(csv_rows[0]["reserve"]) == pytest.approx(reserve)

        spatial_response = client.get(f"{base}/spatial")
        assert spatial_response.status_code == 200, spatial_response.text
        geometry = spatial_response.json()
        assert geometry["supported"]
        assert geometry["time_us"] == geometry["state_time_us"] == state["time_us"]
        assert len(geometry["nodes"]) == 2
        graph_response = client.get(f"{base}/spatial/graph")
        assert graph_response.status_code == 200, graph_response.text
        assert len(graph_response.json()["nodes"]) == 2
        current_page = client.get(f"{base}/data/nodes?limit=1").json()
        assert current_page["rows"][0]["id"] == 0 and current_page["more"]
        next_page = client.get(f"{base}/data/nodes?after={current_page['next']}&limit=1").json()
        assert next_page["rows"][0]["id"] == 1 and not next_page["more"]
        checkpoint = database.load_checkpoint(project, run)[0]
        historical = client.get(f"{base}/data/nodes?checkpoint_id={checkpoint['id']}&limit=1").json()
        assert historical["rows"][0]["id"] == 0
        assert client.get(f"{base}/data/edges").status_code == 200
        zero_source = client.post(f"{base}/data-exports", json={"table": "edges", "format": "csv", "source": "0"})
        assert zero_source.status_code == 202, zero_source.text
        assert database.load_checkpoint(project, run)[1].digest == image.digest
    assert engine.capture_state().digest == image.digest
