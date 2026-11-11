import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, post, projectPath } from "./api";
import "./kernelConfiguration.css";
import { can } from "./access";
import { t } from "./i18n";
import { Button, ErrorBox, Field, Loading, Modal, useWorkspace } from "./ui";
import {
  ConfigurationEditor,
  type Catalogue,
  type ConfigurationHandle,
} from "./configuration";

import { KernelSelector } from "./kernelSelector";
export { KernelSelector, kernelLabel } from "./kernelSelector";

type Spec = Record<string, any>;
export type KernelConfigurationHandle = {
  validate: () => Promise<{
    spec: Spec;
    creationSource: Spec;
    execution?: { backend: string };
  } | null>;
};

/** Kernel is the owner of a parameter draft. Templates never select another kernel. */
export const KernelConfiguration = forwardRef<
  KernelConfigurationHandle,
  {
    catalogue: Catalogue;
    initialKernel?: string;
    project?: string;
    readOnly?: boolean;
    worldProtocol?: any;
    robotProtocol?: any;
  }
>(function KernelConfiguration(
  {
    catalogue,
    initialKernel,
    project,
    readOnly = false,
    worldProtocol,
    robotProtocol,
  },
  ref,
) {
  const { user, projects } = useWorkspace(),
    client = useQueryClient();
  const editor = useRef<ConfigurationHandle>(null);
  const [kernel, setKernel] = useState(
    initialKernel || catalogue.defaults.kernel_id,
  );
  const [draft, setDraft] = useState<Spec | null>(null);
  const [source, setSource] = useState<Spec>({});
  const [selectedTemplate, setSelectedTemplate] = useState("system");
  const [dirty, setDirty] = useState(false);
  const [pendingChange, setPendingChange] = useState<{
    kind: "kernel" | "template";
    value: string;
  } | null>(null);
  const [notice, setNotice] = useState("");
  const [templateName, setTemplateName] = useState<string | null>(null);
  const [presetOpen, setPresetOpen] = useState(false);
  const [presetProject, setPresetProject] = useState("");
  const [appliedPreset, setAppliedPreset] = useState<{
    id: string;
    name: string;
  } | null>(null);
  const generation = useRef(0);
  const defaults = useQuery({
    queryKey: ["kernel-creation-defaults", kernel],
    queryFn: () =>
      api(`/configuration/defaults?kernel_id=${encodeURIComponent(kernel)}`),
    refetchOnWindowFocus: false,
    gcTime: 0,
  });
  const templates = useQuery({
    queryKey: ["configuration-templates", kernel],
    queryFn: () =>
      api(`/configuration/templates?kernel_id=${encodeURIComponent(kernel)}`),
    refetchOnWindowFocus: false,
  });
  const projectPreset = useQuery({
    queryKey: ["creation-project-preset", presetProject],
    queryFn: () => api(`${projectPath(presetProject)}/configuration/defaults`),
    enabled: presetOpen && !!presetProject,
    refetchOnWindowFocus: false,
  });
  const rows: any[] = Array.isArray(templates.data)
    ? templates.data
    : [...(templates.data?.items || []), ...(templates.data?.builtins || [])];
  const matchingRows = rows.filter(
    (row) => (row.kernel_id || row.spec?.kernel_id) === kernel,
  );
  const bound = (spec: Spec) => ({
    ...spec,
    ...(robotProtocol
      ? { environment: "robot", robot_protocol: robotProtocol }
      : worldProtocol
        ? { environment: "world", world_protocol: worldProtocol }
        : {}),
  });
  const defaultSource = (value: any) => ({
    kind: value.source === "factory" ? "factory" : "system",
    kernel_id: kernel,
    revision: value.revision,
  });
  useEffect(() => {
    if (!draft && defaults.data?.spec.kernel_id === kernel) {
      setDraft(bound(defaults.data.spec));
      setSource(defaultSource(defaults.data));
    }
  }, [kernel, defaults.data, draft]);
  const apply = useMutation({
    mutationFn: async ({ value, at }: { value: string; at: number }) => {
      if (value === "system")
        return {
          value,
          at,
          data: await api(
            `/configuration/defaults?kernel_id=${encodeURIComponent(kernel)}`,
          ),
        };
      if (value.startsWith("project-preset:")) {
        const identity = value.slice("project-preset:".length);
        const data = projectPreset.data;
        if (
          !data ||
          identity !== presetProject ||
          data.spec.kernel_id !== kernel
        )
          throw new Error(t("项目预设与当前内核不同，不能作为此内核的模板。"));
        return {
          value,
          at,
          data: {
            ...data,
            source: {
              kind: "project-preset",
              project_id: identity,
              revision: data.revision,
            },
          },
        };
      }
      const row = matchingRows.find((row) => row.id === value);
      if (!row) throw new Error(t("所选模板不属于当前内核。"));
      if (row.spec && row.spec.kernel_id !== kernel)
        throw new Error(t("所选模板不属于当前内核。"));
      return {
        value,
        at,
        data: row.spec ? row : await api(`/configuration/templates/${value}`),
      };
    },
    onSuccess: ({ value, at, data }) => {
      if (at !== generation.current) return;
      if (data.spec.kernel_id !== kernel) return;
      const next = bound(data.spec);
      setDraft(next);
      editor.current?.reset(next);
      setSource(
        value === "system"
          ? defaultSource(data)
          : ["builtin-template", "project-preset"].includes(data.source?.kind)
            ? data.source
            : { kind: "template", id: data.id, revision: data.revision },
      );
      setSelectedTemplate(value);
      if (value.startsWith("project-preset:")) {
        setAppliedPreset({
          id: presetProject,
          name:
            projects.find((row) => row.id === presetProject)?.name ||
            presetProject,
        });
        setPresetOpen(false);
      } else setAppliedPreset(null);
      setDirty(false);
      setNotice(t("模板参数已载入；可以继续调整，已有意识不会改变。"));
    },
  });
  function commitChange(change: {
    kind: "kernel" | "template";
    value: string;
  }) {
    setPendingChange(null);
    setNotice("");
    generation.current += 1;
    if (change.kind === "kernel") {
      setKernel(change.value);
      setDraft(null);
      setSource({});
      setSelectedTemplate("system");
      setAppliedPreset(null);
      setDirty(false);
    } else apply.mutate({ value: change.value, at: generation.current });
  }
  function requestChange(change: {
    kind: "kernel" | "template";
    value: string;
  }) {
    if (dirty) setPendingChange(change);
    else commitChange(change);
  }
  const saveTemplate = useMutation({
    mutationFn: async () => {
      const spec = await editor.current?.validate();
      if (!spec) return null;
      return post("/configuration/templates", {
        name: templateName?.trim(),
        spec,
      });
    },
    onSuccess: (result) => {
      if (!result) return;
      client.invalidateQueries({ queryKey: ["configuration-templates"] });
      client.invalidateQueries({ queryKey: ["system-templates"] });
      setTemplateName(null);
      setNotice(t("当前参数已保存为模板，不包含个体状态或学习权重。"));
    },
  });
  useImperativeHandle(ref, () => ({
    async validate() {
      if (!draft || apply.isPending || pendingChange) return null;
      const spec = await editor.current?.validate();
      if (!spec || spec.kernel_id !== kernel) return null;
      const descriptor = catalogue.kernels?.find(
        (row) => row.kernel_id === kernel,
      );
      return {
        spec,
        creationSource: source,
        ...(descriptor?.backends?.length === 1
          ? { execution: { backend: descriptor.backends[0] } }
          : {}),
      };
    },
  }));
  return (
    <section className="kernel-configuration">
      <KernelSelector
        catalogue={catalogue}
        value={kernel}
        onChange={(value) => requestChange({ kind: "kernel", value })}
        disabled={readOnly || apply.isPending}
      />
      <section className="kernel-parameters" aria-label={t("内核参数")}>
        <Field label={t("配置模板")}>
          <select
            aria-label={t("配置模板")}
            value={selectedTemplate}
            disabled={readOnly || !draft || apply.isPending}
            onChange={(event) =>
              requestChange({ kind: "template", value: event.target.value })
            }
          >
            <option value="system">{t("系统默认模板")}</option>
            {appliedPreset && (
              <option value={`project-preset:${appliedPreset.id}`}>
                {t("项目预设")} · {appliedPreset.name}
              </option>
            )}
            {matchingRows.map((row) => (
              <option key={row.id} value={row.id}>
                {row.name || row.title} · v{row.revision}
              </option>
            ))}
          </select>
        </Field>
        {can(user, "projects.read") && (
          <Button
            type="button"
            disabled={readOnly || !draft || apply.isPending}
            onClick={() => setPresetOpen(true)}
          >
            {t("采用项目预设")}
          </Button>
        )}
        <p className="footnote">
          {dirty
            ? t("已基于所选模板修改参数。")
            : t("模板只设置当前内核的参数，可以继续手动调整。")}
        </p>
        <ErrorBox error={defaults.error || templates.error || apply.error} />
        {!draft ? (
          <Loading />
        ) : (
          <ConfigurationEditor
            key={kernel}
            ref={editor}
            initial={draft}
            catalogue={catalogue}
            project={project}
            managedKernel
            readOnly={readOnly || apply.isPending}
            onDirty={() => setDirty(true)}
          />
        )}
        {can(user, "system.write") && (
          <Button
            type="button"
            disabled={readOnly || !draft || apply.isPending}
            onClick={() => setTemplateName("")}
          >
            {t("将当前参数保存为模板")}
          </Button>
        )}
        {notice && <p role="status">{notice}</p>}
      </section>
      <Modal
        open={!!pendingChange}
        onOpenChange={(open) => !open && setPendingChange(null)}
        title={t("替换当前参数？")}
      >
        <p>
          {t(
            "当前参数已有修改。采用新内核或模板将替换这些修改，取消会保留当前草稿。",
          )}
        </p>
        <Button type="button" onClick={() => setPendingChange(null)}>
          {t("取消")}
        </Button>
        <Button
          type="button"
          variant="primary"
          onClick={() => pendingChange && commitChange(pendingChange)}
        >
          {t("替换参数")}
        </Button>
      </Modal>
      <Modal
        open={presetOpen}
        onOpenChange={setPresetOpen}
        title={t("采用项目预设")}
      >
        <Field label={t("预设来源项目")}>
          <select
            aria-label={t("预设来源项目")}
            value={presetProject}
            onChange={(event) => setPresetProject(event.target.value)}
          >
            <option value="">{t("请选择归属项目")}</option>
            {projects.map((row) => (
              <option key={row.id} value={row.id}>
                {row.name}
              </option>
            ))}
          </select>
        </Field>
        <ErrorBox error={projectPreset.error || apply.error} />
        {projectPreset.data && (
          <p className="footnote">
            <code>{projectPreset.data.spec.kernel_id}</code> · v
            {projectPreset.data.revision}
          </p>
        )}
        {projectPreset.data && projectPreset.data.spec.kernel_id !== kernel && (
          <p role="alert">
            {t("项目预设与当前内核不同，不能作为此内核的模板。")}
          </p>
        )}
        <Button type="button" onClick={() => setPresetOpen(false)}>
          {t("取消")}
        </Button>
        <Button
          type="button"
          variant="primary"
          disabled={
            !projectPreset.data ||
            projectPreset.data.spec.kernel_id !== kernel ||
            apply.isPending
          }
          onClick={() =>
            requestChange({
              kind: "template",
              value: `project-preset:${presetProject}`,
            })
          }
        >
          {t("采用预设参数")}
        </Button>
      </Modal>
      <Modal
        open={templateName !== null}
        onOpenChange={(open) => !open && setTemplateName(null)}
        title={t("将当前参数保存为模板")}
      >
        <Field label={t("模板名称")}>
          <input
            value={templateName || ""}
            maxLength={120}
            onChange={(event) => setTemplateName(event.target.value)}
          />
        </Field>
        <ErrorBox error={saveTemplate.error} />
        <Button type="button" onClick={() => setTemplateName(null)}>
          {t("取消")}
        </Button>
        <Button
          type="button"
          variant="primary"
          disabled={!templateName?.trim() || saveTemplate.isPending}
          onClick={() => saveTemplate.mutate()}
        >
          {t("保存模板")}
        </Button>
      </Modal>
    </section>
  );
});
