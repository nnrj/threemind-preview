import { ChangeEvent, useEffect, useMemo, useState } from "react";
import { kernelText, runtimeStatusText, useLocale, useT } from "./i18n";

const API = (import.meta.env.VITE_THREEMIND_API as string | undefined)?.replace(/\/$/, "") ?? "";

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, init);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail ?? `Request failed (${response.status})`);
  return payload as T;
}

export type ConsciousnessItem = {
  id: string;
  name: string;
  kernel?: string;
  parent_id?: string | null;
  snapshots: number;
  portraits: number;
  status: string;
  running: boolean;
  active?: boolean;
  metrics?: { tick?: number; node_count?: number; edge_count?: number };
  latest?: { metrics?: { tick?: number } } | null;
};

type PackageItem = {
  path: string;
  name: string;
  consciousness_id?: string;
  invalid?: boolean;
  size: number;
  snapshots?: number;
  portraits?: number;
  manifest?: { kernel_id?: string; spatial_embedding?: boolean; spatial_dimensions?: number };
};

type PackageDetails = {
  path: string;
  payload: {
    manifest?: Record<string, unknown>;
    state?: Record<string, unknown>;
    snapshots?: Array<Record<string, unknown>>;
    portraits?: Array<Record<string, unknown>>;
  };
};

const jsonHeaders = { "Content-Type": "application/json" };
const fileName = (path: string) => path.replaceAll("\\", "/").split("/").pop() ?? path;

export function PackageManager() {
  const t = useT();
  const locale = useLocale();
  const [items, setItems] = useState<PackageItem[]>([]);
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(12);
  const [selected, setSelected] = useState<string[]>([]);
  const [details, setDetails] = useState<PackageDetails | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [operation, setOperation] = useState("");
  const copy = locale === "en" ? {
    loading: "Loading model packages…",
    importing: "Importing model package…",
    opening: "Opening package details…",
    renaming: "Renaming model package…",
    deleting: "Deleting model package…",
    restoring: "Restoring package state…",
    refreshed: "Model package list refreshed.",
    imported: (name: string) => `Imported ${name}.`,
    renamed: "Model package renamed.",
    deleted: "Model package deleted.",
    restored: "Selected state restored to the model package.",
  } : {
    loading: "正在读取模型包…",
    importing: "正在导入模型包…",
    opening: "正在打开模型包详情…",
    renaming: "正在重命名模型包…",
    deleting: "正在删除模型包…",
    restoring: "正在恢复模型包状态…",
    refreshed: "模型包列表已刷新。",
    imported: (name: string) => `已导入 ${name}。`,
    renamed: "模型包已重命名。",
    deleted: "模型包已删除。",
    restored: "已将所选状态恢复到模型包。",
  };

  const refreshItems = async () => {
    const result = await api<{ items: PackageItem[] }>("/api/packages");
    setItems(result.items);
  };

  const load = async (announce = false) => {
    setBusy(true);
    setOperation(copy.loading);
    try {
      await refreshItems();
      if (announce) setMessage(copy.refreshed);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t("operationFailed"));
    } finally {
      setOperation("");
      setBusy(false);
    }
  };
  useEffect(() => { void load(); }, []);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return needle ? items.filter((item) =>
      `${item.name} ${fileName(item.path)} ${item.consciousness_id ?? ""} ${item.manifest?.kernel_id ?? ""}`.toLowerCase().includes(needle)
    ) : items;
  }, [items, query]);
  const pages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const safePage = Math.min(page, pages);
  const rows = filtered.slice((safePage - 1) * pageSize, safePage * pageSize);

  const importFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const data = new FormData();
    data.append("file", file);
    setBusy(true);
    setOperation(copy.importing);
    try {
      await api("/api/packages/import", { method: "POST", body: data });
      await refreshItems();
      setMessage(copy.imported(file.name));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "导入失败");
    } finally {
      event.target.value = "";
      setOperation("");
      setBusy(false);
    }
  };

  const openDetails = async (item: PackageItem) => {
    setBusy(true);
    setOperation(copy.opening);
    try {
      setDetails(await api<PackageDetails>(`/api/packages/${encodeURIComponent(fileName(item.path))}`));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "无法读取模型包详情");
    } finally {
      setOperation("");
      setBusy(false);
    }
  };

  const rename = async (item: PackageItem) => {
    const name = window.prompt("模型包中的意识名称", item.name)?.trim();
    if (!name) return;
    setBusy(true);
    setOperation(copy.renaming);
    try {
      await api(`/api/packages/${encodeURIComponent(fileName(item.path))}`, {
        method: "PATCH", headers: jsonHeaders, body: JSON.stringify({ name }),
      });
      await refreshItems();
      setMessage(copy.renamed);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "重命名失败");
    } finally {
      setOperation("");
      setBusy(false);
    }
  };

  const remove = async (names: string[]) => {
    if (!names.length || !window.confirm(`确定删除 ${names.length} 个模型包？此操作不可恢复。`)) return;
    setBusy(true);
    setOperation(copy.deleting);
    try {
      await api("/api/packages/batch-delete", {
        method: "POST", headers: jsonHeaders, body: JSON.stringify({ names }),
      });
      setSelected([]);
      await refreshItems();
      setMessage(copy.deleted);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "删除失败");
    } finally {
      setOperation("");
      setBusy(false);
    }
  };

  const restore = async (packageName: string, index: number, portrait: boolean) => {
    setBusy(true);
    setOperation(copy.restoring);
    try {
      await api(`/api/packages/${encodeURIComponent(packageName)}/restore?index=${index}&portrait=${portrait}`, { method: "POST" });
      setMessage(copy.restored);
      setDetails(null);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "恢复失败");
    } finally {
      setOperation("");
      setBusy(false);
    }
  };

  return <section className="management-page">
    <header>
      <div><h2>{t("modelPackage")}</h2><p>{t("modelPackagesDescription")}</p></div>
      <div className="page-actions">
        <label className="file-button" aria-disabled={busy}>{t("import")}<input type="file" accept=".tmind,.bbx" onChange={importFile} disabled={busy} /></label>
        <button type="button" onClick={() => void load(true)} disabled={busy}>{t("refresh")}</button>
      </div>
    </header>
    <div className="manager-toolbar">
      <input value={query} onChange={(event) => { setQuery(event.target.value); setPage(1); }} placeholder="按名称、ID、内核或文件名筛选" />
      <button className="danger" type="button" disabled={busy || !selected.length} onClick={() => void remove(selected)}>删除所选（{selected.length}）</button>
    </div>
    {operation && <div className="management-message is-pending" role="status"><span className="ui-spinner" aria-hidden="true" />{operation}</div>}
    {message && <div className="management-message">{message}</div>}
    <div className="record-table-wrap">
      <table className="record-table">
        <thead><tr><th><input type="checkbox" aria-label="选择当前页" checked={rows.length > 0 && rows.every((item) => selected.includes(fileName(item.path)))} onChange={(event) => {
          const names = rows.map((item) => fileName(item.path));
          setSelected(event.target.checked ? [...new Set([...selected, ...names])] : selected.filter((name) => !names.includes(name)));
        }} /></th><th>名称</th><th>模型 / 空间</th><th>意识 ID</th><th>快照 / 遗照</th><th>大小</th><th>操作</th></tr></thead>
        <tbody>{rows.map((item) => {
          const name = fileName(item.path);
          return <tr key={item.path}>
            <td><input type="checkbox" checked={selected.includes(name)} onChange={(event) => setSelected(event.target.checked ? [...selected, name] : selected.filter((value) => value !== name))} /></td>
            <td><strong>{item.name}</strong><small>{name}</small></td>
            <td>{item.invalid ? "无效模型包" : `${item.manifest?.kernel_id ?? "unified"} · ${item.manifest?.spatial_embedding ? `${item.manifest.spatial_dimensions ?? 0}D 空间` : "无空间基底"}`}</td>
            <td>{item.consciousness_id?.slice(0, 12) ?? "—"}</td>
            <td>{item.snapshots ?? 0} / {item.portraits ?? 0}</td>
            <td>{Math.max(1, Math.round(item.size / 1024))} KB</td>
            <td><div className="table-actions">
              <button type="button" disabled={busy || item.invalid} onClick={() => void openDetails(item)}>{t("details")}</button>
              <a href={`${API}/api/archive?path=${encodeURIComponent(item.path)}`}>{t("export")}</a>
              <button type="button" disabled={busy || item.invalid} onClick={() => void rename(item)}>重命名</button>
              <button type="button" disabled={busy} onClick={() => void remove([name])} className="danger">{t("delete")}</button>
            </div></td>
          </tr>;
        })}</tbody>
      </table>
      {!rows.length && <div className="empty-state"><strong>没有模型包</strong><span>可导入 .tmind 文件，或从运行中的意识保存模型包。</span></div>}
    </div>
    <div className="record-pagination"><span>共 {filtered.length} 条，第 {safePage} / {pages} 页</span>
      <label>每页 <select value={pageSize} onChange={(event) => { setPageSize(Number(event.target.value)); setPage(1); }}><option>12</option><option>24</option><option>48</option></select></label>
      <button disabled={safePage <= 1} onClick={() => setPage(safePage - 1)}>{t("previousPage")}</button>
      <button disabled={safePage >= pages} onClick={() => setPage(safePage + 1)}>{t("nextPage")}</button>
    </div>
    {details && <div className="settings-backdrop" onMouseDown={() => setDetails(null)}>
      <section className="archive-modal package-detail-modal" onMouseDown={(event) => event.stopPropagation()}>
        <header className="settings-header"><div><strong>模型包详情</strong><span>{fileName(details.path)}</span></div><button onClick={() => setDetails(null)}>×</button></header>
        <div className="package-summary-grid">
          <article><span>内核</span><strong>{String(details.payload.manifest?.kernel_id ?? "—")}</strong></article>
          <article><span>意识名称</span><strong>{String(details.payload.state?.name ?? "—")}</strong></article>
          <article><span>当前 tick</span><strong>{String(details.payload.state?.tick ?? 0)}</strong></article>
          <article><span>生命周期</span><strong>{String(details.payload.state?.life_state ?? "—")}</strong></article>
        </div>
        <h3>快照</h3>
        <div className="archive-list">{(details.payload.snapshots ?? []).map((record, index) =>
          <article className="archive-row" key={`snapshot-${index}`}><div><strong>{String(record.label ?? `快照 ${index + 1}`)}</strong><span>tick {String((record.metrics as Record<string, unknown> | undefined)?.tick ?? "—")}</span></div><button disabled={busy} onClick={() => void restore(fileName(details.path), index, false)}>{operation ? (locale === "en" ? "Restoring…" : "正在恢复…") : "恢复"}</button></article>
        )}{!(details.payload.snapshots ?? []).length && <p className="settings-note">包内没有快照。</p>}</div>
        <h3>遗照</h3>
        <div className="archive-list">{(details.payload.portraits ?? []).map((record, index) =>
          <article className="archive-row" key={`portrait-${index}`}><div><strong>{String(record.label ?? `遗照 ${index + 1}`)}</strong><span>tick {String((record.metrics as Record<string, unknown> | undefined)?.tick ?? "—")}</span></div><button disabled={busy} onClick={() => void restore(fileName(details.path), index, true)}>{operation ? (locale === "en" ? "Restoring…" : "正在恢复…") : "恢复"}</button></article>
        )}{!(details.payload.portraits ?? []).length && <p className="settings-note">包内没有遗照。</p>}</div>
      </section>
    </div>}
  </section>;
}

export function InstanceManager({
  items,
  loading,
  error,
  onRefresh,
  onOpenDetails,
}: {
  items: ConsciousnessItem[];
  loading: boolean;
  error: string;
  onRefresh: () => void;
  onOpenDetails: (item: ConsciousnessItem) => void;
}) {
  const t = useT();
  const locale = useLocale();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [selected, setSelected] = useState<string[]>([]);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("New consciousness");
  const [kernel, setKernel] = useState("anonymous-spatial-v3");
  const [v3NodeMode, setV3NodeMode] = useState<"anonymous" | "labeled-observation" | "literal-character">("anonymous");
  const [v3SpatialEnabled, setV3SpatialEnabled] = useState(true);
  const [message, setMessage] = useState("");
  const [busyAction, setBusyAction] = useState("");
  const copy = locale === "en" ? {
    creating: "Creating consciousness instance…",
    activating: "Switching the observed consciousness…",
    saving: "Saving consciousness package…",
    cloning: "Cloning consciousness instance…",
    continuing: "Continuing from the latest snapshot…",
    deleting: "Deleting consciousness instance…",
    batch: "Applying batch operation…",
    control: "Updating consciousness runtime…",
    importing: "Importing consciousness package…",
    created: "New consciousness instance created and running.",
    activated: "The observatory now follows this consciousness.",
    saved: (name: string) => `“${name}” was saved as a model package.`,
    cloned: (name: string) => `Created a direct clone of “${name}”.`,
    continued: (name: string, label: string) => `Continued “${name}” from ${label}.`,
    deleted: "Consciousness instance deleted.",
    batchDone: "Batch operation completed.",
    controlDone: "Runtime operation completed.",
    imported: (name: string) => `Imported “${name}” into consciousness archives.`,
  } : {
    creating: "正在创建意识实例…",
    activating: "正在切换当前观测的意识…",
    saving: "正在保存意识模型包…",
    cloning: "正在克隆意识实例…",
    continuing: "正在从最新快照继续运行…",
    deleting: "正在删除意识实例…",
    batch: "正在执行批量操作…",
    control: "正在更新意识运行状态…",
    importing: "正在导入意识模型包…",
    created: "新的意识实例已创建并开始运行。",
    activated: "画布现在正在观测该意识。",
    saved: (name: string) => `“${name}”已保存为模型包。`,
    cloned: (name: string) => `已从“${name}”创建直系克隆。`,
    continued: (name: string, label: string) => `已从“${name}”的${label}继续运行。`,
    deleted: "意识实例已删除。",
    batchDone: "批量操作已完成。",
    controlDone: "运行状态操作已完成。",
    imported: (name: string) => `已将“${name}”导入意识档案。`,
  };

  const perform = async <T,>(label: string, fallback: string, work: () => Promise<T>, success?: string): Promise<T | undefined> => {
    if (busyAction) return undefined;
    setBusyAction(label);
    setMessage("");
    try {
      const result = await work();
      if (success) setMessage(success);
      await Promise.resolve(onRefresh());
      return result;
    } catch (error) {
      setMessage(error instanceof Error ? error.message : fallback);
      return undefined;
    } finally {
      setBusyAction("");
    }
  };

  const rows = useMemo(() => items.filter((item) => {
    const text = `${item.name} ${item.id} ${item.kernel ?? ""}`.toLowerCase();
    return (!query || text.includes(query.toLowerCase())) && (status === "all" || item.status === status);
  }), [items, query, status]);

  const manifest = () => kernel === "anonymous-spatial-v3"
    ? { kernel_id: "anonymous-spatial-v3", name: "Spatial associative model", node_payload: "anonymous", weighted_edges: true, spatial_embedding: v3SpatialEnabled, spatial_dimensions: v3SpatialEnabled ? 3 : 0, parameters: { ...(v3SpatialEnabled ? { neighborhood_enabled: true, spatial_radius: 2.5, spatial_competition: 0 } : {}), sensory_encoding: v3NodeMode === "anonymous" ? "anonymous-distributed" : v3NodeMode } }
    : kernel === "anonymous-sensory-v2"
      ? { kernel_id: "anonymous-sensory-v2", name: "Anonymous sensory model", node_payload: "anonymous", weighted_edges: true, spatial_embedding: false, spatial_dimensions: 0, parameters: { sensory_encoding: "anonymous-distributed" } }
      : { kernel_id: "labeled-feature-v1", name: "Labeled baseline", node_payload: "labeled", weighted_edges: true, spatial_embedding: false, spatial_dimensions: 0, parameters: { sensory_encoding: "legacy-labeled" } };

  const create = async () => {
    const created = await perform(copy.creating, locale === "en" ? "Unable to create consciousness." : "创建意识失败。", async () => {
      await api("/api/consciousnesses", { method: "POST", headers: jsonHeaders, body: JSON.stringify({ name: name.trim() || "Unnamed consciousness", manifest: manifest() }) });
      return true;
    }, copy.created);
    if (created) {
      setCreating(false);
    }
  };
  const importPackage = async (file: File) => {
    const result = await perform(copy.importing, locale === "en" ? "Unable to import the .tmind package." : "无法导入 .tmind 模型包。", async () => {
      const data = new FormData();
      data.append("file", file);
      return api<{ name?: string }>("/api/packages/import", { method: "POST", body: data });
    });
    if (result) setMessage(copy.imported(result.name ?? file.name));
  };
  const control = async (id: string, action: string) => {
    await perform(copy.control, locale === "en" ? "Runtime operation failed." : "运行状态操作失败。", async () => {
      await api(`/api/consciousnesses/${encodeURIComponent(id)}/runtime/${action}`, { method: "POST" });
      return true;
    }, copy.controlDone);
  };
  const continueFromLatestSnapshot = async (item: ConsciousnessItem) => {
    const result = await perform(copy.continuing, locale === "en" ? "No snapshot is available to continue this consciousness." : "没有可用于继续运行的快照。", () => api<{ snapshot?: { label?: string; kind?: string } }>(`/api/consciousnesses/${encodeURIComponent(item.id)}/continue`, { method: "POST", headers: jsonHeaders, body: JSON.stringify({}) }));
    if (result) setMessage(copy.continued(item.name, result.snapshot?.label ?? (locale === "en" ? "the latest snapshot" : "最新快照")));
  };
  const activate = async (id: string) => {
    await perform(copy.activating, locale === "en" ? "Unable to switch the observed consciousness." : "切换观测意识失败。", async () => {
      await api(`/api/consciousnesses/${encodeURIComponent(id)}/activate`, { method: "POST" });
      return true;
    }, copy.activated);
  };
  const saveInstance = async (item: ConsciousnessItem, download: boolean) => {
    const result = await perform(copy.saving, locale === "en" ? "Unable to save consciousness package." : "保存意识模型包失败。", async () => {
      await api(`/api/consciousnesses/${encodeURIComponent(item.id)}/activate`, { method: "POST" });
      return api<{ path: string }>("/api/package/save", { method: "POST" });
    }, copy.saved(item.name));
    if (result && download) {
      const anchor = document.createElement("a");
      anchor.href = `${API}/api/archive?path=${encodeURIComponent(result.path)}`;
      anchor.click();
    }
  };
  const cloneInstance = async (item: ConsciousnessItem) => {
    const cloneName = window.prompt("克隆意识名称", `${item.name} clone`)?.trim();
    if (!cloneName) return;
    await perform(copy.cloning, locale === "en" ? "Unable to clone consciousness." : "克隆意识失败。", async () => {
      await api(`/api/consciousnesses/${encodeURIComponent(item.id)}/activate`, { method: "POST" });
      await api(`/api/package/clone?name=${encodeURIComponent(cloneName)}`, { method: "POST" });
      return true;
    }, copy.cloned(item.name));
  };
  const batch = async (action: string) => {
    if (!selected.length) return;
    await perform(copy.batch, locale === "en" ? "Batch operation failed." : "批量操作失败。", async () => {
      await api(`/api/consciousnesses/batch-control?action=${encodeURIComponent(action)}`, { method: "POST", headers: jsonHeaders, body: JSON.stringify(selected) });
      setSelected([]);
      return true;
    }, copy.batchDone);
  };
  const remove = async (item: ConsciousnessItem) => {
    if (!window.confirm(`删除意识实例“${item.name}”？此操作不可恢复。`)) return;
    await perform(copy.deleting, locale === "en" ? "Unable to delete consciousness." : "删除意识失败。", async () => {
      await api(`/api/consciousnesses/${encodeURIComponent(item.id)}`, { method: "DELETE" });
      return true;
    }, copy.deleted);
  };

  return <section className="management-page">
    <header><div><h2>{t("consciousnessManagement")}</h2><p>{t("consciousnessDescription")}</p></div><div className="page-actions"><button className="primary" disabled={Boolean(busyAction)} onClick={() => setCreating(true)}>{t("createConsciousness")}</button><label className="file-button">{locale === "en" ? "Import .tmind" : "导入 .tmind"}<input type="file" accept=".tmind,.bbx,application/zip" disabled={Boolean(busyAction)} onChange={(event) => { const file = event.target.files?.[0]; if (file) void importPackage(file); event.currentTarget.value = ""; }} /></label><button disabled={Boolean(busyAction)} onClick={onRefresh}>{t("refresh")}</button></div></header>
    <div className="manager-toolbar">
      <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="按意识名称、ID 或模型筛选" />
      <select value={status} onChange={(event) => setStatus(event.target.value)}><option value="all">{t("allStatuses")}</option><option value="active">{runtimeStatusText(locale, "active")}</option><option value="paused">{runtimeStatusText(locale, "paused")}</option><option value="dead">{runtimeStatusText(locale, "dead")}</option></select>
      <button disabled={Boolean(busyAction) || !selected.length} onClick={() => void batch("pause")}>批量暂停</button>
      <button disabled={Boolean(busyAction) || !selected.length} onClick={() => void batch("resume")}>批量继续</button>
      <button disabled={Boolean(busyAction) || !selected.length} onClick={() => void batch("stop")} className="danger">批量停止</button>
    </div>
    {busyAction && <div className="management-message is-pending" role="status"><span className="ui-spinner" aria-hidden="true" />{busyAction}</div>}
    {message && <div className="management-message">{message}</div>}
    {error && <div className="error">{error}</div>}
    {loading ? <p className="settings-note">正在读取意识实例…</p> : <div className="record-table-wrap"><table className="record-table">
      <thead><tr><th>选择</th><th>意识</th><th>模型</th><th>状态</th><th>节点 / 连接</th><th>谱系</th><th>操作</th></tr></thead>
      <tbody>{rows.map((item) => <tr key={item.id}>
        <td><input type="checkbox" disabled={Boolean(busyAction)} checked={selected.includes(item.id)} onChange={(event) => setSelected(event.target.checked ? [...selected, item.id] : selected.filter((id) => id !== item.id))} /></td>
        <td><strong>{item.name}{item.active ? " · 当前观察" : ""}</strong><small>{item.id}</small></td>
        <td>{item.kernel ?? "unified-associative"}</td>
        <td><span className={`state-badge state-${item.status}`}>{item.running ? "运行中" : item.status}</span><small>tick {item.metrics?.tick ?? item.latest?.metrics?.tick ?? 0}</small></td>
        <td>{item.metrics?.node_count ?? 0} / {item.metrics?.edge_count ?? 0}</td>
        <td>父意识 {item.parent_id?.slice(0, 8) ?? "—"}<small>{item.snapshots} 快照 · {item.portraits} 遗照</small></td>
        <td><div className="table-actions">
          <button disabled={Boolean(busyAction)} onClick={() => onOpenDetails(item)}>{t("details")}</button>
          {!item.active && <button disabled={Boolean(busyAction)} onClick={() => void activate(item.id)}>观察</button>}
          <button disabled={Boolean(busyAction)} onClick={() => void saveInstance(item, false)}>{t("save")}</button>
          <button disabled={Boolean(busyAction)} onClick={() => void saveInstance(item, true)}>{t("export")}</button>
          <button disabled={Boolean(busyAction)} onClick={() => void cloneInstance(item)}>克隆</button>
          <button disabled={Boolean(busyAction)} onClick={() => void control(item.id, "pause")}>暂停</button>
          <button disabled={Boolean(busyAction)} onClick={() => void ((item.running && item.status !== "dead") ? control(item.id, "resume") : continueFromLatestSnapshot(item))}>{item.running && item.status !== "dead" ? "继续运行" : "从最新快照继续"}</button>
          <button disabled={Boolean(busyAction)} className="danger" onClick={() => void control(item.id, "stop")}>停止</button>
          <button disabled={Boolean(busyAction)} className="danger" onClick={() => void remove(item)}>{t("delete")}</button>
        </div></td>
      </tr>)}</tbody>
    </table>{!rows.length && <div className="empty-state"><strong>没有符合条件的意识实例</strong></div>}</div>}
    {creating && <div className="settings-backdrop" onMouseDown={() => { if (!busyAction) setCreating(false); }}><section className="name-dialog operation-dialog" onMouseDown={(event) => event.stopPropagation()}>
      <h3>创建新意识实例</h3>
      <label className="settings-field">名称<input autoFocus value={name} onChange={(event) => setName(event.target.value)} /></label>
      <label className="settings-field">{locale === "en" ? "Model" : "模型"}<select value={kernel} onChange={(event) => setKernel(event.target.value)}><option value="anonymous-spatial-v3">{kernelText(locale, "anonymous-spatial-v3")}</option><option value="anonymous-sensory-v2">{kernelText(locale, "anonymous-sensory-v2")}</option><option value="labeled-feature-v1">{kernelText(locale, "labeled-feature-v1")}</option></select></label>
      {kernel === "anonymous-spatial-v3" && <label className="settings-field">{t("v3NodeMode")}<select value={v3NodeMode} onChange={(event) => setV3NodeMode(event.target.value as "anonymous" | "labeled-observation" | "literal-character")}><option value="anonymous">{t("v3Anonymous")}</option><option value="labeled-observation">{t("v3LabeledObservation")}</option><option value="literal-character">{t("v3LiteralCharacter")}</option></select><span className="settings-note">{t("v3NodeModeImmutable")}</span></label>}
      {kernel === "anonymous-spatial-v3" && <label className="settings-switch"><input type="checkbox" checked={v3SpatialEnabled} onChange={(event) => setV3SpatialEnabled(event.target.checked)} /> {t("enableSpatialEmbedding")}<span className="settings-note">{t("spatialEmbeddingCreationDetail")}</span></label>}
      {busyAction && <p className="dialog-operation" role="status"><span className="ui-spinner" aria-hidden="true" />{busyAction}</p>}
      <div className="actions"><button disabled={Boolean(busyAction)} onClick={() => setCreating(false)}>{t("cancel")}</button><button className="primary" disabled={Boolean(busyAction)} onClick={() => void create()}>{busyAction ? (locale === "en" ? "Creating…" : "正在创建…") : t("createAndRun")}</button></div>
    </section></div>}
  </section>;
}

type HistoryKind = "stimuli" | "interpretations" | "events";
type HistoryResult = { items: Array<Record<string, unknown>>; total: number; page: number; page_size: number; pages: number };

export function HistoryManager({
  kind,
  consciousnesses,
  onConfigure,
}: {
  kind: HistoryKind;
  consciousnesses: ConsciousnessItem[];
  onConfigure: () => void;
}) {
  const t = useT();
  const locale = useLocale();
  const [consciousnessId, setConsciousnessId] = useState("");
  const [queryDraft, setQueryDraft] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [result, setResult] = useState<HistoryResult>({ items: [], total: 0, page: 1, page_size: 50, pages: 1 });
  const [selected, setSelected] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!consciousnessId && consciousnesses.length) {
      setConsciousnessId(consciousnesses.find((item) => item.active)?.id ?? consciousnesses[0].id);
    }
  }, [consciousnessId, consciousnesses]);

  useEffect(() => {
    if (!consciousnessId) return;
    let alive = true;
    setLoading(true);
    api<HistoryResult>(`/api/consciousnesses/${encodeURIComponent(consciousnessId)}/history?kind=${kind}&page=${page}&page_size=${pageSize}&query=${encodeURIComponent(query)}`)
      .then((payload) => { if (alive) { setResult(payload); setError(""); } })
      .catch((caught) => { if (alive) setError(caught instanceof Error ? caught.message : "读取历史失败"); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [consciousnessId, kind, page, pageSize, query]);

  const title = kind === "stimuli" ? "刺激器管理" : kind === "interpretations" ? "解读器管理" : "事件历史";
  const download = () => {
    const blob = new Blob([JSON.stringify({ consciousness_id: consciousnessId, kind, exported_at: new Date().toISOString(), items: result.items }, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url; anchor.download = `${kind}-${consciousnessId}-${Date.now()}.json`; anchor.click();
    URL.revokeObjectURL(url);
  };

  return <section className="management-page">
    <header><div><h2>{title}</h2><p>{t("historyDescription")}</p></div><div className="page-actions"><button onClick={onConfigure}>{t("settings")}</button><button onClick={download} disabled={!result.items.length}>{t("currentPageExport")}</button></div></header>
    <div className="record-filters">
      <label>意识实例<select value={consciousnessId} onChange={(event) => { setConsciousnessId(event.target.value); setPage(1); }}>{consciousnesses.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.id.slice(0, 8)}</option>)}</select></label>
      <label>关键词<input value={queryDraft} onChange={(event) => setQueryDraft(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") { setQuery(queryDraft); setPage(1); } }} /></label>
      <div className="filter-actions"><button className="primary" onClick={() => { setQuery(queryDraft); setPage(1); }}>{t("search")}</button><button onClick={() => { setQueryDraft(""); setQuery(""); setPage(1); }}>{t("reset")}</button></div>
    </div>
    {error && <div className="error">{error}</div>}
    {loading && <div className="management-message is-pending" role="status"><span className="ui-spinner" aria-hidden="true" />{locale === "en" ? "Loading history…" : "正在读取历史记录…"}</div>}
    <div className="record-table-wrap"><table className="record-table">
      <thead>{kind === "stimuli" ? <tr><th>tick</th><th>来源</th><th>强度</th><th>刺激</th><th>操作</th></tr> : kind === "interpretations" ? <tr><th>tick</th><th>触发</th><th>供应商</th><th>重要</th><th>解读</th><th>操作</th></tr> : <tr><th>tick</th><th>类型</th><th>概要</th><th>操作</th></tr>}</thead>
      <tbody>{result.items.map((row, index) => kind === "stimuli" ? <tr key={index}><td>{String(row.tick ?? "—")}</td><td>{String(row.source ?? "—")}</td><td>{String(row.intensity ?? "—")}</td><td>{String(row.text ?? "")}</td><td><button onClick={() => setSelected(row)}>详情</button></td></tr> : kind === "interpretations" ? <tr key={index}><td>{String(row.tick ?? "—")}</td><td>{String(row.trigger ?? "—")}</td><td>{String(row.provider_id ?? "—")}</td><td>{row.important ? "是" : "否"}</td><td>{String(row.text ?? "")}</td><td><button onClick={() => setSelected(row)}>详情</button></td></tr> : <tr key={index}><td>{String(row.tick ?? "—")}</td><td>{String(row.kind ?? "—")}</td><td>{String(row.text ?? row.reason ?? row.name ?? "")}</td><td><button onClick={() => setSelected(row)}>详情</button></td></tr>)}</tbody>
    </table>{!result.items.length && <div className="empty-state"><strong>没有符合条件的记录</strong></div>}</div>
    <div className="record-pagination"><span>共 {result.total} 条，第 {result.page} / {Math.max(1, result.pages)} 页</span><label>每页 <select value={pageSize} onChange={(event) => { setPageSize(Number(event.target.value)); setPage(1); }}><option>25</option><option>50</option><option>100</option></select></label><button disabled={page <= 1} onClick={() => setPage(page - 1)}>上一页</button><button disabled={page >= result.pages} onClick={() => setPage(page + 1)}>下一页</button></div>
    {selected && <div className="settings-backdrop" onMouseDown={() => setSelected(null)}><section className="name-dialog history-detail" onMouseDown={(event) => event.stopPropagation()}><h3>记录详情</h3><dl>{Object.entries(selected).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{typeof value === "object" ? JSON.stringify(value, null, 2) : String(value)}</dd></div>)}</dl><div className="actions"><button onClick={() => setSelected(null)}>关闭</button></div></section></div>}
  </section>;
}

type StorageItem = {
  id: string;
  name: string;
  category: string;
  bytes: number;
  modified_at: number;
  selectable: boolean;
  action: string;
  note: string;
};

type StorageScan = {
  data_dir: string;
  total_bytes: number;
  items: StorageItem[];
  categories: Record<string, { count: number; bytes: number; selectable_count: number }>;
  confirmation_phrase: string;
  archive_writer?: { queued?: number; pending?: number };
};

const storageCategoryOrder = [
  "durable_records",
  "legacy_history",
  "model_packages",
  "temporary_files",
  "diagnostic_logs",
  "history_database",
  "database_sidecars",
  "archive_index",
  "configuration_and_credentials",
  "unclassified",
];

function storageCategoryText(locale: "en" | "zh-CN", category: string): string {
  const labels: Record<string, [string, string]> = {
    durable_records: ["Current durable records", "当前持久化记录"],
    legacy_history: ["Legacy JSON history", "旧版 JSON 历史"],
    model_packages: ["Model packages", "意识模型包"],
    temporary_files: ["Incomplete temporary files", "未完成的临时文件"],
    diagnostic_logs: ["Diagnostic logs", "诊断日志"],
    history_database: ["History database", "历史数据库"],
    database_sidecars: ["Database sidecars", "数据库辅助文件"],
    archive_index: ["Archive catalogue", "归档目录索引"],
    configuration_and_credentials: ["Configuration & credentials", "设置与凭据"],
    unclassified: ["Unclassified files", "未分类文件"],
  };
  return labels[category]?.[locale === "en" ? 0 : 1] ?? category;
}

function storageNoteText(locale: "en" | "zh-CN", note: string): string {
  const labels: Record<string, [string, string]> = {
    active_sqlite_backend: ["Clears durable history and experiment records from the active SQLite backend; a live consciousness may later write a new checkpoint.", "清空当前 SQLite 后端中的持久化历史与实验记录；运行中的意识之后仍可能写入新的检查点。"],
    active_mysql_backend: ["Clears durable history and experiment records from the active MySQL backend; a live consciousness may later write a new checkpoint.", "清空当前 MySQL 后端中的持久化历史与实验记录；运行中的意识之后仍可能写入新的检查点。"],
    active_d1_backend: ["Clears durable history and experiment records from the active D1 backend; a live consciousness may later write a new checkpoint.", "清空当前 D1 后端中的持久化历史与实验记录；运行中的意识之后仍可能写入新的检查点。"],
    active_file_backend: ["The active file backend is protected. Switch to a database backend before removing it.", "当前文件后端正在使用，已受保护。请先切换到数据库后端再移除。"],
    legacy_file_backend_unused: ["Not selected by the current backend. Removing it does not change current SQLite history.", "当前后端未使用它；删除不会改变正在使用的 SQLite 历史。"],
    portable_model_package: ["Portable .tmind snapshot, portrait, or model package. Deletion is irreversible.", "便携的 .tmind 快照、遗照或模型包。删除不可恢复。"],
    stale_incomplete_archive: ["An incomplete archive write older than one minute. It is safe to remove after review.", "超过一分钟的未完成存档写入；确认后可安全移除。"],
    recent_write_in_progress: ["Recent temporary write; protected to avoid racing a snapshot operation.", "近期临时写入，已保护以避免与快照操作竞争。"],
    diagnostic_output: ["Diagnostic output only; it does not contain consciousness state.", "仅为诊断输出，不包含意识状态。"],
    managed_by_current_persistence: ["Managed by the active persistence backend. Use the logical durable-records item above instead of deleting this file.", "由当前持久化后端管理。请使用上方的“当前持久化记录”逻辑项，而不要直接删除此文件。"],
    active_database_sidecar: ["Active database sidecar; protected while the service may be using it.", "活动数据库辅助文件；服务可能正在使用，已保护。"],
    rebuildable_archive_catalogue: ["The catalogue can be rebuilt from retained .tmind packages. Use the rebuild button rather than deleting it directly.", "该目录可从保留的 .tmind 包重建。请使用“重建索引”，而不要直接删除。"],
    configuration_or_secret: ["Protected local settings or encrypted credentials. It is intentionally excluded from ordinary cleanup.", "受保护的本地设置或加密凭据，已刻意排除在普通清理之外。"],
    unclassified_file: ["Unknown file type; protected until it is explicitly understood.", "未知文件类型；在明确用途前保持受保护状态。"],
  };
  return labels[note]?.[locale === "en" ? 0 : 1] ?? note;
}

function storageActionText(locale: "en" | "zh-CN", action: string): string {
  const labels: Record<string, [string, string]> = {
    delete_file: ["Selected file can be deleted", "可删除的已选文件"],
    clear_records: ["Clear records", "清空记录"],
    protected: ["Protected", "受保护"],
    managed_history: ["Managed", "受管理"],
    rebuild_index: ["Rebuildable", "可重建"],
  };
  return labels[action]?.[locale === "en" ? 0 : 1] ?? action;
}

function storageBytes(value: number, locale: "en" | "zh-CN"): string {
  if (value < 1024) return `${value} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let amount = value / 1024;
  let index = 0;
  while (amount >= 1024 && index < units.length - 1) { amount /= 1024; index += 1; }
  return `${amount.toLocaleString(locale === "en" ? "en-US" : "zh-CN", { maximumFractionDigits: amount >= 100 ? 0 : 2 })} ${units[index]}`;
}

export function StorageCleanupManager() {
  const locale = useLocale();
  const t = useT();
  const [scan, setScan] = useState<StorageScan | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [confirmation, setConfirmation] = useState("");
  const [busy, setBusy] = useState(false);
  const [operation, setOperation] = useState("");
  const [message, setMessage] = useState("");

  const copy = locale === "en" ? {
    title: "Storage & cleanup",
    subtitle: "Scan local ThreeMind artifacts before selecting any irreversible cleanup. The scan reads metadata only; it never opens model packages or legacy JSON history.",
    scanning: "Scanning local storage…",
    cleaning: "Cleaning selected storage items…",
    refreshed: "Storage inventory refreshed.",
    cleaned: (files: number, records: number) => `Cleanup completed: ${files} file(s) removed, ${records} durable-record set(s) cleared.`,
    rebuild: "Rebuild archive catalogue",
    rebuilding: "Archive catalogue rebuild has been scheduled.",
    selected: "selected",
    selectGroup: "Select removable in this group",
    clearSelection: "Clear selection",
    protected: "Protected items cannot be selected here.",
    confirmation: "Type DELETE to confirm the selected cleanup",
    delete: "Delete selected items",
    total: "Local data scanned",
    files: "files",
    pendingWrites: "Archive writes are pending; selected .tmind packages will be skipped until they finish.",
    liveNote: "Clearing durable records never changes the live consciousness graph. A running consciousness may later create a fresh history checkpoint.",
    none: "No local storage items were found.",
    item: "Item",
    size: "Size",
    modified: "Modified",
    safety: "Safety / action",
    description: "Description",
  } : {
    title: "存储与清理",
    subtitle: "先扫描本地 ThreeMind 工件，再选择需要清理的内容。扫描只读取元数据，不会打开模型包或旧版 JSON 历史。",
    scanning: "正在扫描本地存储…",
    cleaning: "正在清理所选存储项…",
    refreshed: "存储清单已刷新。",
    cleaned: (files: number, records: number) => `清理完成：已删除 ${files} 个文件，已清空 ${records} 组持久化记录。`,
    rebuild: "重建归档目录索引",
    rebuilding: "已安排归档目录索引重建。",
    selected: "已选择",
    selectGroup: "选择本组可清理项",
    clearSelection: "清空选择",
    protected: "受保护项目不能在这里被选中。",
    confirmation: "输入 DELETE 以确认所选清理操作",
    delete: "删除所选项目",
    total: "已扫描本地数据",
    files: "个文件",
    pendingWrites: "存在待完成的归档写入；所选 .tmind 包会在写入完成前被跳过。",
    liveNote: "清空持久化记录不会改变内存中的实时意识图；运行中的意识之后仍可能写入新的历史检查点。",
    none: "没有发现本地存储项目。",
    item: "项目",
    size: "大小",
    modified: "修改时间",
    safety: "安全性／操作",
    description: "说明",
  };

  const load = async (announce = false) => {
    setBusy(true);
    setOperation(copy.scanning);
    try {
      const result = await api<StorageScan>("/api/storage/scan");
      setScan(result);
      setSelected((current) => current.filter((id) => result.items.some((item) => item.id === id && item.selectable)));
      if (announce) setMessage(copy.refreshed);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : (locale === "en" ? "Storage scan failed." : "存储扫描失败。"));
    } finally {
      setOperation("");
      setBusy(false);
    }
  };

  useEffect(() => { void load(); }, [locale]);

  const selectedItems = useMemo(() => scan?.items.filter((item) => selected.includes(item.id)) ?? [], [scan, selected]);
  const groups = useMemo(() => {
    const buckets = new Map<string, StorageItem[]>();
    for (const item of scan?.items ?? []) buckets.set(item.category, [...(buckets.get(item.category) ?? []), item]);
    return [...buckets.entries()].sort(([left], [right]) => {
      const leftIndex = storageCategoryOrder.indexOf(left);
      const rightIndex = storageCategoryOrder.indexOf(right);
      return (leftIndex < 0 ? 999 : leftIndex) - (rightIndex < 0 ? 999 : rightIndex);
    });
  }, [scan]);

  const toggle = (item: StorageItem, checked: boolean) => {
    if (!item.selectable || busy) return;
    setSelected((current) => checked ? [...new Set([...current, item.id])] : current.filter((id) => id !== item.id));
  };

  const toggleGroup = (items: StorageItem[], checked: boolean) => {
    if (busy) return;
    const ids = items.filter((item) => item.selectable).map((item) => item.id);
    setSelected((current) => checked ? [...new Set([...current, ...ids])] : current.filter((id) => !ids.includes(id)));
  };

  const cleanup = async () => {
    if (!selected.length || confirmation !== "DELETE") return;
    setBusy(true);
    setOperation(copy.cleaning);
    setMessage("");
    try {
      const result = await api<{ deleted: string[]; cleared: string[]; skipped: Array<{ id: string; reason: string }>; scan: StorageScan }>("/api/storage/cleanup", {
        method: "POST", headers: jsonHeaders, body: JSON.stringify({ item_ids: selected, confirmation }),
      });
      setScan(result.scan);
      setSelected([]);
      setConfirmation("");
      const suffix = result.skipped.length ? ` ${locale === "en" ? `${result.skipped.length} item(s) skipped.` : `另有 ${result.skipped.length} 项被跳过。`}` : "";
      setMessage(`${copy.cleaned(result.deleted.length, result.cleared.length)}${suffix}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : (locale === "en" ? "Storage cleanup failed." : "存储清理失败。"));
    } finally {
      setOperation("");
      setBusy(false);
    }
  };

  const rebuildIndex = async () => {
    setBusy(true);
    setOperation(locale === "en" ? "Scheduling archive catalogue rebuild…" : "正在安排归档目录索引重建…");
    try {
      await api("/api/archive-index/reindex?force=true", { method: "POST" });
      setMessage(copy.rebuilding);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : (locale === "en" ? "Unable to rebuild archive catalogue." : "无法重建归档目录索引。"));
    } finally {
      setOperation("");
      setBusy(false);
    }
  };

  return <section className="management-page storage-cleanup-page">
    <header>
      <div><h2>{copy.title}</h2><p>{copy.subtitle}</p></div>
      <div className="page-actions"><button type="button" disabled={busy} onClick={() => void rebuildIndex()}>{copy.rebuild}</button><button type="button" disabled={busy} onClick={() => void load(true)}>{t("refresh")}</button></div>
    </header>
    {operation && <div className="management-message is-pending" role="status"><span className="ui-spinner" aria-hidden="true" />{operation}</div>}
    {message && <div className="management-message">{message}</div>}
    {scan && <>
      <section className="storage-summary-grid" aria-label={copy.total}>
        <article><span>{copy.total}</span><strong>{storageBytes(scan.total_bytes, locale)}</strong></article>
        <article><span>{copy.files}</span><strong>{scan.items.filter((item) => item.id.startsWith("file:")).length}</strong></article>
        <article><span>{copy.selected}</span><strong>{selected.length}</strong></article>
      </section>
      <p className="storage-safety-note">{copy.liveNote}</p>
      {(Number(scan.archive_writer?.queued ?? 0) > 0 || Number(scan.archive_writer?.pending ?? 0) > 0) && <p className="storage-safety-note is-warning">{copy.pendingWrites}</p>}
      <div className="storage-cleanup-toolbar">
        <div><strong>{selectedItems.length} {copy.selected}</strong><span>{selectedItems.length ? selectedItems.map((item) => item.name).join(" · ") : copy.protected}</span></div>
        <button type="button" disabled={busy || !selected.length} onClick={() => setSelected([])}>{copy.clearSelection}</button>
      </div>
      {groups.map(([category, items]) => {
        const selectable = items.filter((item) => item.selectable);
        const allSelected = selectable.length > 0 && selectable.every((item) => selected.includes(item.id));
        return <section className="storage-category" key={category}>
          <div className="storage-category-heading"><div><h3>{storageCategoryText(locale, category)}</h3><span>{items.length} {copy.files} · {storageBytes(items.reduce((sum, item) => sum + item.bytes, 0), locale)}</span></div>{selectable.length > 0 && <label className="storage-group-select"><input type="checkbox" disabled={busy} checked={allSelected} onChange={(event) => toggleGroup(items, event.target.checked)} /> {copy.selectGroup}</label>}</div>
          <div className="record-table-wrap"><table className="record-table storage-table"><thead><tr><th aria-label={copy.selected} /><th>{copy.item}</th><th>{copy.size}</th><th>{copy.modified}</th><th>{copy.safety}</th><th>{copy.description}</th></tr></thead><tbody>{items.map((item) => <tr className={item.selectable ? "" : "storage-protected-row"} key={item.id}><td><input type="checkbox" aria-label={`${copy.selected}: ${item.name}`} disabled={busy || !item.selectable} checked={selected.includes(item.id)} onChange={(event) => toggle(item, event.target.checked)} /></td><td><strong>{item.id === "persistence:records" ? (locale === "en" ? "Current durable history records" : "当前持久化历史记录") : item.name}</strong><small>{item.id}</small></td><td>{item.bytes ? storageBytes(item.bytes, locale) : "—"}</td><td>{item.modified_at ? new Date(item.modified_at * 1000).toLocaleString(locale === "en" ? "en-US" : "zh-CN") : "—"}</td><td><span className={`storage-action storage-action-${item.action}`}>{storageActionText(locale, item.action)}</span></td><td>{storageNoteText(locale, item.note)}</td></tr>)}</tbody></table></div>
        </section>;
      })}
      {!scan.items.length && <div className="empty-state"><strong>{copy.none}</strong></div>}
      <section className="storage-confirmation-panel">
        <div><h3>{locale === "en" ? "Confirm selected cleanup" : "确认所选清理"}</h3><p>{copy.confirmation}</p></div>
        <label className="settings-field"><span className="sr-only">{copy.confirmation}</span><input value={confirmation} disabled={busy || !selected.length} onChange={(event) => setConfirmation(event.target.value)} placeholder="DELETE" /></label>
        <button className="danger" type="button" disabled={busy || !selected.length || confirmation !== "DELETE"} onClick={() => void cleanup()}>{copy.delete}</button>
      </section>
    </>}
  </section>;
}
