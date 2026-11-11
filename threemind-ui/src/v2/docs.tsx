import { t } from "./i18n";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import {
  BookOpen,
  Code2,
  Copy,
  Check,
  ArrowUpRight,
  Search,
} from "lucide-react";
import { api } from "./api";
import { DocumentMarkdown, documentHeadings } from "./DocumentMarkdown";
import { PageTitle, Button, ErrorBox, Loading } from "./ui";

export default function Documentation() {
  const [params] = useSearchParams(),
    doc = params.get("doc") ?? "";
  const [filter, setFilter] = useState(""),
    [source, setSource] = useState(false),
    [copied, setCopied] = useState(false);
  const index = useQuery({
    queryKey: ["documents"],
    queryFn: () => api("/documents"),
    staleTime: 60000,
  });
  const content = useQuery({
    queryKey: ["document", doc],
    queryFn: () => api(`/documents/content?path=${encodeURIComponent(doc)}`),
    enabled: !!doc,
    staleTime: 60000,
  });
  const toc = useMemo(
    () => documentHeadings(content.data?.markdown ?? ""),
    [content.data?.markdown],
  );
  const documents = index.data?.documents ?? [];
  return (
    <>
      <PageTitle
        eyebrow="DOCUMENTATION"
        title={t("项目文档")}
        description={t(
          "从研究假设、内核公式，到实验设计和部署操作。文档直接来自项目 Markdown。",
        )}
      />
      <div className="docs-layout">
        <aside className="docs-nav">
          <div className="docs-search">
            <Search size={15} />
            <input
              placeholder={t("搜索文档标题…")}
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            />
          </div>
          <Link className={!doc ? "active" : ""} to="/docs">
            <BookOpen size={15} />
            {t("文档索引")}
          </Link>
          {index.data?.categories
            .filter((c: any) => c.id !== "index")
            .map((category: any) => (
              <div key={category.id}>
                <h4>{t(category.title)}</h4>
                {documents
                  .filter(
                    (d: any) =>
                      d.category === category.id &&
                      d.title.toLowerCase().includes(filter.toLowerCase()),
                  )
                  .map((d: any) => (
                    <Link
                      key={d.id}
                      className={doc === d.id ? "active" : ""}
                      to={`/docs?doc=${encodeURIComponent(d.id)}`}
                    >
                      {d.title}
                    </Link>
                  ))}
              </div>
            ))}
        </aside>
        <div className="doc-body">
          {!doc ? (
            <article className="markdown doc-index">
              <span className="eyebrow">THREEMIND KNOWLEDGE BASE</span>
              <h1>{t("理解模型，也理解证据。")}</h1>
              <p>
                {t(
                  "ThreeMind 探索持续运行、环境耦合和局部可塑性。这里记录它的假设、实际实现及验证边界。",
                )}
              </p>
              <div className="doc-featured">
                {[
                  [
                    "docs/zh/v2-operations.md",
                    "开始使用",
                    "启动工作站，创建运行与第一个实验。",
                  ],
                  [
                    "docs/zh/v2-kernel.md",
                    "内核架构与公式",
                    "时间、局部动力学、可塑性和恢复语义。",
                  ],
                  [
                    "docs/zh/second-generation-architecture-assessment.md",
                    "架构评估与决策",
                    "理解 Runtime、Lab、数据库与部署的边界。",
                  ],
                ].map(([id, title, text]) => (
                  <Link to={`/docs?doc=${encodeURIComponent(id)}`} key={id}>
                    <h3>
                      {t(title)}
                      <ArrowUpRight size={17} />
                    </h3>
                    <p>{t(text)}</p>
                  </Link>
                ))}
              </div>
              {index.data?.categories
                .filter((c: any) => c.id !== "index")
                .map((c: any) => (
                  <section key={c.id}>
                    <h2>{t(c.title)}</h2>
                    {documents
                      .filter(
                        (d: any) =>
                          d.category === c.id && d.title.includes(filter),
                      )
                      .map((d: any) => (
                        <Link
                          className="doc-index-link"
                          key={d.id}
                          to={`/docs?doc=${encodeURIComponent(d.id)}`}
                        >
                          {d.title}
                          <ArrowUpRight size={14} />
                        </Link>
                      ))}
                  </section>
                ))}
            </article>
          ) : (
            <>
              <div className="reader-toolbar">
                <code>{doc}</code>
                <div>
                  <Button variant="small" onClick={() => setSource((v) => !v)}>
                    <Code2 size={14} />
                    {source ? t("阅读视图") : t("Markdown 源码")}
                  </Button>
                  <Button
                    variant="small"
                    onClick={async () => {
                      await navigator.clipboard.writeText(
                        content.data?.markdown ?? "",
                      );
                      setCopied(true);
                      setTimeout(() => setCopied(false), 2000);
                    }}
                  >
                    {copied ? <Check size={14} /> : <Copy size={14} />}
                    {t("复制")}
                  </Button>
                </div>
              </div>
              <ErrorBox error={content.error} />
              {content.isPending ? (
                <Loading />
              ) : (
                content.data && (
                  <>
                    {content.data.legacy && (
                      <div className="notice">
                        {t(
                          "这是历史设计参考。当前第二代行为以「第二代使用与架构」文档为准。",
                        )}
                      </div>
                    )}
                    {source ? (
                      <pre className="markdown-source">
                        {content.data.markdown}
                      </pre>
                    ) : (
                      <article className="markdown">
                        <DocumentMarkdown
                          markdown={content.data.markdown}
                          doc={doc}
                        />
                      </article>
                    )}
                  </>
                )
              )}
            </>
          )}
        </div>
        {doc && (
          <aside className="doc-toc">
            <h4>{t("本页目录")}</h4>
            {toc.map((item: any) => (
              <a
                key={item.id}
                href={`#${item.id}`}
                style={{ paddingLeft: (item.level - 1) * 10 }}
              >
                {item.text}
              </a>
            ))}
          </aside>
        )}
      </div>
    </>
  );
}
