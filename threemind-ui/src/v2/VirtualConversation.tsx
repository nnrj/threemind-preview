import {
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { t } from "./i18n";

// Variable-height window over a bounded page cache. Evicted pages remain queryable
// through server cursors; the viewport never defines the evidence retained.
export default function VirtualConversation({
  rows,
  follow,
  onScroll,
  children,
}: {
  rows: { id: string }[];
  follow: boolean;
  onScroll: (position: { top: number; remaining: number }) => void;
  children: (row: any) => ReactNode;
}) {
  const root = useRef<HTMLDivElement>(null);
  const heights = useRef(new Map<string, number>());
  const previous = useRef<{ id: string; top: number; height: number }[]>([]);
  const automatic = useRef(false);
  const [revision, setRevision] = useState(0);
  const [view, setView] = useState({ top: 0, height: 500 });
  const positions = useMemo(() => {
    let top = 0;
    return rows.map((row) => {
      const height = heights.current.get(row.id) ?? 115;
      const position = { id: row.id, top, height };
      top += height;
      return position;
    });
  }, [rows, revision]);
  const total = positions.length
    ? positions.at(-1)!.top + positions.at(-1)!.height
    : 0;
  const visible = positions.flatMap((p, i) =>
    p.top + p.height >= view.top - 400 && p.top <= view.top + view.height + 600
      ? [i]
      : [],
  );

  useLayoutEffect(() => {
    const el = root.current;
    if (!el) return;
    const oldAnchor = previous.current.find(
      (p) => p.top + p.height > el.scrollTop,
    );
    automatic.current = true;
    if (follow) el.scrollTop = Math.min(positions.at(-1)?.top ?? 0, Math.max(0, total - el.clientHeight));
    else if (oldAnchor) {
      const next = positions.find((p) => p.id === oldAnchor.id);
      if (next) el.scrollTop += next.top - oldAnchor.top;
    }
    previous.current = positions;
    setView({ top: el.scrollTop, height: el.clientHeight });
    const frame = requestAnimationFrame(() => {
      automatic.current = false;
    });
    // Bound measurement metadata to the current page cache too.
    const present = new Set(rows.map((r) => r.id));
    for (const key of heights.current.keys())
      if (!present.has(key)) heights.current.delete(key);
    return () => cancelAnimationFrame(frame);
  }, [positions, total, follow, rows]);

  useLayoutEffect(() => {
    const el = root.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      let changed = false;
      for (const entry of entries) {
        const id = (entry.target as HTMLElement).dataset.chatRow;
        if (!id) {
          setView((v) => ({ ...v, height: el.clientHeight }));
          continue;
        }
        const height = Math.ceil(entry.target.getBoundingClientRect().height);
        if (height > 0 && heights.current.get(id) !== height) {
          heights.current.set(id, height);
          changed = true;
        }
      }
      if (changed) setRevision((v) => v + 1);
    });
    observer.observe(el);
    el.querySelectorAll("[data-chat-row]").forEach((node) =>
      observer.observe(node),
    );
    return () => observer.disconnect();
  }, [visible.join(","), rows]);

  return (
    <div
      ref={root}
      className="conversation-messages"
      role="log"
      aria-label={t("刺激与意识读出历史")}
      aria-live="off"
      onScroll={() => {
        const el = root.current!;
        setView({ top: el.scrollTop, height: el.clientHeight });
        if (!automatic.current)
          onScroll({
            top: el.scrollTop,
            remaining: el.scrollHeight - el.scrollTop - el.clientHeight,
          });
      }}
    >
      <div className="conversation-spacer" style={{ height: total }}>
        {visible.map((index) => (
          <div
            key={rows[index].id}
            data-chat-row={rows[index].id}
            className="conversation-position"
            style={{ transform: `translateY(${positions[index].top}px)` }}
          >
            {children(rows[index])}
          </div>
        ))}
      </div>
    </div>
  );
}
