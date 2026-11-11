import { useEffect, useId, useMemo, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import DOMPurify from "dompurify";
import "katex/dist/katex.min.css";

export function documentHeadings(markdown: string) {
  const counts = new Map<string, number>();
  let fence = "";
  return markdown.split("\n").flatMap((line, i) => {
    const boundary = /^\s*(`{3,}|~{3,})/.exec(line);
    if (boundary) {
      if (!fence) fence = boundary[1];
      else if (
        boundary[1][0] === fence[0] &&
        boundary[1].length >= fence.length
      )
        fence = "";
      return [];
    }
    if (fence) return [];
    const match = /^(#{1,3})\s+(.+)/.exec(line);
    if (!match) return [];
    const base = match[2]
      .toLowerCase()
      .replace(/[`*]/g, "")
      .replace(/[^\p{L}\p{N}\s-]/gu, "")
      .trim()
      .replace(/\s/g, "-");
    const n = counts.get(base) ?? 0;
    counts.set(base, n + 1);
    return [
      {
        text: match[2],
        level: match[1].length,
        line: i + 1,
        id: base + (n ? `-${n}` : ""),
      },
    ];
  });
}

function Mermaid({ source }: { source: string }) {
  const id = useId().replace(/[^a-zA-Z0-9]/g, "");
  const [svg, setSvg] = useState(""),
    [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    setSvg("");
    setError("");
    import("mermaid")
      .then(async ({ default: mermaid }) => {
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: "strict",
          htmlLabels: false,
          flowchart: { htmlLabels: false },
          theme: "neutral",
        });
        const result = await mermaid.render(`tmDiagram${id}`, source);
        if (live)
          setSvg(
            DOMPurify.sanitize(result.svg, {
              USE_PROFILES: { svg: true, svgFilters: true },
            }),
          );
      })
      .catch((e) => {
        if (live) setError(String(e));
      });
    return () => {
      live = false;
    };
  }, [source, id]);
  return error ? (
    <pre>{source}</pre>
  ) : (
    <div className="mermaid" dangerouslySetInnerHTML={{ __html: svg }} />
  );
}

export function DocumentMarkdown({
  markdown,
  doc,
  linkTo,
}: {
  markdown: string;
  doc: string;
  linkTo?: (path: string, hash: string) => string;
}) {
  const headings = useMemo(() => documentHeadings(markdown), [markdown]);
  const location = useLocation();
  useEffect(() => {
    if (!location.hash) return;
    let id: string;
    try {
      id = decodeURIComponent(location.hash.slice(1));
    } catch {
      return;
    }
    const frame = requestAnimationFrame(() =>
      document.getElementById(id)?.scrollIntoView(),
    );
    return () => cancelAnimationFrame(frame);
  }, [doc, markdown, location.hash]);
  function heading(level: number, props: any) {
    const Tag = `h${level}` as "h1";
    const item = headings.find(
      (h) => h.line === props.node?.position?.start?.line,
    );
    return <Tag id={item?.id}>{props.children}</Tag>;
  }
  function resolved(href: string) {
    const url = new URL(href, `https://docs.local/${doc}`);
    return { path: decodeURIComponent(url.pathname.slice(1)), hash: url.hash };
  }
  function docLink(href: string) {
    if (href.startsWith("#")) return href;
    const { path, hash } = resolved(href);
    return linkTo
      ? linkTo(path, hash)
      : `/docs?doc=${encodeURIComponent(path)}${hash}`;
  }
  function resourceLink(href: string) {
    return `/api/v2/documents/resource?path=${encodeURIComponent(resolved(href).path)}`;
  }
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm, remarkMath]}
      rehypePlugins={[rehypeKatex]}
      components={{
        h1: (p) => heading(1, p),
        h2: (p) => heading(2, p),
        h3: (p) => heading(3, p),
        a: ({ href = "", children }) =>
          /^(https?:|mailto:)/i.test(href) ? (
            <a href={href} target="_blank" rel="noreferrer">
              {children}
            </a>
          ) : /^[a-z][a-z0-9+.-]*:/i.test(href) ? (
            <span>{children}</span>
          ) : /\.(json|csv|png|jpe?g|webp|pdf)(?:[?#]|$)/i.test(href) ? (
            <a href={resourceLink(href)}>{children}</a>
          ) : (
            <Link to={docLink(href)}>{children}</Link>
          ),
        img: ({ src = "", alt = "" }) => (
          <img
            src={/^https?:/i.test(src) ? src : resourceLink(src)}
            alt={alt}
            loading="lazy"
          />
        ),
        code: ({ className, children }) =>
          className === "language-mermaid" ? (
            <Mermaid source={String(children)} />
          ) : (
            <code className={className}>{children}</code>
          ),
      }}
    >
      {markdown}
    </ReactMarkdown>
  );
}
