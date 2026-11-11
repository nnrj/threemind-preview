import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, post, timeLabel } from "./api";
import { t, useLocale, messageKeys } from "./i18n";
import ObserverSpeech from "./ObserverSpeech";
import EcologyAI from "./EcologyAI";
import {
  Button,
  CodeEditor,
  Empty,
  ErrorBox,
  Field,
  Loading,
  Modal,
} from "./ui";

const states = messageKeys({
  clear: "未命中",
  pending: "累计采样时长中",
  active: "条件成立",
  missing: "证据不足",
  triggered: "预警命中",
  reminder: "预警仍成立",
  cleared: "预警解除",
  coverage_gap: "采样覆盖中断",
  missing_evidence: "缺少有效证据",
  coverage_resumed: "恢复有效采样",
  event: "事件说明",
  summary: "状态小结",
  warning: "规则预警",
});

function ObserverEditor({ root, current, catalogue, close, saved }: any) {
  const language = useLocale() === "en" ? "en" : "zh";
  const [baseRevision] = useState(current?.revision ?? 0);
  const [value, setValue] = useState(() =>
    structuredClone(current?.configuration ?? catalogue.defaults),
  );
  const [mode, setMode] = useState("form"),
    [raw, setRaw] = useState("");
  const [error, setError] = useState<unknown>(null),
    [busy, setBusy] = useState(false),
    [valid, setValid] = useState(false);
  function change(next: any) {
    setValue(next);
    setValid(false);
    setError(null);
  }
  async function read() {
    if (mode === "form") return value;
    const { parseJson } = await import("./JsonEditor");
    return parseJson(raw);
  }
  async function checked() {
    const response = await post<any>(root + "/validate", await read());
    setValid(true);
    return response.configuration;
  }
  async function action(kind: string) {
    setBusy(true);
    setError(null);
    try {
      if (kind === "format") setRaw(JSON.stringify(await read(), null, 2));
      else if (kind === "toggle") {
        const config = await checked();
        setValue(config);
        setRaw(JSON.stringify(config, null, 2));
        setMode(mode === "form" ? "json" : "form");
      } else if (kind === "save") {
        const config = await checked();
        await post(root + "/configuration", {
          configuration: config,
          expected_revision: baseRevision,
        });
        saved();
      } else await checked();
    } catch (e) {
      setError(e);
      setValid(false);
    } finally {
      setBusy(false);
    }
  }
  function rule(index: number, key: string, next: any) {
    change({
      ...value,
      rules: value.rules.map((item: any, at: number) =>
        at === index ? { ...item, [key]: next } : item,
      ),
    });
  }
  return (
    <Modal
      open
      wide
      title={t("配置生态观察与预警")}
      onOpenChange={(open) => {
        if (!open && !busy) close();
      }}
    >
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void action("save");
        }}
      >
        <div className="observer-toolbar">
          <p className="footnote">
            {t("规则只读取已提交证据；保存为新版本，保留旧版本及其观察记录。")}
          </p>
          <button
            className="text-link"
            type="button"
            disabled={busy}
            onClick={() => void action("toggle")}
          >
            {mode === "form" ? t("切换到 JSON 编辑") : t("切换到图形配置")}
          </button>
        </div>
        {mode === "json" ? (
          <>
            <div className="query-controls">
              <Button
                type="button"
                disabled={busy}
                onClick={() => void action("format")}
              >
                {t("格式化")}
              </Button>
              <Button
                type="button"
                disabled={busy}
                onClick={() => void action("validate")}
              >
                {t("校验")}
              </Button>
            </div>
            <CodeEditor
              label={t("观察与预警 JSON")}
              readOnly={busy}
              value={raw}
              rows={22}
              onChange={(text) => {
                setRaw(text);
                setValid(false);
                setError(null);
              }}
            />
          </>
        ) : (
          <fieldset disabled={busy} className="observer-form">
            <div className="observer-switches">
              {[
                ["enabled", t("启用生态观察")],
                ["narration_enabled", t("生成事件说明和状态小结")],
                ["warnings_enabled", t("启用规则预警")],
              ].map(([key, label]) => (
                <label className="check" key={key}>
                  <input
                    type="checkbox"
                    checked={value[key]}
                    onChange={(e) =>
                      change({ ...value, [key]: e.target.checked })
                    }
                  />
                  {label}
                </label>
              ))}
            </div>
            <Field
              label={t("本版本从哪里开始观察")}
              hint={t("选择最近恢复点会略过更早历史；原始实验数据仍然保留。")}
            >
              <select
                aria-label={t("本版本从哪里开始观察")}
                aria-description={t(
                  "选择最近恢复点会略过更早历史；原始实验数据仍然保留。",
                )}
                value={value.start_from}
                onChange={(e) =>
                  change({ ...value, start_from: e.target.value })
                }
              >
                <option value="latest">{t("最近已提交恢复点及后续")}</option>
                <option value="beginning">
                  {t("从第一个恢复点回顾并继续")}
                </option>
              </select>
            </Field>
            <p className="footnote">
              {t(
                "持续时长只表示已采样点满足条件；超过最大采样间隔后重新累计，不推断中间状态。",
              )}
            </p>
            {value.rules.map((item: any, index: number) => (
              <fieldset className="observer-rule" key={index}>
                <legend>{t("预警规则 {number}", { number: index + 1 })}</legend>
                <div className="observer-fields">
                  <Field label={t("规则名称")}>
                    <input
                      maxLength={120}
                      value={item.label}
                      onChange={(e) => rule(index, "label", e.target.value)}
                    />
                  </Field>
                  <Field label={t("规则编号")}>
                    <input
                      required
                      pattern="[a-z][a-z0-9_-]{0,47}"
                      value={item.id}
                      onChange={(e) => rule(index, "id", e.target.value)}
                    />
                  </Field>
                  <Field label={t("观察指标")}>
                    <select
                      aria-label={t("观察指标")}
                      value={item.metric}
                      onChange={(e) => rule(index, "metric", e.target.value)}
                    >
                      {Object.entries(catalogue.metrics).map(
                        ([key, names]: any) => (
                          <option key={key} value={key}>
                            {names[language]}
                          </option>
                        ),
                      )}
                    </select>
                  </Field>
                  <Field label={t("比较条件")}>
                    <select
                      aria-label={t("比较条件")}
                      value={item.comparison}
                      onChange={(e) =>
                        rule(index, "comparison", e.target.value)
                      }
                    >
                      {[
                        ["gte", "≥"],
                        ["gt", ">"],
                        ["lte", "≤"],
                        ["lt", "<"],
                        ["eq", "="],
                      ].map(([key, name]) => (
                        <option key={key} value={key}>
                          {name}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <Field label={t("触发阈值")}>
                    <input
                      type="number"
                      required
                      min={0}
                      max={1e12}
                      step="any"
                      value={item.threshold ?? ""}
                      onChange={(e) =>
                        rule(
                          index,
                          "threshold",
                          e.target.value === "" ? null : Number(e.target.value),
                        )
                      }
                    />
                  </Field>
                  <label className="check">
                    <input
                      type="checkbox"
                      checked={item.enabled}
                      onChange={(e) => rule(index, "enabled", e.target.checked)}
                    />
                    {t("启用这条规则")}
                  </label>
                </div>
                <details>
                  <summary>{t("高级时长与重复提示")}</summary>
                  <div className="observer-fields">
                    {[
                      ["hold_us", t("条件采样时长（秒）")],
                      ["cooldown_us", t("重复提示间隔（秒）")],
                      ["maximum_gap_us", t("最大采样间隔（秒）")],
                    ].map(([key, label]) => (
                      <Field key={key} label={label}>
                        <input
                          type="number"
                          required
                          min={key === "maximum_gap_us" ? 0.000001 : 0}
                          max={1e6}
                          step="0.000001"
                          value={item[key] === null ? "" : item[key] / 1e6}
                          onChange={(e) =>
                            rule(
                              index,
                              key,
                              e.target.value === ""
                                ? null
                                : Math.round(Number(e.target.value) * 1e6),
                            )
                          }
                        />
                      </Field>
                    ))}
                  </div>
                </details>
                <Button
                  type="button"
                  onClick={() =>
                    change({
                      ...value,
                      rules: value.rules.filter(
                        (_: any, at: number) => at !== index,
                      ),
                    })
                  }
                >
                  {t("删除规则")}
                </Button>
              </fieldset>
            ))}
            <Button
              type="button"
              disabled={value.rules.length >= 32}
              onClick={() => {
                const next = structuredClone(catalogue.defaults.rules[0]);
                next.id = "rule-" + crypto.randomUUID().slice(0, 8);
                change({ ...value, rules: [...value.rules, next] });
              }}
            >
              {t("添加预警规则")}
            </Button>
          </fieldset>
        )}
        {valid && <p role="status">{t("配置校验通过；保存时会再次校验。")}</p>}
        <ErrorBox error={error} />
        <div className="modal-actions">
          <Button type="button" disabled={busy} onClick={close}>
            {t("取消")}
          </Button>
          <Button type="submit" variant="primary" disabled={busy}>
            {t("保存观察配置")}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export default function EcologyObserver({
  root: campaignRoot,
  checkpoint,
  write,
}: {
  root: string;
  checkpoint?: string;
  write: boolean;
}) {
  const root = campaignRoot + "/observer",
    client = useQueryClient();
  const language = useLocale() === "en" ? "en" : "zh";
  const [editing, setEditing] = useState(false),
    [selected, setSelected] = useState("");
  const [before, setBefore] = useState(""),
    [kind, setKind] = useState(""),
    [revisionBefore, setRevisionBefore] = useState("");
  const detail = useQuery({
    queryKey: ["ecology-observer", root],
    queryFn: () => api<any>(root),
    refetchInterval: 3000,
  });
  const history = useQuery({
    queryKey: ["ecology-observer-revisions", root, revisionBefore],
    queryFn: () =>
      api<any>(
        root +
          "/revisions" +
          (revisionBefore ? "?before=" + revisionBefore : ""),
      ),
    enabled: !!detail.data,
  });
  const params = new URLSearchParams();
  if (selected) params.set("configuration_revision", selected);
  if (checkpoint) params.set("checkpoint_id", checkpoint);
  if (before) params.set("before", before);
  if (kind) params.set("kind", kind);
  const feed = useQuery({
    queryKey: ["ecology-observer-feed", root, params.toString()],
    queryFn: () => api<any>(root + "/entries?" + params),
    enabled: !!detail.data,
    refetchInterval: before ? false : 3000,
  });
  function refresh() {
    void client.invalidateQueries({
      predicate: (query) =>
        String(query.queryKey[0]).startsWith("ecology-observer"),
    });
  }
  const retry = useMutation({
    mutationFn: () =>
      post(root + "/retry", {
        expected_revision: detail.data.observer.revision,
      }),
    onSuccess: refresh,
  });
  if (!detail.data)
    return (
      <>
        <ErrorBox error={detail.error} />
        <Loading />
      </>
    );
  const current = detail.data.observer,
    config = feed.data?.configuration;
  const download = new URLSearchParams({
    configuration_revision: String(config?.revision ?? current?.revision ?? 1),
  });
  if (checkpoint) download.set("checkpoint_id", checkpoint);
  return (
    <section
      className="ecology-group observer-panel"
      aria-label={t("生态观察与预警")}
    >
      <div className="observer-toolbar">
        <h3>{t("生态观察与预警")}</h3>
        <Button disabled={!write} onClick={() => setEditing(true)}>
          {t("配置观察")}
        </Button>
      </div>
      <p className="footnote">
        {t(
          "事件说明与预警来自已提交证据，独立于内核；此处不判断意识的意图，也不执行训练干预。",
        )}
      </p>
      <p role="status">
        {current?.configuration.enabled
          ? t("已处理至恢复点 r{done}；当前最新为 r{latest}。", {
              done: current.next_checkpoint_revision - 1,
              latest: detail.data.latest_checkpoint_revision,
            })
          : t("生态观察当前关闭；原始实验事件继续按实验协议保存。")}
      </p>
      {current?.job_error && (
        <>
          <ErrorBox error={current.job_error} />
          <Button
            disabled={!write || retry.isPending}
            onClick={() => retry.mutate()}
          >
            {t("重试观察任务")}
          </Button>
        </>
      )}
      <ErrorBox
        error={detail.error || history.error || feed.error || retry.error}
      />
      {current?.configuration.enabled && (
        <ObserverSpeech
          key={root + ":" + current.revision + ":" + language}
          root={root}
          revision={current.revision}
        />
      )}
      <div className="observer-fields">
        <Field label={t("观察规则版本")}>
          <select
            aria-label={t("观察规则版本")}
            value={selected}
            onChange={(e) => {
              setSelected(e.target.value);
              setBefore("");
            }}
          >
            <option value="">{t("当前规则版本")}</option>
            {selected &&
              !history.data?.rows.some(
                (row: any) => String(row.revision) === selected,
              ) && <option value={selected}>r{selected}</option>}
            {history.data?.rows.map((row: any) => (
              <option key={row.revision} value={row.revision}>
                r{row.revision} ·{" "}
                {row.configuration.enabled ? t("启用") : t("关闭")}
              </option>
            ))}
          </select>
        </Field>
        <Field label={t("观察条目类型")}>
          <select
            aria-label={t("观察条目类型")}
            value={kind}
            onChange={(e) => {
              setKind(e.target.value);
              setBefore("");
            }}
          >
            <option value="">{t("全部")}</option>
            {["event", "summary", "warning"].map((key) => (
              <option key={key} value={key}>
                {t(states[key as keyof typeof states])}
              </option>
            ))}
          </select>
        </Field>
      </div>
      <div className="query-controls">
        {history.data?.more && (
          <Button
            onClick={() =>
              setRevisionBefore(String(history.data.rows.at(-1).revision))
            }
          >
            {t("更早规则版本")}
          </Button>
        )}
        {revisionBefore && (
          <Button onClick={() => setRevisionBefore("")}>
            {t("最新规则版本")}
          </Button>
        )}
        {config && (
          <a
            className="text-link"
            download
            href={"/api/v2" + root + "/export?" + download}
          >
            {t("导出当前规则的观察 JSONL")}
          </a>
        )}
      </div>
      {config && (
        <p className="footnote">
          {t(
            "本规则版本从 r{first} 开始；页面仅显示所选种群恢复点及此前已生成的条目。",
            { first: config.first_checkpoint_revision },
          )}
        </p>
      )}
      {!selected &&
        current?.configuration.enabled &&
        Object.keys(current.rule_state).length > 0 && (
          <details>
            <summary>{t("最新规则状态（不随历史恢复点切换）")}</summary>
            <ul>
              {Object.entries(current.rule_state).map(([key, state]: any) => (
                <li key={key}>
                  {key} ·{" "}
                  {t(
                    states[state.status as keyof typeof states] ?? state.status,
                  )}
                </li>
              ))}
            </ul>
          </details>
        )}
      {feed.isPending ? (
        <Loading />
      ) : feed.data?.rows.length ? (
        <ol className="observer-feed">
          {feed.data.rows.map((row: any) => (
            <li key={row.id} className={"observer-entry observer-" + row.kind}>
              <div className="observer-toolbar">
                <strong>
                  {t(
                    states[row.body.code as keyof typeof states] ??
                      states[row.kind as keyof typeof states],
                  )}
                </strong>
                <small>r{row.body.source.checkpoint_revision}</small>
              </div>
              {row.body.rule_id && (
                <p>
                  {row.body.facts.rule.label || row.body.rule_id} ·{" "}
                  {
                    detail.data.catalogue.metrics[row.body.facts.rule.metric]?.[
                      language
                    ]
                  }
                </p>
              )}
              <p>{row.body.text[language]}</p>
              {row.body.kind === "warning" && (
                <p>
                  {t("采样值：{value}；采样时间：{time}。", {
                    value: row.body.facts.value ?? t("未判定"),
                    time: row.body.facts.sample_time_us
                      ? timeLabel(row.body.facts.sample_time_us)
                      : t("未判定"),
                  })}
                </p>
              )}
              <details>
                <summary>{t("查看事实与原始依据")}</summary>
                <pre>
                  {JSON.stringify(
                    {
                      facts: row.body.facts,
                      source: row.body.source,
                      content_hash: row.body.content_hash,
                    },
                    null,
                    2,
                  )}
                </pre>
              </details>
            </li>
          ))}
        </ol>
      ) : (
        <Empty
          title={t("此范围尚无观察条目")}
          detail={t(
            "启用后由后台任务生成；关闭页面不会停止处理。历史事件仍可在原始事件列表查看。",
          )}
        />
      )}
      <div className="query-controls">
        <Button disabled={!before} onClick={() => setBefore("")}>
          {t("最新观察")}
        </Button>
        <Button
          disabled={!feed.data?.more}
          onClick={() => setBefore(feed.data.rows.at(-1).id)}
        >
          {t("更早观察")}
        </Button>
      </div>
      <Link
        className="text-link"
        to="/docs?doc=docs%2Fzh%2Fv2-ecology-observer.md"
      >
        {t("观察与预警的证据边界")}
      </Link>
      <EcologyAI key={root} root={root} checkpoint={checkpoint} write={write} />
      {editing && (
        <ObserverEditor
          key={root}
          root={root}
          current={current}
          catalogue={detail.data.catalogue}
          close={() => setEditing(false)}
          saved={() => {
            setEditing(false);
            setSelected("");
            setBefore("");
            setRevisionBefore("");
            refresh();
          }}
        />
      )}
    </section>
  );
}
