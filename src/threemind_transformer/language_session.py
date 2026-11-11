"""Database-free language adapter. Core receives ordinary stimuli through the existing input bus."""

import hashlib
import time

from threemind_kernels.registry import DEFAULT_KERNEL, state_kernel
from threemind_runtime.host import create_engine
from threemind_runtime.profile import profile_from_spec
from threemind_runtime.readout_session import ReadoutSession
from threemind_runtime.sensory import TextSensor, TextSensorConfig

from .language_compute import compute
from .language_protocol import LanguageCompute, LanguageProtocol
from .language_senses import advance_language, embedding_frame
from .supervisor import ComputeExecutionError


class LanguageSession:
    def __init__(
        self,
        protocol,
        *,
        image=None,
        context=None,
        kernel_id=None,
        config=None,
        seed=20260724,
        backend="native",
        text_sensor=None,
        readouts=None,
    ):
        self.protocol = LanguageProtocol.model_validate(protocol)
        if context:
            if (
                context.get("schema") != "threemind.language-runtime/1"
                or context["protocol"] != self.protocol.model_dump()
            ):
                raise ValueError("language continuation requires the same frozen adapter protocol")
            seed, text_sensor, readouts = context["seed"], context["text_sensor"], context["readout_config"]
        self.kernel_id = kernel_id or (state_kernel(image).kernel_id if image is not None else DEFAULT_KERNEL)
        if context and context.get("kernel_id") != self.kernel_id:
            raise ValueError("language recovery Core identity mismatch")
        self.engine = create_engine(
            config if image is None else None, state=image, backend=backend, kernel_id=self.kernel_id
        )
        self.seed, self.sensor_config = seed, text_sensor or {}
        self.profile = profile_from_spec({"seed": seed, "text_sensor": self.sensor_config})
        self.sensor = TextSensor(self.profile["sensory_seed"], TextSensorConfig(**self.sensor_config))
        self.readout_config = readouts or {"activity_readout": {"enabled": True, "analysis_version": 2}}
        self.records = []
        self.reader = ReadoutSession(
            self.engine, record=self.records.append, config=self.readout_config, state=(context or {}).get("readouts")
        )

    def turn(self, text, *, intensity=1.0, policy=None, head=None, input_checkpoint=None, output_checkpoint=None):
        if not isinstance(text, str) or not text.strip() or len(text) > 2048:
            raise ValueError("language turn requires 1..2048 characters")
        policy = policy or LanguageCompute()
        protocol = self.protocol
        before = self.engine.capture_state().digest
        if self.engine.life == "dead":
            raise ValueError("consciousness is dead; create or restore another instance")
        encoded = None
        if protocol.input_model == "text":
            frames = list(self.sensor.frames(text, intensity))
        else:
            encoded, _ = compute(
                "encode", {"texts": [text], "protocol": protocol.model_dump()}, policy, checkpoint=input_checkpoint
            )
            frames = [{"stimulus": embedding_frame(encoded["vectors"][0], protocol, intensity), "labels": {}}]
        return self._complete(frames, text, intensity, encoded, before, policy, head, output_checkpoint)

    def observe(self, *, policy=None, head=None, output_checkpoint=None):
        """Advance one normal window with no new stimulus and no artificial prompt.

        Queued events are still delivered normally. The decoder never receives a
        preceding utterance, and generated words are not fed back into Core.
        """
        if self.engine.life == "dead":
            raise ValueError("consciousness is dead; no automatic revival")
        pending = self.reader.bus.pending_count()
        result = self._complete(
            [],
            None,
            0.0,
            None,
            self.engine.capture_state().digest,
            policy or LanguageCompute(),
            head,
            output_checkpoint,
        )
        result.update(
            schema="threemind.language-observation/1",
            new_input=False,
            pending_external_before=pending,
            pending_external_after=self.reader.bus.pending_count(),
        )
        return result

    def stream(self, windows=20, **kwargs):
        """Bounded, window-by-window no-input observation for external callers."""
        if type(windows) is not int or not 1 <= windows <= 256:
            raise ValueError("observation requires 1..256 windows")
        for index in range(windows):
            if self.engine.life == "dead":
                break
            result = self.observe(**kwargs)
            result["window_index"] = index
            yield result

    def _complete(self, frames, text, intensity, encoded, before, policy, head, output_checkpoint):
        protocol = self.protocol
        self.records.clear()
        import psutil

        started = time.monotonic()
        owner = psutil.Process()

        def guard():
            if time.monotonic() - started > policy.wall_seconds:
                raise ValueError("language Core advance exceeded wall budget")
            if owner.memory_info().rss > policy.memory_mib * 2**20 or psutil.virtual_memory().available < 2 * 2**30:
                raise ValueError("language Core advance reached memory budget")

        process = advance_language(self.engine, frames, protocol, self.reader, guard)
        if protocol.output_model == "raw" or protocol.mode == "core":
            decoded = {"text": None, "reason": "raw_readout", "external_contribution": False}
        else:
            # A new isolated process receives only declared features and, in assisted mode, the user text.
            decoder_protocol = protocol.model_copy(update={"mode": "strict"}) if text is None else protocol
            payload = {"protocol": decoder_protocol.model_dump(), "features": process["features"]}
            if protocol.mode == "assisted" and text is not None:
                payload["assistance"] = text
            try:
                decoded, _ = compute("decode", payload, policy, head=head, checkpoint=output_checkpoint)
            except ComputeExecutionError as error:
                decoded = {
                    "text": None,
                    "reason": str(error),
                    "status": "decoder_failed",
                    "external_contribution": False,
                    "evidence": error.report,
                }
        return {
            "schema": "threemind.language-turn/1",
            "text": text,
            "intensity": intensity,
            "protocol": protocol.model_dump(),
            "input_hash": hashlib.sha256(text.encode()).hexdigest() if text is not None else None,
            "encoding": encoded,
            "stimuli": [frame["stimulus"].to_dict() for frame in frames],
            "before_hash": before,
            "after_hash": self.engine.capture_state().digest,
            "process": process,
            "readouts": list(self.records),
            "interpretation": decoded,
            "metrics": self.engine.metrics(),
            "decoder_head_sha256": hashlib.sha256(head).hexdigest() if head else None,
            "wall_seconds": time.monotonic() - started,
        }

    def context(self):
        return {
            "schema": "threemind.language-runtime/1",
            "protocol": self.protocol.model_dump(),
            "kernel_id": self.kernel_id,
            "seed": self.seed,
            "text_sensor": self.sensor_config,
            "readout_config": self.readout_config,
            "readouts": self.reader.capture(),
        }
