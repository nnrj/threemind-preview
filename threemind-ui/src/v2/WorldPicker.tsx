import { useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import { t } from "./i18n";
import { Button, ErrorBox, Field, Modal } from "./ui";
import { WorldEditor, type WorldEditorHandle } from "./WorldEditor";

export default function WorldPicker({
  project,
  value,
  onChange,
  readOnly = false,
}: {
  project: string;
  value: any;
  onChange: (v: any) => void;
  readOnly?: boolean;
}) {
  const [open, setOpen] = useState(false),
    [q, setQ] = useState(""),
    [offset, setOffset] = useState(0),
    [chosen, setChosen] = useState("");
  const [error, setError] = useState<unknown>(null),
    [busy, setBusy] = useState(false);
  const editor = useRef<WorldEditorHandle>(null);
  const root = `/projects/${project}/worlds`;
  const library = useQuery({
    queryKey: ["world-picker", project, q, offset],
    queryFn: () =>
      api<any>(`${root}?q=${encodeURIComponent(q)}&offset=${offset}`),
    enabled: !readOnly,
  });
  async function choose(id: string) {
    if (!id) return;
    setBusy(true);
    setError(null);
    try {
      const row = await api<any>(`${root}/${id}`);
      onChange(row.protocol);
      setChosen(id);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="world-picker">
      <p>{value?.label || t("尚未配置世界")}</p>
      {!readOnly && (
        <>
          <Field label={t("搜索已保存世界")}>
            <input
              value={q}
              onChange={(e) => {
                setQ(e.target.value);
                setOffset(0);
              }}
            />
          </Field>
          <Field label={t("从世界库选择")}>
            <select
              value={chosen}
              disabled={busy}
              onChange={(e) => choose(e.target.value)}
            >
              <option value="">{t("自定义协议／请选择")}</option>
              {chosen &&
                !library.data?.rows.some((r: any) => r.id === chosen) && (
                  <option value={chosen}>{value?.label}</option>
                )}
              {library.data?.rows.map((r: any) => (
                <option key={r.id} value={r.id}>
                  {r.title} · r{r.revision}
                </option>
              ))}
            </select>
          </Field>
          {(offset > 0 || library.data?.more) && (
            <div className="query-controls">
              <Button
                type="button"
                disabled={!offset}
                onClick={() => setOffset(offset - 30)}
              >
                {t("上一页")}
              </Button>
              <Button
                type="button"
                disabled={!library.data?.more}
                onClick={() => setOffset(offset + 30)}
              >
                {t("下一页")}
              </Button>
            </div>
          )}
        </>
      )}
      <Button
        type="button"
        disabled={readOnly && !value}
        onClick={() => setOpen(true)}
      >
        {readOnly ? t("查看世界协议") : t("图形配置世界与躯体")}
      </Button>
      <ErrorBox error={error ?? library.error} />
      <Modal
        open={open}
        onOpenChange={setOpen}
        wide
        title={t("世界与躯体配置")}
      >
        {open && (
          <WorldEditor
            ref={editor}
            project={project}
            initial={value}
            readOnly={readOnly}
          />
        )}
        <div className="modal-actions">
          <Button type="button" onClick={() => setOpen(false)}>
            {t("关闭")}
          </Button>
          {!readOnly && (
            <Button
              type="button"
              variant="primary"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  const v = await editor.current?.validate();
                  if (v) {
                    onChange(v);
                    setChosen("");
                    setOpen(false);
                  }
                } finally {
                  setBusy(false);
                }
              }}
            >
              {t("采用世界配置")}
            </Button>
          )}
        </div>
      </Modal>
    </div>
  );
}
