import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useLocation, useSearchParams } from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  Code2,
  Download,
  Search,
} from "lucide-react";
import { api } from "./api";
import { Button, ErrorBox, Loading } from "./ui";
import { t, useLocale } from "./i18n";
import { DocumentMarkdown, documentHeadings } from "./DocumentMarkdown";

type Work = {
  id: string;
  title: string;
  subtitle: string;
  language: string;
  description: string;
};
type Chapter = {
  id: string;
  work: string;
  key: string;
  group: string;
  title: string;
  path: string;
  period: string;
  tags: string[];
};
type Catalog = {
  schema: string;
  compiled_on: string;
  source_count: number;
  works: Work[];
  chapters: Chapter[];
};
type Document = { title: string; markdown: string; id: string };
const groupNames: Record<string, string> = {
  guide: "开篇与导读",
  chronicles: "编年六卷",
  themes: "专题列传",
  decisions: "决策与考证",
  sources: "原始史料与全目",
  classical: "各卷目录",
};
function chapterUrl(chapter: Chapter) {
  return `/history?book=${encodeURIComponent(chapter.work)}&chapter=${encodeURIComponent(chapter.key)}`;
}

export default function History() {
  const [params, setParams] = useSearchParams();
  const language = useLocale(),
    location = useLocation();
  const [filter, setFilter] = useState("");
  const [showSource, setShowSource] = useState(false);
  const [compact, setCompact] = useState(
    () => window.matchMedia("(max-width: 760px)").matches,
  );
  const reader = useRef<HTMLElement>(null);
  const catalog = useQuery({
    queryKey: ["history"],
    queryFn: () => api<Catalog>("/history"),
    staleTime: 60000,
    retry: false,
  });
  const data = catalog.data;
  const bookId =
    params.get("book") ?? (language === "en" ? "modern-en" : "modern-zh");
  const work = data?.works.find((w) => w.id === bookId);
  const chapters = data?.chapters.filter((c) => c.work === bookId) ?? [];
  const requested = params.get("chapter");
  const current = requested
    ? chapters.find((c) => c.key === requested)
    : chapters[0];
  const sourceDoc = params.get("source");
  const doc = sourceDoc || current?.path || "";
  const content = useQuery({
    queryKey: ["document", doc],
    queryFn: () =>
      api<Document>(`/documents/content?path=${encodeURIComponent(doc)}`),
    enabled: !!doc && !!work && !!current,
    staleTime: 60000,
    retry: false,
  });
  const headings = useMemo(
    () => documentHeadings(content.data?.markdown ?? ""),
    [content.data?.markdown],
  );
  const q = filter.trim().toLocaleLowerCase();
  const visible = chapters.filter((c) =>
    `${c.title} ${c.period} ${c.tags.join(" ")}`
      .toLocaleLowerCase()
      .includes(q),
  );
  const index = chapters.findIndex((c) => c.id === current?.id);
  useEffect(() => {
    const query = window.matchMedia("(max-width: 760px)");
    const update = () => setCompact(query.matches);
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  useEffect(() => {
    setShowSource(false);
  }, [doc]);
  useEffect(() => {
    if (!content.data || location.hash) return;
    reader.current?.focus({ preventScroll: true });
    if (requested || sourceDoc)
      reader.current?.scrollIntoView({ block: "start" });
  }, [doc, content.data, location.hash, requested, sourceDoc]);
  function switchBook(id: string) {
    const peer = data?.chapters.find(
      (c) => c.work === id && c.key === current?.key,
    );
    const first = data?.chapters.find((c) => c.work === id);
    if (!first) return;
    setFilter("");
    setParams({ book: id, chapter: (peer ?? first).key });
  }
  function linkTo(path: string, hash: string) {
    const chapter = data?.chapters.find((c) => c.path === path);
    if (chapter) return chapterUrl(chapter) + hash;
    return `${current ? chapterUrl(current) : "/history"}&source=${encodeURIComponent(path)}${hash}`;
  }
  function download() {
    if (!content.data) return;
    const url = URL.createObjectURL(
      new Blob([content.data.markdown], {
        type: "text/markdown;charset=utf-8",
      }),
    );
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = doc.split("/").at(-1) || "threemind-history.md";
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  if (catalog.isPending) return <Loading />;
  if (catalog.error)
    return (
      <>
        <ErrorBox error={catalog.error} />
        <Button onClick={() => catalog.refetch()}>{t("重试")}</Button>
      </>
    );
  if (!work || !current)
    return (
      <div className="history-empty">
        <h1>{t("未找到这部史书或章节")}</h1>
        <Link to="/history">{t("返回史书目录")}</Link>
      </div>
    );

  return (
    <>
      <section className="history-intro">
        <div>
          <span className="eyebrow">THE THREEMIND CHRONICLES</span>
          <h1>{t("史书")}</h1>
          <p>{t("记下想法如何成为机制，实验如何改变判断。")}</p>
        </div>
        <div className="history-date">
          <span>{t("项目起点")} · 2026.07.23</span>
          <span>
            {t("本版编纂")} · {data?.compiled_on}
          </span>
        </div>
      </section>
      <div
        className="history-editions"
        role="group"
        aria-label={t("选择史书版本")}
      >
        {data?.works.map((w) => (
          <button
            key={w.id}
            type="button"
            aria-pressed={work.id === w.id}
            onClick={() => switchBook(w.id)}
          >
            <BookOpen size={18} />
            <span>
              <strong>{w.title}</strong>
              <small>{w.subtitle}</small>
            </span>
          </button>
        ))}
      </div>
      <label className="history-mobile-edition">
        {t("史书版本")}
        <select
          aria-label={t("史书版本")}
          value={work.id}
          onChange={(e) => switchBook(e.target.value)}
        >
          {data?.works.map((w) => (
            <option value={w.id} key={w.id}>
              {w.title} · {w.subtitle}
            </option>
          ))}
        </select>
      </label>
      <div className="history-layout">
        <aside className="history-navigation">
          <details className="history-book-toc" open={!compact}>
            <summary>{t("卷目与史料")}</summary>
            <div className="history-search">
              <Search size={16} />
              <input
                aria-label={t("搜索章节")}
                placeholder={t("搜索标题、时期或主题…")}
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
              />
            </div>
            <nav aria-label={t("史书章节")}>
              {Object.entries(groupNames).map(([group, label]) => {
                const items = visible.filter((c) => c.group === group);
                if (!items.length) return null;
                return (
                  <details
                    className="history-nav-group"
                    key={group}
                    open={
                      !!q || group !== "sources" || current.group === "sources"
                    }
                  >
                    <summary>
                      {t(label)} <small>{items.length}</small>
                    </summary>
                    {items.map((c) => (
                      <Link
                        key={c.id}
                        to={chapterUrl(c)}
                        aria-current={
                          c.id === current.id && !sourceDoc ? "page" : undefined
                        }
                        onClick={() => {
                          if (window.matchMedia("(max-width: 760px)").matches) {
                            const toc =
                              document.querySelector<HTMLDetailsElement>(
                                ".history-book-toc",
                              );
                            if (toc) toc.open = false;
                          }
                        }}
                      >
                        {c.title}
                      </Link>
                    ))}
                  </details>
                );
              })}
              {!visible.length && (
                <p className="history-muted">{t("没有匹配的章节")}</p>
              )}
            </nav>
          </details>
          <p className="history-nav-note">
            {t("正文直接来自项目 Markdown；原始报告保持原位。")}
          </p>
        </aside>
        <section
          ref={reader}
          tabIndex={-1}
          className="history-reader"
          aria-label={t("史书正文")}
        >
          <div className="history-reader-meta">
            <span>{sourceDoc ? t("原始文献") : current.period}</span>
            <div>
              <Button
                variant="small"
                onClick={() => setShowSource((v) => !v)}
                disabled={!content.data}
              >
                <Code2 size={14} />
                {showSource ? t("阅读视图") : t("Markdown 源码")}
              </Button>
              <Button
                variant="small"
                onClick={download}
                disabled={!content.data}
              >
                <Download size={14} />
                {t("下载本章")}
              </Button>
            </div>
          </div>
          {sourceDoc && (
            <Link className="history-back" to={chapterUrl(current)}>
              <ArrowLeft size={15} />
              {t("返回引用章节")}
            </Link>
          )}
          <ErrorBox error={content.error} />
          {content.isPending ? (
            <Loading />
          ) : (
            content.data && (
              <>
                <details className="history-page-toc">
                  <summary>{t("本页目录")}</summary>
                  {headings.map((h) => (
                    <a
                      href={`#${h.id}`}
                      key={h.id}
                      style={{ paddingInlineStart: (h.level - 1) * 12 }}
                    >
                      {h.text}
                    </a>
                  ))}
                </details>
                {showSource ? (
                  <pre className="markdown-source">{content.data.markdown}</pre>
                ) : (
                  <article
                    className="markdown history-prose"
                    lang={
                      sourceDoc?.includes("/en/") ||
                      sourceDoc?.endsWith(".en.md")
                        ? "en"
                        : work.language
                    }
                  >
                    <DocumentMarkdown
                      markdown={content.data.markdown}
                      doc={doc}
                      linkTo={linkTo}
                    />
                  </article>
                )}
                <p className="history-source-path">{doc}</p>
              </>
            )
          )}
          {!sourceDoc && (
            <nav className="history-pagination" aria-label={t("章节翻阅")}>
              {index > 0 ? (
                <Link to={chapterUrl(chapters[index - 1])}>
                  <ArrowLeft size={16} />
                  <span>
                    <small>{t("上一章")}</small>
                    {chapters[index - 1].title}
                  </span>
                </Link>
              ) : (
                <span />
              )}
              {index + 1 < chapters.length ? (
                <Link to={chapterUrl(chapters[index + 1])}>
                  <span>
                    <small>{t("下一章")}</small>
                    {chapters[index + 1].title}
                  </span>
                  <ArrowRight size={16} />
                </Link>
              ) : (
                <span />
              )}
            </nav>
          )}
        </section>
      </div>
    </>
  );
}
