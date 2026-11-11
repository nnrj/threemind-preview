import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useProjectSearchParams as useSearchParams } from "./projectRouting";
import { ArrowRight, Download, GitBranch, Plus } from "lucide-react";
import { api, post, projectPath, timeLabel, numberLabel } from "./api";
import { t } from "./i18n";
import {
  Badge,
  Button,
  Empty,
  ErrorBox,
  Field,
  Loading,
  Modal,
  PageTitle,
  useWorkspace,
} from "./ui";
import {
  ConfigurationEditor,
  type ConfigurationHandle,
  useCatalogue,
} from "./configuration";

type Page = { rows: any[]; more: boolean; next?: number };

function Paging({
  offset,
  more,
  change,
  disabled = false,
}: {
  offset: number;
  more?: boolean;
  change: (n: number) => void;
  disabled?: boolean;
}) {
  return (
    <div className="development-pagination">
      <Button
        type="button"
        variant="quiet"
        disabled={disabled || !offset}
        onClick={() => change(Math.max(0, offset - 30))}
      >
        {t("上一页")}
      </Button>
      <span>{t("第 {page} 页", { page: offset / 30 + 1 })}</span>
      <Button
        type="button"
        variant="quiet"
        disabled={disabled || !more}
        onClick={() => change(offset + 30)}
      >
        {t("下一页")}
      </Button>
    </div>
  );
}

function NewDevelopment({
  source,
  close,
  done,
}: {
  source?: any;
  close: () => void;
  done: () => void;
}) {
  const { project } = useWorkspace(),
    catalogue = useCatalogue(),
    editor = useRef<ConfigurationHandle>(null);
  const [name, setName] = useState(
    source ? t("继承后发育") : t("新的发育训练"),
  );
  const [objective, setObjective] = useState(
    t("观察环境刺激对连接形成、巩固和遗忘的影响。"),
  );
  const [nonce, setNonce] = useState(() => crypto.randomUUID());
  const mutation = useMutation({
    mutationFn: async () => {
      const spec = await editor.current?.validate();
      if (!spec) return false;
      await post(`${projectPath(project!.id)}/development`, {
        operation_id: nonce,
        name,
        objective,
        source_version_id: source?.id ?? null,
        spec,
      });
      return true;
    },
    onSuccess: (success) => {
      if (success) done();
    },
  });
  const dirty = () => {
    setNonce(crypto.randomUUID());
    mutation.reset();
  };
  return (
    <Modal
      open
      onOpenChange={(value) => {
        if (!value && !mutation.isPending) close();
      }}
      title={t("新建发育训练")}
      wide
      description={t(
        "使用普通运行时持续塑造连接；训练过程保存在数据库，先天版本由你按恢复点登记。",
      )}
    >
      <form
        onSubmit={(e) => {
          e.preventDefault();
          mutation.mutate();
        }}
      >
        <Field label={t("训练名称")}>
          <input
            required
            maxLength={120}
            value={name}
            disabled={mutation.isPending}
            onChange={(e) => {
              setName(e.target.value);
              dirty();
            }}
          />
        </Field>
        <Field label={t("研究目标与环境说明")}>
          <textarea
            required
            maxLength={8000}
            rows={3}
            value={objective}
            disabled={mutation.isPending}
            onChange={(e) => {
              setObjective(e.target.value);
              dirty();
            }}
          />
        </Field>
        <div className="development-origin">
          <GitBranch size={17} />
          <div>
            <strong>{source ? source.name : t("从空白结构开始")}</strong>
            <p>
              {source
                ? t(
                    "保留已形成结构与感官身份，清空活动、在途事件和外部环境状态，从模拟时间零开始。",
                  )
                : t("连接由本次声明的刺激形成；不会预置语义连接。")}
            </p>
          </div>
        </div>
        <ErrorBox error={catalogue.error || mutation.error} />
        {catalogue.isPending ? (
          <Loading />
        ) : (
          catalogue.data && (
            <ConfigurationEditor
              ref={editor}
              project={project!.id}
              catalogue={catalogue.data}
              initial={
                source
                  ? {
                      ...source.protocol,
                      study_id: null,
                      condition: null,
                      block_seed: null,
                      phases: [],
                      intervention: null,
                    }
                  : {
                      ...catalogue.data.defaults,
                      clock: "unbounded",
                      duration_s: null,
                    }
              }
              lockedPaths={source?.locked_paths ?? []}
              lockedMessage={t("此创建方式须保留来源配置，不能修改该字段。")}
              onDirty={dirty}
              readOnly={mutation.isPending}
            />
          )
        )}
        <p className="hint">
          {t(
            "训练中另行添加的输入或参数修改仍按普通运行留证；登记版本使用所选恢复点当时的实际配置。",
          )}
        </p>
        <div className="modal-actions">
          <Button
            type="button"
            variant="quiet"
            disabled={mutation.isPending}
            onClick={close}
          >
            {t("取消")}
          </Button>
          <Button
            type="submit"
            disabled={mutation.isPending || !catalogue.data}
          >
            <Plus size={16} />
            {mutation.isPending ? t("正在创建…") : t("创建并训练")}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function Registration({
  initialRun,
  close,
  done,
}: {
  initialRun?: string;
  close: () => void;
  done: (id: string) => void;
}) {
  const { project } = useWorkspace(),
    base = projectPath(project!.id);
  const [run, setRun] = useState(initialRun ?? ""),
    [q, setQ] = useState(""),
    [offset, setOffset] = useState(0);
  const [cp, setCp] = useState<any>(),
    [cursors, setCursors] = useState<(number | null)[]>([null]);
  const [name, setName] = useState(t("新的先天版本")),
    [note, setNote] = useState(
      t("按研究者选择的恢复点登记；未执行自动适应度筛选。"),
    );
  const [nonce, setNonce] = useState(() => crypto.randomUUID());
  const runs = useQuery({
    queryKey: ["registration-runs", project?.id, q, offset],
    queryFn: () =>
      api<Page>(
        `${base}/model-library?archived=all&q=${encodeURIComponent(q)}&offset=${offset}`,
      ),
    enabled: !initialRun,
  });
  const before = cursors[cursors.length - 1];
  const points = useQuery({
    queryKey: ["registration-points", project?.id, run, before],
    queryFn: () =>
      api<Page>(
        `${base}/runs/${run}/versions${before == null ? "" : `?before=${before}`}`,
      ),
    enabled: !!run,
    gcTime: 0,
  });
  const mutation = useMutation({
    mutationFn: () =>
      post(`${base}/innate-versions`, {
        operation_id: nonce,
        name,
        selection_note: note,
        run_id: run,
        checkpoint_id: cp.id,
        expected_state_hash: cp.state_hash,
      }),
    onSuccess: (value) => done(value.id),
  });
  const dirty = () => {
    setNonce(crypto.randomUUID());
    mutation.reset();
  };
  return (
    <Modal
      open
      title={t("登记先天版本")}
      wide
      onOpenChange={(value) => {
        if (!value && !mutation.isPending) close();
      }}
      description={t(
        "固定一个已提交的恢复点并记录选择依据。原始状态不会被改写，同一训练可以登记多个版本。",
      )}
    >
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (cp) mutation.mutate();
        }}
      >
        {!initialRun && (
          <div className="panel">
            <Field label={t("查找来源意识")}>
              <input
                value={q}
                disabled={mutation.isPending}
                onChange={(e) => {
                  setQ(e.target.value);
                  setOffset(0);
                  setRun("");
                  setCp(undefined);
                  setCursors([null]);
                  dirty();
                }}
              />
            </Field>
            <Field label={t("来源意识")}>
              <select
                aria-label={t("来源意识")}
                value={run}
                disabled={mutation.isPending}
                onChange={(e) => {
                  setRun(e.target.value);
                  setCp(undefined);
                  setCursors([null]);
                  dirty();
                }}
              >
                <option value="">{t("请选择")}</option>
                {runs.data?.rows.map((row) => (
                  <option key={row.id} value={row.id}>
                    {row.name}
                  </option>
                ))}
              </select>
            </Field>
            <Paging
              offset={offset}
              more={runs.data?.more}
              disabled={mutation.isPending}
              change={(value) => {
                setOffset(value);
                setRun("");
                setCp(undefined);
                setCursors([null]);
                dirty();
              }}
            />
          </div>
        )}
        <ErrorBox error={runs.error || points.error || mutation.error} />
        {run && (
          <>
            <div className="development-checkpoints">
              {points.isPending ? (
                <Loading />
              ) : (
                points.data?.rows.map((point) => (
                  <label
                    key={point.id}
                    className={cp?.id === point.id ? "selected" : ""}
                  >
                    <input
                      type="radio"
                      name="checkpoint"
                      checked={cp?.id === point.id}
                      disabled={mutation.isPending}
                      onChange={() => {
                        setCp(point);
                        dirty();
                      }}
                    />
                    <span>
                      <strong>
                        r{point.revision} · {timeLabel(point.time_us)}
                      </strong>
                      <span>{point.label}</span>
                      <code>{point.state_hash}</code>
                    </span>
                  </label>
                ))
              )}
              {points.data?.rows.length === 0 && (
                <p>
                  {t("还没有已提交的恢复点，请等待运行提交或手动请求检查点。")}
                </p>
              )}
            </div>
            <div className="development-pagination">
              <Button
                type="button"
                variant="quiet"
                disabled={cursors.length === 1}
                onClick={() => setCursors(cursors.slice(0, -1))}
              >
                {t("上一页")}
              </Button>
              <Button
                type="button"
                variant="quiet"
                disabled={!points.data?.more}
                onClick={() => setCursors([...cursors, points.data!.next!])}
              >
                {t("下一页")}
              </Button>
            </div>
          </>
        )}
        {cp && (
          <p className="hint">
            {t("已固定选择：修订 {revision}，模拟时间 {time}。", {
              revision: cp.revision,
              time: timeLabel(cp.time_us),
            })}
          </p>
        )}
        <Field label={t("版本名称")}>
          <input
            required
            maxLength={120}
            value={name}
            disabled={mutation.isPending}
            onChange={(e) => {
              setName(e.target.value);
              dirty();
            }}
          />
        </Field>
        <Field label={t("选择依据与局限")}>
          <textarea
            required
            rows={3}
            maxLength={8000}
            value={note}
            disabled={mutation.isPending}
            onChange={(e) => {
              setNote(e.target.value);
              dirty();
            }}
          />
        </Field>
        <div className="modal-actions">
          <Button
            type="button"
            variant="quiet"
            disabled={mutation.isPending}
            onClick={close}
          >
            {t("取消")}
          </Button>
          <Button type="submit" disabled={!cp || mutation.isPending}>
            {mutation.isPending ? t("正在登记…") : t("登记所选恢复点")}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function VersionDetail({
  id,
  train,
  choose,
  write,
}: {
  id: string;
  train: (source: any) => void;
  choose: (id: string) => void;
  write: boolean;
}) {
  const { project } = useWorkspace(),
    base = projectPath(project!.id),
    client = useQueryClient(),
    catalogue = useCatalogue();
  const [format, setFormat] = useState("tmind");
  const detail = useQuery({
    queryKey: ["innate-version", project?.id, id],
    queryFn: () => api(`${base}/innate-versions/${id}`),
    gcTime: 0,
  });
  const jobs = useQuery({
    queryKey: ["innate-exports", project?.id, id],
    queryFn: () => api<any[]>(`${base}/innate-versions/${id}/exports`),
    refetchInterval: 3000,
  });
  const exportModel = useMutation({
    mutationFn: () => post(`${base}/innate-versions/${id}/exports`, { format }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["innate-exports"] }),
  });
  const value = detail.data;
  if (!value)
    return (
      <>
        <ErrorBox error={detail.error} />
        {detail.isPending && <Loading />}
      </>
    );
  return (
    <article className="panel development-detail">
      <div className="development-heading">
        <div>
          <span className="eyebrow">INNATE VERSION · {value.generation}</span>
          <h2>{value.name}</h2>
        </div>
        <Button disabled={!write} onClick={() => train(value)}>
          <GitBranch size={16} />
          {t("从此版本发育")}
        </Button>
      </div>
      <p className="preserve-lines">{value.selection_note}</p>
      <dl className="development-facts">
        <dt>{t("来源恢复点")}</dt>
        <dd>
          <Link to={`/runs/${value.run_id}`}>
            r{value.source_revision} · {timeLabel(value.source_time_us)}{" "}
            <ArrowRight size={14} />
          </Link>
        </dd>
        <dt>{t("来源状态校验和")}</dt>
        <dd>
          <code>{value.state_hash}</code>
        </dd>
        <dt>{t("出生规则")}</dt>
        <dd>
          <code>{value.birth_rule}</code>
        </dd>
        <dt>{t("形成记录")}</dt>
        <dd>
          {value.development
            ? value.development.objective
            : t("来自已有意识的恢复点；本模块未记录此前的发育训练。")}
        </dd>
      </dl>
      <h3>{t("先天版本谱系")}</h3>
      <ol className="development-lineage">
        {[...value.lineage].reverse().map((item: any) => (
          <li key={item.id}>
            <button
              type="button"
              onClick={() => choose(item.id)}
              disabled={item.id === id}
            >
              {item.name}
            </button>
            <code>{item.state_hash.slice(0, 16)}</code>
          </li>
        ))}
      </ol>
      {value.lineage_truncated && (
        <p className="hint">
          {t("这里只显示最近一百层祖先，可点击最早一层继续追溯。")}
        </p>
      )}
      {!!value.children.length && (
        <div className="development-children">
          <span>{t("已登记后代")}</span>
          {value.children.map((item: any) => (
            <Button
              key={item.id}
              variant="quiet"
              onClick={() => choose(item.id)}
            >
              {item.name}
            </Button>
          ))}
        </div>
      )}
      {value.children_more && (
        <p className="hint">
          {t("当前显示前三十个后代；更多版本可在左侧检索。")}
        </p>
      )}
      <details>
        <summary>{t("查看固定配置（图形 / JSON）")}</summary>
        {catalogue.data && (
          <ConfigurationEditor
            key={id}
            initial={value.protocol}
            catalogue={catalogue.data}
            project={project!.id}
            readOnly
          />
        )}
      </details>
      <section className="development-export">
        <h3>{t("导出出生模型")}</h3>
        <p>
          {t(
            "导出的是可独立运行、仍可被刺激塑造的新个体初态。完整继续原个体请使用来源意识的模型导出。",
          )}
        </p>
        <Field label={t("模型格式")}>
          <select
            aria-label={t("模型格式")}
            value={format}
            onChange={(e) => setFormat(e.target.value)}
          >
            <option value="tmind">{t(".tmind · 标准模型本体")}</option>
            <option value="json">{t("JSON · 等价模型转换")}</option>
            <option value="bundle">{t("ZIP · 模型与形成清单")}</option>
          </select>
        </Field>
        <Button
          disabled={!write || exportModel.isPending}
          onClick={() => exportModel.mutate()}
        >
          <Download size={16} />
          {t("生成导出")}
        </Button>
        <ErrorBox error={exportModel.error || jobs.error} />
        <p className="hint">
          {t(
            "形成清单包含来源校验和与选择依据；原始刺激、图表和完整过程数据从来源意识另行导出。",
          )}
        </p>
        <ul className="development-export-list">
          {jobs.data?.map((job) => (
            <li key={job.id}>
              <span>{job.params.format}</span>
              <Badge status={job.status} />
              {job.result?.artifact_id && (
                <a
                  href={`/api/v2${base}/artifacts/${job.result.artifact_id}`}
                  download
                >
                  {t("下载文件")}
                </a>
              )}
              {job.error && <ErrorBox error={job.error} />}
            </li>
          ))}
        </ul>
      </section>
    </article>
  );
}

export default function Development() {
  const [params] = useSearchParams();
  const { project } = useWorkspace(),
    base = projectPath(project!.id),
    client = useQueryClient(),
    write = project!.role !== "viewer";
  const [tab, setTab] = useState<"sessions" | "versions">(
      params.get("version") ? "versions" : "sessions",
    ),
    [offset, setOffset] = useState(0),
    [q, setQ] = useState("");
  const [newSource, setNewSource] = useState<any>(),
    [newOpen, setNewOpen] = useState(false),
    [registerRun, setRegisterRun] = useState<string | null>(null),
    [selected, setSelected] = useState(params.get("version") || "");
  const rows = useQuery({
    queryKey: ["development-library", project?.id, tab, q, offset],
    queryFn: () =>
      api<Page>(
        `${base}/${tab === "sessions" ? "development" : "innate-versions"}?q=${encodeURIComponent(q)}&offset=${offset}`,
      ),
    refetchInterval: tab === "sessions" ? 3000 : false,
  });
  const show = (next: "sessions" | "versions") => {
    setTab(next);
    setOffset(0);
    setQ("");
  };
  return (
    <>
      <PageTitle
        eyebrow="DEVELOPMENT & INHERITANCE"
        title={t("发育与先天模型")}
        description={t(
          "追踪刺激塑造连接的过程，登记可复用的先天版本，并沿真实来源追溯谱系。",
        )}
        actions={
          <>
            <Button
              variant="quiet"
              disabled={!write}
              onClick={() => setRegisterRun("")}
            >
              {t("登记已有恢复点")}
            </Button>
            <Button
              disabled={!write}
              onClick={() => {
                setNewSource(undefined);
                setNewOpen(true);
              }}
            >
              <Plus size={16} />
              {t("新建发育训练")}
            </Button>
          </>
        }
      />
      <div className="development-guide">
        <div>
          <strong>{t("发育训练")}</strong>
          <p>{t("环境输入 → 运行时可塑变化 → 数据库检查点")}</p>
        </div>
        <ArrowRight size={18} />
        <div>
          <strong>{t("登记先天版本")}</strong>
          <p>{t("选择恢复点并说明依据 → 固定来源与谱系")}</p>
        </div>
        <ArrowRight size={18} />
        <div>
          <strong>{t("继承出生 / 独立部署")}</strong>
          <p>{t("保留学习结构 → 重置活动与时间 → 接入新刺激")}</p>
        </div>
      </div>
      <p className="hint">
        {t(
          "本页提供发育训练与人工版本选择，不自动按活跃度筛选后代，也不把训练完成视为意识或 AGI 已成立。",
        )}{" "}
        <Link to="/docs?doc=docs/zh/v2-development.md">
          {t("阅读训练与继承说明")}
        </Link>
      </p>
      <div className="tabs" role="tablist" aria-label={t("发育模型页面")}>
        <button
          role="tab"
          aria-selected={tab === "sessions"}
          className={tab === "sessions" ? "active" : ""}
          onClick={() => show("sessions")}
        >
          {t("发育训练")}
        </button>
        <button
          role="tab"
          aria-selected={tab === "versions"}
          className={tab === "versions" ? "active" : ""}
          onClick={() => show("versions")}
        >
          {t("先天版本")}
        </button>
      </div>
      <Field label={t("检索训练或版本")}>
        <input
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setOffset(0);
          }}
        />
      </Field>
      <ErrorBox error={rows.error} />
      {rows.isPending ? (
        <Loading />
      ) : tab === "sessions" ? (
        <div className="development-sessions">
          {rows.data?.rows.map((row) => (
            <article className="panel" key={row.id}>
              <div className="development-heading">
                <h2>{row.name}</h2>
                <Badge status={row.status} />
              </div>
              <p className="preserve-lines">{row.objective}</p>
              <p>
                {row.source_name
                  ? `${t("先天来源")}：${row.source_name}`
                  : t("从空白结构开始")}
              </p>
              <div className="development-metrics">
                <span>{timeLabel(row.time_us)}</span>
                <span>
                  {t("节点数")} {numberLabel(row.metrics?.nodes)}
                </span>
                <span>
                  {t("有向边数")} {numberLabel(row.metrics?.edges)}
                </span>
              </div>
              <div className="development-actions">
                <Link className="button quiet" to={`/runs/${row.run_id}`}>
                  {t("观察、控制与证据")}
                  <ArrowRight size={16} />
                </Link>
                <Button
                  variant="quiet"
                  disabled={!write || !row.revision}
                  onClick={() => setRegisterRun(row.run_id)}
                >
                  {t("登记先天版本")}
                </Button>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="development-version-layout">
          <div className="development-version-list">
            {rows.data?.rows.map((row) => (
              <button
                key={row.id}
                className={selected === row.id ? "selected" : ""}
                onClick={() => setSelected(row.id)}
              >
                <strong>{row.name}</strong>
                <span>
                  {t("谱系代数 {generation} · 来源修订 {revision}", {
                    generation: row.generation,
                    revision: row.source_revision,
                  })}
                </span>
                <code>{row.state_hash.slice(0, 20)}</code>
              </button>
            ))}
          </div>
          {selected ? (
            <VersionDetail
              key={selected}
              id={selected}
              write={write}
              choose={setSelected}
              train={(source) => {
                setNewSource(source);
                setNewOpen(true);
              }}
            />
          ) : (
            <Empty
              title={t("选择一个先天版本")}
              detail={t(
                "查看固定配置、来源与谱系，或导出用于独立部署的出生模型。",
              )}
            />
          )}
        </div>
      )}
      {rows.data?.rows.length === 0 && (
        <Empty
          title={
            tab === "sessions" ? t("还没有发育训练") : t("还没有匹配的先天版本")
          }
          detail={t(
            "先运行一个发育过程，再从已提交的恢复点登记版本；也可以选择已有意识的恢复点。",
          )}
        />
      )}
      <Paging offset={offset} more={rows.data?.more} change={setOffset} />
      {newOpen && (
        <NewDevelopment
          source={newSource}
          close={() => setNewOpen(false)}
          done={() => {
            setNewOpen(false);
            show("sessions");
            client.invalidateQueries({ queryKey: ["development-library"] });
            client.invalidateQueries({ queryKey: ["runs"] });
          }}
        />
      )}
      {registerRun !== null && (
        <Registration
          initialRun={registerRun || undefined}
          close={() => setRegisterRun(null)}
          done={(id) => {
            setRegisterRun(null);
            show("versions");
            setSelected(id);
            client.invalidateQueries({ queryKey: ["development-library"] });
          }}
        />
      )}
    </>
  );
}
