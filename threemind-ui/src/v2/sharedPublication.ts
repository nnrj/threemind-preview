import { t } from "./i18n";

export async function verifiedHtml(
  url: string,
  expected: string,
  signal: AbortSignal,
  credentials: RequestCredentials = "omit",
) {
  const response = await fetch(url, {
    signal,
    credentials,
    referrerPolicy: "no-referrer",
  });
  if (!response.ok)
    throw new Error(t("分享内容无法读取，链接可能已过期或被撤销。"));
  if (Number(response.headers.get("Content-Length")) > 32 * 1024 ** 2)
    throw new Error(t("分享正文超过 32 MiB 预览上限。"));
  const raw = await response.arrayBuffer();
  if (raw.byteLength > 32 * 1024 ** 2)
    throw new Error(t("分享正文超过 32 MiB 预览上限。"));
  const hash = [...new Uint8Array(await crypto.subtle.digest("SHA-256", raw))]
    .map((v) => v.toString(16).padStart(2, "0"))
    .join("");
  if (hash !== expected)
    throw new Error(t("正文校验失败，未显示可能损坏的内容。"));
  return new TextDecoder("utf-8", { fatal: true }).decode(raw);
}
