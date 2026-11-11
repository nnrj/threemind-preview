import {t} from "./i18n";
import { api, ApiError } from "./api";

export type MediaUpload = {
  id: string;
  byte_length: string;
  received_bytes: string;
  next_chunk: number;
  chunk_bytes: number;
  status: string;
  stage: string;
  progress_bytes: string;
  progress_frames: string;
  metadata: {
    kind: string;
    filename: string;
    intensity: number;
    delay_us: number;
  };
  expires_at: string;
  error?: string | null;
  receipt?: any;
};
export type TransferProgress = { stage: string; bytes: number; total: number };

async function retry<T>(
  operation: () => Promise<T>,
  signal: AbortSignal,
): Promise<T> {
  for (let attempt = 0; ; attempt++) {
    signal.throwIfAborted();
    try {
      return await operation();
    } catch (error) {
      if (
        signal.aborted ||
        attempt >= 2 ||
        (error instanceof ApiError &&
          ![408, 429, 502, 503, 504].includes(error.status))
      )
        throw error;
      await new Promise((resolve) => setTimeout(resolve, 300 * 2 ** attempt));
    }
  }
}

export async function transferMedia(
  base: string,
  file: File,
  metadata: MediaUpload["metadata"],
  id: string,
  report: (value: TransferProgress) => void,
  signal: AbortSignal,
) {
  const uploads = `${base}/media-uploads`;
  const session = await retry(
    () =>
      api<MediaUpload>(uploads, {
        method: "POST",
        signal,
        body: JSON.stringify({
          request_id: id,
          byte_length: file.size,
          ...metadata,
        }),
      }),
    signal,
  );
  const url = `${uploads}/${id}`;
  report({
    stage: "uploading",
    bytes: Number(session.received_bytes),
    total: file.size,
  });
  if (session.status === "accepted") return session.receipt;
  if (["cancel_requested", "cancelled", "expired"].includes(session.status))
    throw new Error(t("这次上传已取消或过期，请新建上传。"));
  if (session.status !== "processing") {
    const hashes = new Map<number, { sha256: string; byte_length: number }>();
    let after = -1;
    while (hashes.size < session.next_chunk) {
      const page = await retry(
        () => api<any>(`${url}/chunks?after=${after}&limit=256`, { signal }),
        signal,
      );
      for (const row of page.rows) hashes.set(row.chunk_index, row);
      if (page.next == null) break;
      after = page.next;
    }
    const chunk = session.chunk_bytes;
    for (
      let offset = 0, index = 0;
      offset < file.size;
      offset += chunk, index++
    ) {
      signal.throwIfAborted();
      const part = file.slice(offset, Math.min(offset + chunk, file.size));
      const sha = Array.from(
        new Uint8Array(
          await crypto.subtle.digest("SHA-256", await part.arrayBuffer()),
        ),
        (byte) => byte.toString(16).padStart(2, "0"),
      ).join("");
      if (index < session.next_chunk) {
        const old = hashes.get(index);
        if (!old || old.sha256 !== sha || old.byte_length !== part.size)
          throw new Error(
            t("第 {value0} 块与原上传不一致。请重新选择原文件，或退出续传并新建上传。", {value0: String(index + 1)}),
          );
      } else {
        await retry(
          () =>
            api(`${url}/chunks/${index}?sha256=${sha}`, {
              method: "PUT",
              body: part,
              signal,
              headers: { "Content-Type": "application/octet-stream" },
            }),
          signal,
        );
      }
      report({
        stage: index < session.next_chunk ? "verifying" : "uploading",
        bytes: offset + part.size,
        total: file.size,
      });
    }
  }
  report({ stage: "processing", bytes: file.size, total: file.size });
  try {
    return await api(`${url}/finalize`, { method: "POST", signal });
  } catch (error) {
    if (signal.aborted) throw error;
    const current = await api<MediaUpload>(url).catch(() => null);
    if (current?.status === "accepted") return current.receipt;
    if (current?.status === "processing")
      throw new Error(
        t("服务器仍在校验或解码，原件已保留。可在下方查看进度；服务重启后可重试解码。"),
      );
    throw error;
  }
}
