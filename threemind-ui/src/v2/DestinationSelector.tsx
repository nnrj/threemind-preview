import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { post } from "./api";
import { Button, ErrorBox, Field, useWorkspace } from "./ui";
import { useAccess } from "./access";
import { t } from "./i18n";
export default function DestinationSelector({
  value,
  onChange,
  disabled = false,
}: {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}) {
  const { projects } = useWorkspace(),
    allowed = useAccess(),
    client = useQueryClient();
  const [adding, setAdding] = useState(false),
    [name, setName] = useState(""),
    [created, setCreated] = useState<any[]>([]);
  const save = useMutation({
    mutationFn: () => post("/projects", { name }),
    onSuccess: (project) => {
      setCreated((old) => [
        ...old,
        { ...project, role: project.role || "owner" },
      ]);
      onChange(project.id);
      setAdding(false);
      setName("");
      client.invalidateQueries({ queryKey: ["projects"] });
    },
  });
  const choices = [
    ...projects,
    ...created.filter((p) => !projects.some((q) => q.id === p.id)),
  ].filter((project) => project.role !== "viewer");
  return (
    <section className="new-run-destination">
      <Field label={t("所属项目")}>
        <select
          value={value}
          disabled={disabled}
          onChange={(event) => onChange(event.target.value)}
        >
          <option value="">{t("请选择归属项目")}</option>
          {choices.map((project) => (
            <option value={project.id} key={project.id}>
              {project.name}
            </option>
          ))}
        </select>
      </Field>
      <p className="footnote">
        {t("项目只决定保存位置和访问权限，不改变当前配置草稿。")}
      </p>
      {allowed("projects.create") && (
        <Button
          type="button"
          disabled={disabled}
          onClick={() => setAdding(!adding)}
        >
          {t("新建归属项目")}
        </Button>
      )}
      {adding && (
        <>
          <Field label={t("项目名称")}>
            <input
              value={name}
              required
              maxLength={120}
              onChange={(event) => setName(event.target.value)}
            />
          </Field>
          <Button
            type="button"
            disabled={disabled || save.isPending || !name.trim()}
            onClick={() => save.mutate()}
          >
            {t("创建项目并选用")}
          </Button>
        </>
      )}
      <ErrorBox error={save.error} />
    </section>
  );
}
