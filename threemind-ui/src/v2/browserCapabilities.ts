export type Capability = {
  name: string;
  state: string;
  reason: string;
  [key: string]: unknown;
};
export type CapabilityReport = {
  scope: string;
  checked_at: string;
  features: Record<string, Capability>;
  [key: string]: unknown;
};

export async function inspectBrowser(): Promise<CapabilityReport> {
  const features: Record<string, Capability> = {};
  let devices: MediaDeviceInfo[] = [];
  let enumerationError = "";
  if (navigator.mediaDevices?.enumerateDevices) {
    try {
      devices = await navigator.mediaDevices.enumerateDevices();
    } catch (error) {
      enumerationError = (error as Error).message;
    }
  }
  for (const [id, name, kind] of [
    ["microphone", "麦克风", "audioinput"],
    ["camera", "摄像头", "videoinput"],
  ]) {
    let state = "unknown",
      reason = "浏览器未提供可查询的权限状态；可在连续设备页明确开始采集。";
    const count = devices.filter((d) => d.kind === kind).length;
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      state = "unavailable";
      reason = "当前页面没有可用的安全媒体采集 API，需要 HTTPS 或本机地址。";
    } else {
      try {
        const permission = await navigator.permissions.query({
          name: id as PermissionName,
        });
        state =
          permission.state === "granted"
            ? "available"
            : permission.state === "denied"
              ? "denied"
              : "permission_required";
        reason =
          permission.state === "granted"
            ? "已有设备权限；是否可以启动还取决于感官配置和当前设备状态。"
            : permission.state === "denied"
              ? "浏览器已拒绝权限，请在站点权限中调整。"
              : "尚未授权。请在连续设备页点击开始，由浏览器询问权限。";
        if (state === "available" && !count) {
          state = enumerationError ? "unknown" : "unavailable";
          reason = enumerationError || "已有权限，但当前未发现此类设备。";
        }
      } catch {
        /* Some browsers cannot query these permissions; do not request them as a probe. */
      }
    }
    features[`browser.${id}`] = {
      name,
      state,
      reason,
      visible_device_count: count,
    };
  }
  features["browser.audio_output"] = {
    name: "声音播放",
    state: typeof AudioContext === "function" ? "available" : "unavailable",
    reason: "只检查 Web Audio 支持。实际播放仍须在器官输出页主动开启。",
  };
  const canvas = document.createElement("canvas");
  const gl = canvas.getContext("webgl2");
  features["browser.webgl2"] = {
    name: "网络图形渲染",
    state: gl ? "available" : "unavailable",
    reason: gl
      ? "已建立并释放 WebGL2 上下文；这不代表独显型号或帧率保证。"
      : "无法建立 WebGL2 上下文，请检查浏览器图形设置。",
  };
  gl?.getExtension("WEBGL_lose_context")?.loseContext();
  return { scope: "browser", checked_at: new Date().toISOString(), features };
}
