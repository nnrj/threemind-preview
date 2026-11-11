import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useProjectSearchParams as useSearchParams } from "../projectRouting";
import { api } from "../api";
import { t } from "../i18n";
import { ErrorBox, Loading, PageTitle, useWorkspace } from "../ui";
import { parseLanguageReplay, type LanguageReplayData } from "./languageReplay";
import LanguageReplayPlayer from "./LanguageReplayPlayer";

const MAX_BYTES = 32 * 1024 * 1024;
type Artifact = {
  id: string;
  name: string;
  bytes: number;
  media_type: string;
  metadata?: Record<string, unknown>;
};
export default function LanguageReplayPage() {
  const { project } = useWorkspace();
  const [search] = useSearchParams();
  const [selected, setSelected] = useState(search.get("artifact") ?? "");
  const [loaded, setLoaded] = useState<{
    id: string;
    data: LanguageReplayData;
  } | null>(null);
  const [localFile, setLocalFile] = useState<File | null>(null);
  const [error, setError] = useState<unknown>(null),
    [busy, setBusy] = useState(false);
  const request = useRef(0);
  const catalogue = useQuery({
    queryKey: ["language-replays", project?.id],
    enabled: !!project,
    queryFn: () => api<Artifact[]>(`/projects/${project!.id}/artifacts`),
  });
  const replays = (catalogue.data ?? []).filter(
    (a) => a.metadata?.schema === "threemind.language-replay/1",
  );
  const videos = (catalogue.data ?? []).filter(
    (a) =>
      a.media_type === "video/mp4" &&
      a.metadata?.replay_artifact_id === loaded?.id,
  );
  useEffect(() => {
    request.current++;
    setLoaded(null);
    setLocalFile(null);
    setSelected(search.get("artifact") ?? "");
    setError(null);
    setBusy(false);
  }, [project?.id, search]);
  useEffect(() => {
    if (!selected && replays.length) setSelected(replays[0].id);
  }, [selected, replays[0]?.id]);
  useEffect(() => {
    if (!selected || (selected === "local" ? !localFile : !project)) return;
    const seq = ++request.current,
      controller = new AbortController();
    setBusy(true);
    setLoaded(null);
    setError(null);
    (async () => {
      if (selected === "local") {
        const data = parseLanguageReplay(JSON.parse(await localFile!.text()));
        if (seq === request.current) setLoaded({ id: "local", data });
        return;
      }
      const response = await fetch(
        `/api/v2/projects/${project!.id}/artifacts/${encodeURIComponent(selected)}`,
        { signal: controller.signal, credentials: "same-origin" },
      );
      if (!response.ok)
        throw new Error(`${t("读取回放失败")} (${response.status})`);
      if (Number(response.headers.get("Content-Length")) > MAX_BYTES)
        throw new Error(t("回放文件不能超过32 MiB"));
      const reader = response.body?.getReader();
      if (!reader) throw new Error(t("读取回放失败"));
      const chunks: Uint8Array<ArrayBuffer>[] = [];
      let size = 0;
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        size += value.byteLength;
        if (size > MAX_BYTES) {
          await reader.cancel();
          throw new Error(t("回放文件不能超过32 MiB"));
        }
        chunks.push(new Uint8Array(value));
      }
      const data = parseLanguageReplay(
        JSON.parse(await new Blob(chunks).text()),
      );
      if (seq === request.current) setLoaded({ id: selected, data });
    })()
      .catch((e) => {
        if (seq === request.current && !controller.signal.aborted) setError(e);
      })
      .finally(() => {
        if (seq === request.current) setBusy(false);
      });
    return () => {
      controller.abort();
      request.current++;
    };
  }, [project?.id, selected, localFile]);
  function importFile(file?: File) {
    if (!file) return;
    if (file.size > MAX_BYTES) {
      setError(new Error(t("回放文件不能超过32 MiB")));
      return;
    }
    setSelected("local");
    setLocalFile(file);
  }
  return (
    <>
      <PageTitle
        eyebrow="TEACHING REPLAY"
        title={t("教学回放与视频")}
        description={t(
          "把教学、意识活动、实际回答与对照放在同一时间轴中。回放只读取记录，不推进意识。",
        )}
        actions={
          <Link
            className="button"
            to={project ? `/dialogue?project=${project.id}` : "/dialogue"}
          >
            {t("返回对话实验")}
          </Link>
        }
      />
      <div className="replay-library">
        <label>
          {t("已保存的回放")}
          <select
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
          >
            <option value="">{t("选择回放")}</option>
            {selected === "local" && (
              <option value="local">{t("本地文件")}</option>
            )}
            {replays.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>
        </label>
        <label className="button replay-import">
          {t("打开回放文件")}
          <input
            type="file"
            accept=".json,application/json"
            aria-label={t("打开回放文件")}
            onChange={(e) => void importFile(e.target.files?.[0])}
          />
        </label>
        {videos.map((v) => (
          <a
            className="button"
            key={v.id}
            href={`/api/v2/projects/${project!.id}/artifacts/${v.id}`}
            download
          >
            {t("下载完整MP4")}
          </a>
        ))}
      </div>
      <ErrorBox error={error || catalogue.error} />
      {busy && <Loading />}
      {loaded && !busy && (
        <LanguageReplayPlayer
          key={`${project?.id}:${loaded.id}`}
          data={loaded.data}
        />
      )}
      {!loaded && !busy && (
        <p>
          {t(
            "选择项目中保存的回放，或打开导出的 JSON 文件。没有后端连接也可查看本地回放。",
          )}
        </p>
      )}
    </>
  );
}
