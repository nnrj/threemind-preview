import { useEffect, useMemo, useState } from "react";
import {
  useInfiniteQuery,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Settings2 } from "lucide-react";
import { api, type Run } from "./api";
import { t } from "./i18n";
import { InputComposer } from "./inputs";
import { Button, Empty, ErrorBox, Loading } from "./ui";
import { usePreferences, updatePreferences } from "./preferences";
import ConversationPreferences from "./conversationPreferences";
import ChatOrgans from "./chatOrgans";
import ChatMessage, { type ChatEntry } from "./ChatMessage";
import VirtualConversation from "./VirtualConversation";
import { classes } from "./readouts";
import "./chatRestoration.css";

type Page = {
  rows: ChatEntry[];
  more: boolean;
  next: string | null;
  ceiling: string;
  direction: string;
};
type Cursor = { before?: string; after?: string };
const compare = (a: ChatEntry, b: ChatEntry) =>
  BigInt(a.id) < BigInt(b.id) ? -1 : BigInt(a.id) > BigInt(b.id) ? 1 : 0;

export default function Conversation({
  base,
  run,
  compact = false,
}: {
  base: string;
  run: Run;
  compact?: boolean;
}) {
  const p = usePreferences(),
    client = useQueryClient();
  const [follow, setFollow] = useState(true),
    [options, setOptions] = useState(false);
  const [intensity, setIntensity] = useState(1);
  const filters = new URLSearchParams({
    environment: String(p.showEnvironmentStimuli),
    triggering: String(p.showTriggeringStimuli),
    background: "true",
    passive: String(p.showChatPassive),
  }).toString();
  const key = ["conversation", run.id, "continuous", filters];
  const running = ["running", "queued"].includes(run.status);
  const newest = useQuery({
    queryKey: ["conversation-head", run.id, filters],
    queryFn: () => api<Page>(`${base}/conversation?${filters}&limit=1`),
    gcTime: 0,
    refetchInterval: 1500,
  });
  const feed = useInfiniteQuery({
    queryKey: key,
    initialPageParam: {} as Cursor,
    maxPages: 8,
    gcTime: 0,
    queryFn: async ({ pageParam, signal }) => {
      const query = new URLSearchParams(filters);
      query.set("limit", "40");
      if (pageParam.before) query.set("before", pageParam.before);
      if (pageParam.after) query.set("after", pageParam.after);
      const result = await api<Page>(`${base}/conversation?${query}`, {
        signal,
      });
      return { ...result, rows: result.rows.sort(compare) };
    },
    getPreviousPageParam: (first): Cursor | undefined =>
      first.rows.length && (first.direction === "newer" || first.more)
        ? { before: first.rows[0].id }
        : undefined,
    getNextPageParam: (_last, pages): Cursor | undefined => {
      const lastId = pages.flatMap((page) => page.rows).at(-1)?.id ?? "0";
      return newest.data?.rows.length &&
        BigInt(lastId) < BigInt(newest.data.rows[0].id)
        ? { after: lastId }
        : undefined;
    },
  });
  const rows = useMemo(() => {
    const unique = new Map<string, ChatEntry>();
    for (const page of feed.data?.pages ?? [])
      for (const row of page.rows) unique.set(row.id, row);
    return [...unique.values()].sort(compare);
  }, [feed.data]);
  const pending = rows
    .filter(
      (row) =>
        row.kind === "input" &&
        !["completed", "rejected"].includes(row.stimulus?.status),
    )
    .map((row) => row.id);
  const inputStatus = useQuery({
    queryKey: ["chat-input-status", run.id, pending.join(",")],
    gcTime: 0,
    enabled: pending.length > 0,
    queryFn: () =>
      api(
        `${base}/conversation/statuses?${pending.map((id) => `entry=${id}`).join("&")}`,
      ),
    refetchInterval: running ? 500 : false,
  });
  useEffect(() => {
    if (!inputStatus.data?.rows.length) return;
    const updates = new Map<string, any>(
      inputStatus.data.rows.map((row: any) => [row.id, row]),
    );
    client.setQueryData(
      key,
      (data: any) =>
        data && {
          ...data,
          pages: data.pages.map((page: Page) => ({
            ...page,
            rows: page.rows.map((row) =>
              updates.has(row.id)
                ? {
                    ...row,
                    stimulus: { ...row.stimulus, ...updates.get(row.id) },
                  }
                : row,
            ),
          })),
        },
    );
  }, [inputStatus.dataUpdatedAt]);
  useEffect(() => {
    if (follow && feed.hasNextPage && !feed.isFetching)
      void feed.fetchNextPage();
  }, [follow, feed.hasNextPage, feed.isFetching, newest.dataUpdatedAt]);
  useEffect(() => {
    void newest.refetch();
  }, [run.revision]);
  const temporal = useQuery({
    queryKey: ["chat-temporal-status", run.id],
    queryFn: () => api(`${base}/readouts?kind=temporal_readout&limit=1`),
    gcTime: 0,
    refetchInterval: running ? 2000 : false,
  });
  const latestTemporal = temporal.data?.rows?.[0],
    observing = temporal.data?.active?.length ?? 0;
  const latest = () => {
    setFollow(true);
    void client.resetQueries({ queryKey: key, exact: true });
    void newest.refetch();
  };
  return (
    <div
      className={`conversation-layout conversation-restored ${compact ? "conversation-inline" : ""}`}
    >
      <section className="conversation-panel">
        <div className="panel-heading">
          <h2>{t("意识读出")}</h2>
          <button
            type="button"
            className="text-link"
            aria-label={t("聊天显示设置")}
            onClick={() => setOptions((v) => !v)}
          >
            <Settings2 size={16} />
          </button>
        </div>
        <div className="chat-temporal-status" role="status">
          <Link to="?view=readouts">{t("时序读出")}</Link>
          <span>
            {!run.spec.temporal_readout?.enabled &&
            !run.spec.activity_readout?.enabled
              ? t("未启用")
              : observing
                ? `${t("正在观察")} · ${observing}`
                : latestTemporal
                  ? t(
                      classes[latestTemporal.payload.classification] ??
                        latestTemporal.payload.classification,
                    )
                  : t("等待刺激")}
          </span>
          {latestTemporal && (
            <Link
              className="text-link"
              to={`?view=readouts&record=${latestTemporal.id}`}
            >
              {t("最近结果")}
            </Link>
          )}
        </div>
        {options && (
          <div className="chat-options">
            <ConversationPreferences interaction chat />
            <label>
              <input
                type="checkbox"
                checked={p.showChatPassive}
                onChange={(e) =>
                  updatePreferences({ showChatPassive: e.target.checked })
                }
              />
              {t("显示被动读出")}
            </label>
            <label>
              <input
                type="checkbox"
                checked={p.chatActivationOrder}
                onChange={(e) =>
                  updatePreferences({ chatActivationOrder: e.target.checked })
                }
              />
              {t("明文标签按激活强度排序")}
            </label>
            <label>
              {t("时序正文项数（0 为全部）")}
              <input
                type="number"
                min={0}
                max={2000}
                value={p.temporalChatItems}
                onChange={(e) =>
                  updatePreferences({
                    temporalChatItems: Number(e.target.value),
                  })
                }
              />
            </label>
            <Link to="?view=inputs">{t("感官与输入")}</Link> ·{" "}
            <Link to="?view=readouts">{t("读出查询与导出")}</Link>
            <a
              className="text-link"
              href={`/api/v2${base}/conversation/export?${filters}&format=jsonl`}
            >
              {t("导出消息索引")}
            </a>
          </div>
        )}
        {feed.isLoading ? (
          <Loading />
        ) : rows.length === 0 ? (
          <Empty
            title={t("等待刺激")}
            detail={t("发送刺激后，输入与读出将在这里连续显示。")}
          />
        ) : (
          <VirtualConversation
            rows={rows}
            follow={follow}
            onScroll={({ top, remaining }) => {
              setFollow(remaining < 40);
              if (top < 80 && feed.hasPreviousPage && !feed.isFetching)
                void feed.fetchPreviousPage();
              else if (remaining < 80 && feed.hasNextPage && !feed.isFetching)
                void feed.fetchNextPage();
            }}
          >
            {(row) => <ChatMessage row={row} base={base} />}
          </VirtualConversation>
        )}
        <ErrorBox
          error={
            feed.error ?? newest.error ?? inputStatus.error ?? temporal.error
          }
        />
        <div className="chat-history-status">
          {feed.hasPreviousPage && (
            <button
              type="button"
              className="text-link"
              disabled={feed.isFetching}
              onClick={() => {
                setFollow(false);
                void feed.fetchPreviousPage();
              }}
            >
              {t("加载更早消息")}
            </button>
          )}
          {!follow && (
            <Button onClick={latest}>
              {feed.hasNextPage ? t("有新消息 · 回到最新") : t("回到底部")}
            </Button>
          )}
        </div>
      </section>
      <aside className="conversation-composer">
        <ChatOrgans key={run.id} base={base} run={run} intensity={intensity} />
        <InputComposer
          base={base}
          run={run}
          compact
          intensityValue={intensity}
          onIntensityChange={setIntensity}
        />
      </aside>
    </div>
  );
}
