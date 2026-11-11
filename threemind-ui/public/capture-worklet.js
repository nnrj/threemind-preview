/* Capture actual render quanta; never assume a fixed 128-frame block. */
class ThreeMindCapture extends AudioWorkletProcessor {
  constructor(options) {
    super();
    this.size = options.processorOptions.samplesPerPacket;
    this.buffer = new Float32Array(this.size);
    this.used = 0;
    this.firstFrame = 0;
    this.nextFrame = null;
    this.active = true;
    this.port.onmessage = (event) => {
      if (event.data === "stop" && this.active) {
        this.flush(true);
        this.active = false;
        this.port.postMessage({ type: "stopped" });
      }
    };
  }
  flush(final) {
    const samples = this.buffer.slice(0, this.used);
    this.port.postMessage(
      {
        type: "audio",
        samples,
        firstFrame: this.used
          ? this.firstFrame
          : (this.nextFrame ?? currentFrame),
        final,
      },
      [samples.buffer],
    );
    this.used = 0;
  }
  process(inputs) {
    if (!this.active) return false;
    const samples = inputs[0]?.[0];
    if (!samples?.length) {
      if (this.nextFrame !== null) {
        this.active = false;
        this.port.postMessage({
          type: "gap",
          reason: "音频输入中断，未以零填充。",
        });
      }
      return this.active;
    }
    if (this.nextFrame !== null && this.nextFrame !== currentFrame) {
      this.active = false;
      this.port.postMessage({
        type: "gap",
        reason: `音频渲染时钟出现缺口：期望源帧 ${this.nextFrame}，实际 ${currentFrame}，当前块 ${samples.length} 帧。`,
      });
      return false;
    }
    for (let i = 0; i < samples.length; i++) {
      if (!Number.isFinite(samples[i])) {
        this.active = false;
        this.port.postMessage({
          type: "gap",
          reason: "采集到非有限幅度，当前会话中断。",
        });
        return false;
      }
      if (!this.used) this.firstFrame = currentFrame + i;
      this.buffer[this.used++] = samples[i];
      if (this.used === this.size) this.flush(false);
    }
    this.nextFrame = currentFrame + samples.length;
    return true;
  }
}
registerProcessor("threemind-capture-v2", ThreeMindCapture);
