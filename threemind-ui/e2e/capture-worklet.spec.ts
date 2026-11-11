import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";

test("audio worklet preserves variable quanta, actual tails and explicit render gaps", () => {
  const messages: any[] = [];
  let Capture: any;
  const scope = {
    currentFrame: 1000,
    AudioWorkletProcessor: class {
      port = {
        postMessage: (v: any) => messages.push(v),
        onmessage: null as any,
      };
    },
    registerProcessor: (_name: string, value: any) => {
      Capture = value;
    },
  };
  runInNewContext(readFileSync("public/capture-worklet.js", "utf8"), scope);
  const capture = new Capture({ processorOptions: { samplesPerPacket: 200 } });
  expect(capture.process([[new Float32Array(137).fill(0.25)]])).toBe(true);
  scope.currentFrame = 1137;
  expect(capture.process([[new Float32Array(151).fill(1.25)]])).toBe(true);
  capture.port.onmessage({ data: "stop" });
  const audio = messages.filter((v) => v.type === "audio");
  expect(audio.map((v) => [v.firstFrame, v.samples.length, v.final])).toEqual([
    [1000, 200, false],
    [1200, 88, true],
  ]);
  expect(Array.from(audio[0].samples.slice(137))).toEqual(
    new Array(63).fill(1.25),
  );
  expect(capture.process([[new Float32Array(128)]])).toBe(false);
  messages.length = 0;
  const gap = new Capture({ processorOptions: { samplesPerPacket: 200 } });
  scope.currentFrame = 0;
  gap.process([[new Float32Array(128)]]);
  scope.currentFrame = 384;
  expect(gap.process([[new Float32Array(128)]])).toBe(false);
  expect(messages).toHaveLength(1);
  expect(messages[0].type).toBe("gap");
  expect(messages[0].reason).toContain("128");
  expect(messages[0].reason).toContain("384");
});
