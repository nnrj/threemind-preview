import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, RotateCcw } from "lucide-react";
import { KernelSelector, kernelLabel } from "./kernelConfiguration";
import { api, post } from "./api";
import {
  ConfigurationEditor,
  useCatalogue,
  type ConfigurationHandle,
} from "./configuration";
import { useAccess } from "./access";
import { Button, Empty, ErrorBox, Field, Loading, Modal } from "./ui";
import { t } from "./i18n";

type Template = {
  id: string;
  name: string;
  revision: number;
  spec: Record<string, any>;
};

export default function SystemConfiguration({
  templates = false,
}: {
  templates?: boolean;
}) {
  return templates ? <Templates /> : <Defaults />;
}

function Defaults() {
  const catalogue = useCatalogue(),
    allowed = useAccess(),
    client = useQueryClient();
  const editor = useRef<ConfigurationHandle>(null);
  const [kernel, setKernel] = useState("");
  const [message, setMessage] = useState("");
  const [dirty, setDirty] = useState(false);
  const query = useQuery({
    queryKey: ["system-defaults", kernel],
    queryFn: () =>
      api(
        `/configuration/defaults${kernel ? `?kernel_id=${encodeURIComponent(kernel)}` : ""}`,
      ),
    enabled: allowed("system.read"),
    refetchOnWindowFocus: false,
  });
  const save = useMutation({
    mutationFn: async () => {
      const spec = await editor.current?.validate();
      if (!spec) return null;
      return api("/configuration/defaults", {
        method: "PUT",
        body: JSON.stringify({ spec, expected_revision: query.data.revision }),
      });
    },
    onSuccess: (value) => {
      if (!value) return;
      client.invalidateQueries({ queryKey: ["system-defaults"] });
      client.invalidateQueries({ queryKey: ["new-run-defaults"] });
      client.invalidateQueries({ queryKey: ["kernel-creation-defaults"] });
      setDirty(false);
      setMessage(t("系统默认配置已保存，仅用于以后新建的意识。"));
    },
  });
  if (!allowed("system.read"))
    return (
      <Empty
        title={t("没有此功能的访问权限")}
        detail={t("请联系管理员检查角色权限。")}
      />
    );
  return (
    <section className="panel settings-panel">
      <div className="panel-heading">
        <div>
          <h2>{t("新建意识的系统默认配置")}</h2>
          <p>
            {t(
              "在选择项目之前配置新意识。已有意识始终使用其保存的配置；项目历史配置在项目详情中查看。",
            )}
          </p>
        </div>
      </div>
      {catalogue.data && (
        <KernelSelector
          catalogue={catalogue.data}
          value={kernel || catalogue.data.defaults.kernel_id}
          onChange={(value) => {
            if (
              dirty &&
              !window.confirm(
                t("当前参数已有修改。切换内核将替换这些修改，是否继续？"),
              )
            )
              return;
            setKernel(value);
            setMessage("");
            setDirty(false);
          }}
          disabled={save.isPending}
        />
      )}
      <ErrorBox error={query.error || catalogue.error || save.error} />
      {query.isPending || catalogue.isPending ? (
        <Loading />
      ) : (
        query.data &&
        catalogue.data && (
          <form
            noValidate
            onSubmit={(event) => {
              event.preventDefault();
              save.mutate();
            }}
          >
            <p className="footnote">
              {t("配置来源")}：
              {query.data.source === "factory"
                ? t("内核工厂默认")
                : t("系统保存配置")}{" "}
              · v{query.data.revision}
            </p>
            <ConfigurationEditor
              key={`${kernel}:${query.data.revision}`}
              ref={editor}
              initial={query.data.spec}
              catalogue={catalogue.data}
              project=""
              readOnly={!allowed("system.write") || save.isPending}
              managedKernel
              onDirty={() => {
                setMessage("");
                setDirty(true);
              }}
            />
            {message && <p role="status">{message}</p>}
            {allowed("system.write") && (
              <div className="form-actions">
                <Button
                  type="button"
                  onClick={() => {
                    editor.current?.reset(
                      query.data.factory ?? {
                        ...catalogue.data!.defaults,
                        kernel_id: query.data.spec.kernel_id,
                        config:
                          catalogue.data!.kernel_defaults?.[
                            query.data.spec.kernel_id
                          ] ?? catalogue.data!.defaults.config,
                      },
                    );
                    setDirty(true);
                    setMessage(t("已载入内核默认值，点击保存后生效。"));
                  }}
                >
                  <RotateCcw size={14} />
                  {t("恢复内核默认值")}
                </Button>
                <Button variant="primary" disabled={save.isPending}>
                  {t("保存系统默认配置")}
                </Button>
              </div>
            )}
          </form>
        )
      )}
    </section>
  );
}

function Templates() {
  const allowed = useAccess(),
    client = useQueryClient();
  const catalogue = useCatalogue();
  const [selected, setSelected] = useState<string | null>(null);
  const query = useQuery({
    queryKey: ["system-templates"],
    queryFn: () => api("/configuration/templates"),
    enabled: allowed("system.read"),
  });
  const rows: Template[] = Array.isArray(query.data)
    ? query.data
    : (query.data?.items ?? []);
  const changed = () => {
    client.invalidateQueries({ queryKey: ["system-templates"] });
    setSelected(null);
  };
  return (
    <section className="panel settings-panel">
      <div className="panel-heading">
        <div>
          <h2>{t("创建配置模板")}</h2>
          <p>
            {t(
              "模板保存内核、感官外设、身体和运行协议的配置，不包含个体状态或学习权重。",
            )}
          </p>
        </div>
        {allowed("system.write") && (
          <Button
            variant="primary"
            onClick={() => setSelected("new")}
            disabled={!catalogue.data}
          >
            <Plus size={16} />
            {t("新建模板")}
          </Button>
        )}
      </div>
      <ErrorBox error={query.error || catalogue.error} />
      {query.isPending ? (
        <Loading />
      ) : rows.length ? (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>{t("名称")}</th>
                <th>{t("内核版本")}</th>
                <th>{t("版本")}</th>
                <th>{t("操作")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>{row.name}</td>
                  <td>{kernelLabel({ kernel_id: row.spec.kernel_id })}</td>
                  <td>v{row.revision}</td>
                  <td>
                    <Button variant="small" onClick={() => setSelected(row.id)}>
                      {allowed("system.write") ? t("查看与编辑") : t("查看")}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <Empty
          title={t("尚无创建模板")}
          detail={t(
            "可以直接使用系统默认配置创建意识，也可保存常用配置为模板。",
          )}
        />
      )}
      {selected && catalogue.data && (
        <TemplateEditor
          key={selected}
          identity={selected}
          onClose={() => setSelected(null)}
          onSaved={changed}
        />
      )}
    </section>
  );
}

function TemplateEditor({
  identity,
  onClose,
  onSaved,
}: {
  identity: string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const allowed = useAccess(),
    catalogue = useCatalogue(),
    editor = useRef<ConfigurationHandle>(null);
  const [name, setName] = useState<string | null>(null);
  const [kernel, setKernel] = useState("");
  const [dirty, setDirty] = useState(false);
  const query = useQuery<Template>({
    queryKey: ["system-template", identity],
    queryFn: () => api(`/configuration/templates/${identity}`),
    enabled: identity !== "new",
  });
  const selectedKernel =
    identity === "new"
      ? kernel || catalogue.data?.defaults.kernel_id
      : query.data?.spec.kernel_id;
  const defaults = useQuery({
    queryKey: ["template-defaults", selectedKernel],
    queryFn: () =>
      api(
        `/configuration/defaults?kernel_id=${encodeURIComponent(selectedKernel)}`,
      ),
    enabled: identity === "new" && !!selectedKernel,
    refetchOnWindowFocus: false,
  });
  const initial = identity === "new" ? defaults.data?.spec : query.data?.spec;
  const save = useMutation({
    mutationFn: async () => {
      const spec = await editor.current?.validate();
      if (!spec) return null;
      return identity === "new"
        ? post("/configuration/templates", { name: name ?? "", spec })
        : api(`/configuration/templates/${identity}`, {
            method: "PUT",
            body: JSON.stringify({
              name: name ?? query.data!.name,
              spec,
              expected_revision: query.data!.revision,
            }),
          });
    },
    onSuccess: (result) => result && onSaved(),
  });
  return (
    <Modal
      open
      wide
      title={t("创建配置模板")}
      onOpenChange={(open) => !open && onClose()}
    >
      <ErrorBox error={query.error || defaults.error || save.error} />
      {!initial || !catalogue.data ? (
        query.error || defaults.error ? null : (
          <Loading />
        )
      ) : (
        <form
          noValidate
          onSubmit={(event) => {
            event.preventDefault();
            save.mutate();
          }}
        >
          <Field label={t("模板名称")}>
            <input
              required
              maxLength={120}
              value={name ?? query.data?.name ?? ""}
              disabled={!allowed("system.write")}
              onChange={(event) => setName(event.target.value)}
            />
          </Field>
          <KernelSelector
            catalogue={catalogue.data}
            value={selectedKernel}
            disabled={
              identity !== "new" || !allowed("system.write") || save.isPending
            }
            onChange={(value) => {
              if (
                dirty &&
                !window.confirm(
                  t("当前参数已有修改。切换内核将替换这些修改，是否继续？"),
                )
              )
                return;
              setKernel(value);
              setDirty(false);
            }}
          />
          <ConfigurationEditor
            key={selectedKernel}
            ref={editor}
            managedKernel
            onDirty={() => setDirty(true)}
            initial={initial as any}
            catalogue={catalogue.data}
            project=""
            readOnly={!allowed("system.write") || save.isPending}
          />
          <div className="form-actions">
            <Button type="button" onClick={onClose}>
              {t("关闭")}
            </Button>
            {allowed("system.write") && (
              <Button
                variant="primary"
                disabled={save.isPending || !(name ?? query.data?.name)?.trim()}
              >
                {t("保存模板")}
              </Button>
            )}
          </div>
        </form>
      )}
    </Modal>
  );
}

export function SystemDefaults() {
  return <Defaults />;
}
export function ConfigurationTemplates() {
  return <Templates />;
}
