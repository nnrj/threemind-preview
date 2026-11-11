"""Recoverable passive output cadence, independent of metric or display sampling."""

from copy import deepcopy
from dataclasses import asdict

from .bus import OutputBus
from .media import AcousticConfig, ProjectorConfig, organ_output


class OutputOrgans:
    def __init__(self, acoustic: AcousticConfig, projector: ProjectorConfig, time_us=0, *, state=None):
        self.acoustic, self.projector = acoustic, projector
        self.output = OutputBus()
        self.config = {"acoustic_output": asdict(acoustic), "activation_projector": asdict(projector)}
        self.next_audio = time_us if acoustic.enabled else None
        self.next_image = time_us if projector.enabled else None
        self.last_audio = self.last_image = None
        if state and state.get("schema") != "threemind.output-cadence/1":
            raise ValueError("unsupported output cadence state")
        if state and state["configuration"] == self.config:
            for name in ("next_audio", "next_image", "last_audio", "last_image"):
                setattr(self, name, None if state[name] is None else int(state[name]))

    @property
    def next_us(self):
        times = [v for v in (self.next_audio, self.next_image) if v is not None]
        return min(times) if times else None

    def reconfigure(self, acoustic, projector, time_us):
        # Preserve the other organ's cadence when only one switch changes.
        if acoustic != self.acoustic:
            self.next_audio = time_us if acoustic.enabled else None
            self.last_audio = None
        if projector != self.projector:
            self.next_image = time_us if projector.enabled else None
            self.last_image = None
        self.acoustic, self.projector = acoustic, projector
        self.config = {"acoustic_output": asdict(acoustic), "activation_projector": asdict(projector)}

    def capture(self):
        return {
            "schema": "threemind.output-cadence/1",
            "configuration": deepcopy(self.config),
            **{
                key: None if getattr(self, key) is None else str(getattr(self, key))
                for key in ("next_audio", "next_image", "last_audio", "last_image")
            },
        }

    def observe(self, engine, *, final=False):
        now = engine.time_us
        audio = self.next_audio is not None and (now >= self.next_audio or final and self.last_audio != now)
        image = self.next_image is not None and (now >= self.next_image or final and self.last_image != now)
        if not (audio or image):
            return None
        if any(at is not None and now > at for at in (self.next_audio, self.next_image)):
            raise ValueError("output cadence was skipped; advance to next_us before observing")
        payload = organ_output(now, engine.activations(), self.acoustic, self.projector, audio=audio, image=image)
        payload["terminal"] = final
        self.output.publish(payload)
        if audio:
            self.next_audio, self.last_audio = now + self.acoustic.output_interval_us, now
        if image:
            self.next_image, self.last_image = now + self.projector.output_interval_us, now
        return payload
