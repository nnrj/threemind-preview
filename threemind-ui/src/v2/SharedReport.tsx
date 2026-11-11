import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useLocation } from "react-router-dom";
import { Download } from "lucide-react";
import { dateLabel, t, useLocale } from "./i18n";
import LanguagePicker from "./LanguagePicker";
import { ErrorBox, Loading } from "./ui";
import { usePreferences } from "./preferences";
import { verifiedHtml } from "./sharedPublication";

export default function SharedReport() {
  const language = useLocale(),
    preferences = usePreferences(),
    location = useLocation();
  const id = location.pathname.split("/")[2],
    path = `/api/v2/shared-documents/${encodeURIComponent(id ?? "")}`;
  const [preview, setPreview] = useState(""),
    [error, setError] = useState<unknown>();
  useEffect(() => {
    document.documentElement.lang = language;
    document.documentElement.dataset.theme = preferences.theme;
  }, [language, preferences.theme]);
  const publication = useQuery({
    queryKey: ["public-document", id],
    retry: false,
    queryFn: async () => {
      const response = await fetch(path, {
        credentials: "omit",
        referrerPolicy: "no-referrer",
      });
      if (!response.ok)
        throw new Error(t("分享内容无法读取，链接可能已过期或被撤销。"));
      return response.json();
    },
  });
  const hash = publication.data?.metadata.body.sha256;
  useEffect(() => {
    setPreview("");
    setError(undefined);
    if (!hash) return;
    const controller = new AbortController();
    void verifiedHtml(`${path}/files/body`, hash, controller.signal)
      .then((html) => {
        if (!controller.signal.aborted) setPreview(html);
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(e);
      });
    return () => controller.abort();
  }, [path, hash]);
  const row = publication.data;
  return (
    <main className="shared-report-page">
      <header>
        <a className="shared-brand" href="/">
          ThreeMind <span>RESEARCH LAB</span>
        </a>
        <LanguagePicker compact />
      </header>
      {publication.isPending ? (
        <Loading />
      ) : publication.error ? (
        <ErrorBox error={publication.error} />
      ) : (
        row && (
          <>
            <div className="shared-report-heading">
              <span className="eyebrow">{t("公开的固定版本")}</span>
              <h1>{row.metadata.title}</h1>
              <p>
                r{row.revision} ·{" "}
                {row.metadata.review === "reviewed"
                  ? t("作者已标记复核")
                  : t("待复核草案")}{" "}
                {row.metadata.ai_generated && `· ${t("含 AI 生成来源")}`}
              </p>
              <p className="hint">
                {t("发布于 {date}", { date: dateLabel(row.created_at) })} ·{" "}
                {row.expires_at
                  ? t("到期：{date}", { date: dateLabel(row.expires_at) })
                  : t("直至撤销")}
              </p>
              <p className="publication-hash">
                {t("文档校验值")} · <code>{row.metadata.document_hash}</code>
              </p>
              <div className="report-inline">
                <a href={`${path}/files/body`} rel="noreferrer" download>
                  <Download size={16} />
                  {t("下载 HTML 正文")}
                </a>
                {row.metadata.bundle && (
                  <a href={`${path}/files/bundle`} rel="noreferrer" download>
                    <Download size={16} />
                    {t("下载完整证据 ZIP")}
                  </a>
                )}
              </div>
              <p className="hint">
                {t(
                  "此页保留发布时的内容。作者的后续编辑不会改变该版本；作者说明、AI 推断与原始测量仍须分别评估。",
                )}
              </p>
            </div>
            <ErrorBox error={error} />
            {preview ? (
              <iframe
                className="publication-frame"
                title={t("分享正文")}
                sandbox=""
                referrerPolicy="no-referrer"
                srcDoc={preview}
              />
            ) : (
              !error && <Loading />
            )}
          </>
        )
      )}
    </main>
  );
}
