"""Inline organ switches, applied and acknowledged at a runtime commit boundary."""

from copy import deepcopy
from typing import Literal
from uuid import UUID

from fastapi import Request

from .database import Conflict, NotFound
from .protocols import RunSpec, StrictModel


class OrganSwitch(StrictModel):
    control: Literal["ear", "eye", "mouth", "image", "media-audio", "media-image", "media-video"]
    enabled: bool


def switch_spec(spec, control, enabled):
    from threemind_runtime.source_policies import SOURCES

    value = RunSpec(**spec).model_dump()
    if control in ("mouth", "image"):
        value["acoustic_output" if control == "mouth" else "activation_projector"]["enabled"] = enabled
    elif control in ("ear", "eye"):
        key = "microphone" if control == "ear" else "camera"
        value["live_capture"][f"{key}_enabled"] = enabled
        if enabled:
            value["auditory_sensor" if control == "ear" else "visual_sensor"]["enabled"] = True
            enable_source(value, key, "background", SOURCES)
    elif control.startswith("media-"):
        kind = control.split("-", 1)[1]
        if not enabled:
            raise ValueError("媒体入口只开启所需感官，不关闭其他器官")
        value["auditory_sensor" if kind == "audio" else "visual_sensor"]["enabled"] = True
        enable_source(value, kind, "manual", SOURCES)
    else:
        raise ValueError("unknown organ switch")
    return RunSpec(**value).model_dump()


def enable_source(value, key, category, sources):
    p = value["source_policies"]
    # Opening one device must not incidentally start every source behind a
    # previously closed category gate. Preserve each sibling's effective state.
    if not p[f"{category}_enabled"]:
        for name, _, group, _ in sources:
            if group == category:
                p[f"{name}_enabled"] = False
        p[f"{category}_enabled"] = True
    p[f"{key}_enabled"] = True


def validate_change(change):
    value = deepcopy(change["before"])
    for operation in change["operations"]:
        request = OrganSwitch.model_validate({k: operation[k] for k in ("control", "enabled")}, strict=True)
        value = switch_spec(value, request.control, request.enabled)
    if value != change["after"]:
        raise ValueError("live controls cannot change unrelated parameters")


def register_organ_controls(app, access, edit_configuration):
    base = "/api/v2/projects/{project}/runs/{run_id}/organ-controls"

    @app.post(base)
    def switch(project: UUID, run_id: UUID, request: Request, body: OrganSwitch):
        actor = access(request, project, write=True)
        row = app.state.db.get_run(project, run_id)
        if row["life"] == "dead" or row["spec"].get("study_id"):
            raise Conflict("死亡意识或冻结实验不能修改器官；请新建意识进行对照。")
        if row["status"] in ("paused", "blocked"):
            from .api import EditConfiguration

            spec = switch_spec(row["spec"], body.control, body.enabled)
            updated = edit_configuration(
                project,
                run_id,
                EditConfiguration(
                    name=row["name"],
                    spec=spec,
                    expected_revision=row["revision"],
                    expected_metadata_revision=row["metadata_revision"],
                ),
                request,
            )
            return {"status": "applied", "time_us": str(updated["time_us"]), "spec": updated["spec"]}
        command = app.state.db.command(
            project, run_id, "organ_switch", body.model_dump() | {"actor_id": str(actor["id"])}
        )
        return {"status": "pending", "command_id": str(command["id"])}

    @app.get(base + "/{command_id}")
    def receipt(project: UUID, run_id: UUID, command_id: int, request: Request):
        access(request, project)
        row = app.state.db.get_run(project, run_id)
        with app.state.db.tx(project) as db:
            cmd = db.execute(
                "SELECT payload FROM commands WHERE id=%s AND run_id=%s AND kind='organ_switch'", (command_id, run_id)
            ).fetchone()
            if cmd is None:
                raise NotFound()
            event = db.execute(
                "SELECT time_us,payload FROM events WHERE run_id=%s AND event_key=%s", (run_id, f"command:{command_id}")
            ).fetchone()
        return {
            "status": "applied" if event else "pending",
            "time_us": str(event["time_us"]) if event else None,
            "spec": row["spec"],
            "run_status": row["status"],
        }
