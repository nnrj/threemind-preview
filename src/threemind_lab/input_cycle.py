"""Single-runtime ownership of carrier scheduling and its commit buffers."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from uuid import UUID, uuid5

from threemind_core import Stimulus
from threemind_runtime.bus import InputBus
from threemind_runtime.sensory import TEXT_VERSION, carrier_frames

from .inputs import digest, envelope_record
from .protocols import filter_stimulus


class RuntimeInputs:
    def __init__(self, database, project, run_id, engine, spec, context, start, initial_image=None):
        self.database, self.project, self.run_id = database, project, run_id
        self.engine, self.spec, self.start = engine, spec, start
        state = context.get("input_bus") if context.get("input_bus_run_id") == str(run_id) else None
        self.bus = InputBus(engine, state, spec.input_bus, spec.source_policies)
        self.capture_streams = (
            deepcopy(context.get("capture_streams", {})) if context.get("input_bus_run_id") == str(run_id) else {}
        )
        self.device_streams = (
            deepcopy(context.get("device_streams", {})) if context.get("input_bus_run_id") == str(run_id) else {}
        )
        self.changes = self.empty_changes()
        if initial_image is not None:
            self.bus.verify(initial_image)
            unknown = [q for q in initial_image["queue"] if q["kind"] == "stimulus" and q["id"] not in self.bus.pending]
            if unknown:
                # A fork/import adopts its existing anonymous queue under a NEW
                # audit identity. It must never edit the source run's records.
                item = envelope_record(
                    self.identity("checkpoint-queue"),
                    "checkpoint-queue",
                    "checkpoint-queue",
                    {"frames": [q["payload"] for q in unknown]},
                    {
                        "origin_hash": context.get("origin_hash"),
                        "source_run": context.get("input_bus_run_id"),
                        "checkpoint_time_us": str(engine.time_us),
                    },
                    len(unknown),
                    sum(len(q["payload"]["channels"]) for q in unknown),
                )
                self.changes["envelopes"].append(item)
                for index, event in enumerate(unknown):
                    metadata = self.metadata(item, index, budgeted=False) | {
                        "core_event_id": event["id"],
                        "scheduled_time_us": event["time_us"],
                        "channel_count": len(event["payload"]["channels"]),
                    }
                    self.bus.pending[event["id"]] = metadata
                    self.changes["frames"].append(metadata | {"stimulus": event["payload"]})

    @staticmethod
    def empty_changes():
        return {
            "envelopes": [],
            "frames": [],
            "delivered": [],
            "rejected": [],
            "capture_updates": [],
            "device_updates": [],
        }

    def interrupt_capture(self, reason):
        self.changes["capture_end_reason"] = reason
        for value in self.capture_streams.values():
            value["closed"] = True
        for value in self.device_streams.values():
            value["closed"] = True

    def identity(self, name):
        return str(uuid5(UUID(str(self.run_id)), name))

    @staticmethod
    def metadata(item, index, *, budgeted):
        return {
            "envelope_id": str(item["id"]),
            "frame_index": index,
            "frame_count": item["frame_count"],
            "adapter_id": item["adapter_id"],
            "adapter_version": item["adapter_version"],
            "source": item["source"],
            "configuration_hash": item["configuration_hash"],
            "budgeted": budgeted,
        }

    def schedule(self, item, frames, *, source_enabled=True, budgeted=False):
        prepared = []
        policy = self.spec.source_policies.resolve(item["source"])
        for index, frame in enumerate(frames):
            stimulus = frame["stimulus"]
            effective = (
                filter_stimulus(self.spec, stimulus, self.start)
                if source_enabled and policy["enabled"] and not frame.get("filter_reason")
                else None
            )
            if effective is not None:
                effective = replace(effective, bypass_attention=policy["bypass_attention"])
            if effective is not None and stimulus.time_us < self.engine.time_us:
                raise ValueError("请求的递送时间已过去，不能倒填时间；载体未排入内核。")
            prepared.append((index, frame, effective))
        if budgeted:
            self.bus.reserve(
                sum(e is not None for _, _, e in prepared),
                sum(len(e.channels) for _, _, e in prepared if e is not None),
            )
        # All timestamps and resource requirements have been checked before the first injection.
        scheduled = [i for i, _, effective in prepared if effective is not None]
        for index, frame, effective in prepared:
            metadata = self.metadata(item, index, budgeted=budgeted) | {
                "first_scheduled_index": scheduled[0] if scheduled else None,
                "last_scheduled_index": scheduled[-1] if scheduled else None,
                "scheduled_frame_count": len(scheduled),
                "labels": frame.get("labels", {}),
                **({"stimulus_unit": frame["stimulus_unit"]} if "stimulus_unit" in frame else {}),
                "source_policy": policy,
                "policy_resolved_at_us": str(self.engine.time_us),
            }
            if effective is not None:
                metadata = self.bus.schedule(effective, metadata)
            else:
                metadata |= {
                    "status": "filtered",
                    "reason": "sources_closed"
                    if not source_enabled
                    else policy["reason"]
                    if not policy["enabled"]
                    else frame.get("filter_reason", "phase_input_disabled"),
                    "scheduled_time_us": str(frame["stimulus"].time_us),
                    "channel_count": len(frame["stimulus"].channels),
                }
            self.changes["frames"].append(
                metadata | {"stimulus": (effective or frame["stimulus"]).to_dict(), "labels": frame.get("labels", {})}
            )

    def automatic(
        self,
        key,
        adapter_id,
        stimulus,
        *,
        source_enabled=True,
        configuration=None,
        raw_stimulus=None,
        filter_reason=None,
        transduction=None,
    ):
        item = envelope_record(
            self.identity(key),
            adapter_id,
            adapter_id,
            {"frames": [(raw_stimulus or stimulus).to_dict()]}
            | ({"transduction": transduction} if transduction is not None else {}),
            configuration or {"seed": self.spec.seed},
            1,
            len(stimulus.channels),
            version=f"{adapter_id}/1",
        )
        self.changes["envelopes"].append(item)
        self.schedule(
            item,
            [{"stimulus": stimulus, **({"filter_reason": filter_reason} if filter_reason else {})}],
            source_enabled=source_enabled,
        )

    def replay(self, payloads):
        frames = [Stimulus.from_dict(p) for p in payloads]
        if not frames:
            return
        item = envelope_record(
            self.identity("initial-replay"),
            "replay",
            "replay",
            {"frames": payloads},
            {"seed": self.spec.seed, "origin_us": str(self.start)},
            len(frames),
            sum(len(s.channels) for s in frames),
        )
        self.changes["envelopes"].append(item)
        self.schedule(item, [{"stimulus": Stimulus(self.start + s.time_us, s.channels, s.intensity)} for s in frames])

    def accepted(self, envelope_id, *, source_enabled=True):
        with self.database.tx(self.project) as db:
            item = db.execute(
                "SELECT * FROM input_envelopes WHERE id=%s AND run_id=%s", (envelope_id, self.run_id)
            ).fetchone()
            capture = None
            if item and item["payload"].get("stream_session_id"):
                capture = db.execute(
                    "SELECT status,reason FROM capture_sessions WHERE id=%s AND run_id=%s",
                    (item["payload"]["stream_session_id"], self.run_id),
                ).fetchone()
            device = None
            if item and item["payload"].get("device_session_id"):
                from .devices import delivery_session

                device = delivery_session(db, self.run_id, item["payload"]["device_session_id"])
        if item is None:
            raise ValueError("accepted sensory carrier does not exist")
        try:
            if not source_enabled:
                raise ValueError("执行到该输入命令前，所有输入已关闭；载体未递送。")
            legacy_text = item["adapter_id"] == "text-sensor" and self.spec.kernel_id == "unified-associative"
            expected_text_version = "legacy-unified-text/97d8592" if legacy_text else TEXT_VERSION
            if item["adapter_id"] == "text-sensor" and item["adapter_version"] != expected_text_version:
                raise ValueError("载体编码器版本不匹配，不能静默更换感官编码。")
            stream_id = item["payload"].get("stream_session_id")
            if item["adapter_id"] == "remote-anonymous":
                if device is None or device["status"] != "active":
                    raise ValueError("设备会话已关闭或中断；未处理载体不能重新绑定时钟。")
                if device["clock_mode"] == "simulation":
                    origin = 0
                else:
                    device_id = item["payload"]["device_session_id"]
                    stream = self.device_streams.get(device_id)
                    if stream and stream.get("closed"):
                        raise ValueError("设备采集时钟已经中断。")
                    if stream is None:
                        if device["origin_sim_us"] is not None:
                            raise ValueError("设备时钟缺少匹配的运行时恢复状态；不能重新绑定。")
                        if int(item["payload"]["capture_us"]) != 0:
                            raise ValueError("设备首次输入必须从 capture_us=0 开始。")
                        stream = {"origin_us": str(self.engine.time_us + int(item["delay_us"])), "closed": False}
                        self.device_streams[device_id] = stream
                        self.changes["device_updates"].append({"id": device_id, "origin_us": stream["origin_us"]})
                    origin = int(stream["origin_us"])
            elif stream_id:
                if capture is None or capture["reason"] in (
                    "paused",
                    "completed",
                    "cancelled",
                    "dead",
                    "worker_failed",
                    "worker_replaced",
                ):
                    raise ValueError("连续会话所属的模型执行已结束；未处理采集块不能在恢复后重新绑定时钟。")
                stream = self.capture_streams.get(stream_id)
                if stream and stream.get("closed"):
                    raise ValueError("连续会话已经中断；该采集块未递送。")
                if stream is None:
                    stream = {
                        "origin_us": str(
                            max(0, self.engine.time_us + int(item["delay_us"]) - int(item["payload"]["capture_us"]))
                        ),
                        "closed": False,
                    }
                    self.capture_streams[stream_id] = stream
                    self.changes["capture_updates"].append({"id": stream_id, "origin_us": stream["origin_us"]})
                origin = int(stream["origin_us"])
            else:
                origin = (
                    int(item["requested_time_us"])
                    if item["requested_time_us"] is not None
                    else self.engine.time_us + int(item["delay_us"])
                )
            frames = []
            if item["adapter_id"] in ("auditory-sensor", "visual-sensor"):
                with self.database.tx(self.project) as db:
                    stored = db.execute(
                        "SELECT stimulus FROM media_prepared_frames WHERE run_id=%s AND envelope_id=%s ORDER BY frame_index",
                        (self.run_id, envelope_id),
                    ).fetchall()
                values = [f["stimulus"] for f in stored]
                if (
                    len(values) != item["frame_count"]
                    or digest(values) != item["configuration"]["prepared_frames_hash"]
                ):
                    raise ValueError("媒体转换帧校验失败；未排入内核。")
                decoded = ({"stimulus": Stimulus.from_dict(s)} for s in values)
            elif legacy_text:
                from .legacy_text import frames as legacy_frames

                decoded = legacy_frames(item["payload"], item["configuration"]["adapter"])
            else:
                decoded = carrier_frames(
                    item["adapter_id"], item["payload"], item["configuration"]["seed"], item["configuration"]["adapter"]
                )
            for frame in decoded:
                s = frame["stimulus"]
                frames.append({**frame, "stimulus": replace(s, time_us=origin + s.time_us)})
            self.schedule(item, frames, budgeted=True)
            if legacy_text:
                self.engine.register_channel_labels({int(channel): labels[0]
                                                     for frame in frames for channel, labels in frame.get("labels", {}).items()})
            if not frames:
                self.changes.setdefault("processed_empty", []).append(str(envelope_id))
            return {
                "envelope_id": str(envelope_id),
                "frames": len(frames),
                "scheduled_start_us": str(origin),
                "continuous_capture": bool(stream_id),
            }
        except ValueError as error:
            device_id = item["payload"].get("device_session_id")
            if device_id and device and device["clock_mode"] == "device":
                if device_id in self.device_streams:
                    self.device_streams[device_id]["closed"] = True
                self.changes["device_updates"].append({"id": device_id, "reason": str(error)})
            stream_id = item["payload"].get("stream_session_id")
            if stream_id:
                if stream_id in self.capture_streams:
                    self.capture_streams[stream_id]["closed"] = True
                self.changes["capture_updates"].append({"id": stream_id, "reason": str(error)})
            self.changes["rejected"].append({"envelope_id": str(envelope_id), "reason": str(error)})
            return {"envelope_id": str(envelope_id), "rejected": True, "reason": str(error)}

    def observe(self, event):
        delivery = self.bus.observe(event)
        if delivery and "delivery_stage" in event:
            delivery.update({key: event[key] for key in ("delivery_stage", "legacy_due_epoch", "legacy_envelope_id") if key in event})
        if delivery and delivery.get("envelope_id"):
            self.changes["delivered"].append(delivery)
        return delivery

    def take_changes(self):
        changes, self.changes = self.changes, self.empty_changes()
        return changes
