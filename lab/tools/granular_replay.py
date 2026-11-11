"""Replay recorded physics or re-execute recorded inputs in a separate Core.

The observer camera is separate from the recorded sensory camera. Full raw
measurements and physical continuation are verified; original evidence is read-only.
"""

import argparse
import gzip
import json
import time
from pathlib import Path

import av
import mujoco as mj
import numpy as np
from PIL import Image, ImageDraw

from .granular_physics import TransferWorld
from .service_study import new_json, read_json


def replay_core(folder, output, *, wall_seconds=900):
    """Re-execute the recorded stimuli, without resampling a physical camera."""
    from threemind_core import Stimulus
    from threemind_runtime import create_engine
    from threemind_runtime.codec import ArtifactCodec

    initial = ArtifactCodec.decode((folder / "initial.tmind").read_bytes())
    expected = ArtifactCodec.decode((folder / "final.tmind").read_bytes())
    engine = create_engine(state=initial, backend="native")
    output.mkdir(parents=True, exist_ok=False)
    began, rows = time.monotonic(), 0
    try:
        with gzip.open(folder / "events.jsonl.gz", "rt", encoding="utf-8") as stream:
            for line in stream:
                if time.monotonic() - began > wall_seconds:
                    raise RuntimeError("Core evidence replay exceeded its wall budget")
                row = json.loads(line)
                if [list(item) for item in engine.activations()] != row["activations_before"]:
                    raise ValueError("recorded pre-action activity did not reproduce")
                if row["food"]:
                    food = row["food"]
                    event = engine.supply_energy(food["amount"], time_us=food["time_us"], source=food["source"])
                    if str(event) != str(food["event_id"]):
                        raise ValueError("recorded food event identity did not reproduce")
                event = engine.inject(Stimulus.from_dict(row["stimulus"]))
                if str(event) != str(row["core_event_id"]):
                    raise ValueError("recorded stimulus event identity did not reproduce")
                engine.advance_to(row["time_us"])
                rows += 1
        actual = engine.capture_state()
        if actual.digest != expected.digest:
            raise ValueError("full final Core state did not reproduce")
    except Exception as exc:
        new_json(output / "failure.json", {"verified": False, "rows_checked": rows, "error": str(exc)})
        raise
    result = {
        "schema": "threemind.granular-core-replay/1",
        "rows": rows,
        "all_recorded_pre_action_activity_matches": True,
        "final_state_matches": True,
        "initial_hash": initial.digest,
        "final_hash": actual.digest,
        "input_source": "recorded stimuli and food; no physical rerendering",
        "wall_seconds": time.monotonic() - began,
    }
    new_json(output / "verification.json", result)
    return result


def replay(folder, output, video_seconds=30, *, allow_pixel_variation=False):
    if not 0 < video_seconds <= 120:
        raise ValueError("video is limited to120 simulated seconds")
    wrapper = read_json(folder / "protocol.json")
    protocol = wrapper.get("protocol", wrapper)
    context = read_json(folder / "context.json")
    origin = folder / "origin.json"
    if origin.exists() and read_json(origin) and read_json(origin)["mode"] == "continuation":
        raise ValueError("this renderer starts from birth; continuation replay needs its initial physical checkpoint")
    output.mkdir(parents=True, exist_ok=False)
    began = time.monotonic()
    frames = []
    movie = output / "behavior.mp4"
    with TransferWorld(protocol["world"]) as w, av.open(str(movie), "w") as writer:
        if context["world"]["xml_hash"] != w.xml_hash or context["world"]["mujoco"] != mj.__version__:
            raise ValueError("recorded physics identity differs")
        stream = writer.add_stream("libx264", rate=10, options={"crf": "24", "preset": "fast", "threads": "1"})
        stream.width, stream.height, stream.pix_fmt = 640, 480, "yuv420p"
        renderer = mj.Renderer(w.model, height=480, width=640)
        observer_data = mj.MjData(w.model)
        cam = mj.MjvCamera()
        cam.lookat[:] = [0.32, 0.0, 0.27]
        cam.distance = 1.4
        cam.azimuth = 135
        cam.elevation = -25
        times = [0, 1000000, 5000000, 30000000, 120000000, context["world"]["time_us"]]
        next_frame = 0
        rows = 0
        pixel_variation = {"frames": 0, "pixels": 0, "maximum_absolute_difference": 0, "examples": []}

        def render():
            # Visualisation may update derived MuJoCo fields. Use an independent
            # data copy: even a display-only pass must not touch replay physics.
            mj.mj_copyData(observer_data, w.model, w.data)
            renderer.update_scene(observer_data, camera=cam)
            return renderer.render().copy()

        frames.append((0, render()))
        times.pop(0)
        try:
            with gzip.open(folder / "events.jsonl.gz", "rt", encoding="utf-8") as inputs:
                for line in inputs:
                    row = json.loads(line)
                    w.step(row["action"])
                    if w.time_us != row["time_us"]:
                        raise ValueError("nonconsecutive replay clock")
                    channels, raw = w.senses(row["physical"]["physical"][-1])
                    if raw != row["physical"]:
                        fields = [key for key in raw if raw[key] != row["physical"][key]]
                        if not allow_pixel_variation or fields != ["luminance"]:
                            new_json(
                                output / "mismatch.json",
                                {"time_us": w.time_us, "actual": raw, "expected": row["physical"]},
                            )
                            raise ValueError("raw physical/sensory measurements did not reproduce")
                        delta = np.abs(np.array(raw["luminance"]) - np.array(row["physical"]["luminance"]))
                        pixel_variation["frames"] += 1
                        pixel_variation["pixels"] += int(np.count_nonzero(delta))
                        pixel_variation["maximum_absolute_difference"] = max(
                            pixel_variation["maximum_absolute_difference"], int(delta.max())
                        )
                        if len(pixel_variation["examples"]) < 5:
                            pixel_variation["examples"].append(
                                {"time_us": w.time_us, "maximum_delta": int(delta.max())}
                            )
                    elif [list(channel) for channel in channels] != row["stimulus"]["channels"]:
                        raise ValueError("unchanged measurements produced different anonymous channels")
                    if w.events != row["world_events"]:
                        raise ValueError("physical task events did not reproduce")
                    w.events = []
                    rows += 1
                    if times and w.time_us >= times[0]:
                        frames.append((w.time_us, render()))
                        times.pop(0)
                    if w.time_us >= next_frame and w.time_us <= video_seconds * 1000000:
                        for packet in stream.encode(av.VideoFrame.from_ndarray(render(), format="rgb24")):
                            writer.mux(packet)
                        next_frame = w.time_us + 100000
            for packet in stream.encode():
                writer.mux(packet)
            current = w.capture()
            full_context_matches = current == context["world"]
            if {k: v for k, v in current.items() if k != "last_visual"} != {
                k: v for k, v in context["world"].items() if k != "last_visual"
            }:
                raise ValueError("full recorded physical endpoint did not reproduce")
        except Exception as exc:
            new_json(
                output / "failure.json",
                {
                    "verified": False,
                    "rows_checked": rows,
                    "error": str(exc),
                    "partial_video_is_not_verified_evidence": True,
                },
            )
            raise
        finally:
            renderer.close()
        canvas = Image.new("RGB", (960, 272 * ((len(frames) + 2) // 3)), (242, 246, 243))
        draw = ImageDraw.Draw(canvas)
        for i, (timestamp, pixels) in enumerate(frames):
            x, y = (i % 3) * 320, (i // 3) * 272
            canvas.paste(Image.fromarray(pixels).resize((320, 240)), (x, y))
            draw.text((x + 12, y + 248), f"{timestamp / 1e6:.2f} simulated seconds", fill=(25, 55, 45))
        canvas.save(output / "sequence.png")
    result = {
        "schema": "threemind.granular-action-replay/1",
        "source": str(folder),
        "rows": rows,
        "raw_measurements_match": pixel_variation["frames"] == 0,
        "physical_measurements_match": True,
        "rendered_pixel_variation": pixel_variation,
        "allow_pixel_variation": allow_pixel_variation,
        "final_full_context_match": full_context_matches,
        "physical_events_match": True,
        "final_physics_match": True,
        "core_reexecuted": False,
        "observer_camera": "overview only; sensory camera unchanged",
        "video_seconds": video_seconds,
        "wall_seconds": time.monotonic() - began,
    }
    new_json(output / "verification.json", result)
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("case", type=Path)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--video-seconds", type=float, default=30)
    p.add_argument(
        "--allow-pixel-variation",
        action="store_true",
        help="Keep exact physical checks; report rendering differences without claiming exact sensory replay",
    )
    p.add_argument(
        "--core-only", action="store_true", help="Reproduce exact Core state from recorded inputs, without physics"
    )
    args = p.parse_args()
    if args.core_only:
        print(json.dumps(replay_core(args.case, args.output)))
    else:
        print(
            json.dumps(
                replay(args.case, args.output, args.video_seconds, allow_pixel_variation=args.allow_pixel_variation)
            )
        )
