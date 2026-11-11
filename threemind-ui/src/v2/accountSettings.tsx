import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { post } from "./api";
import { Button, ErrorBox, Field, useWorkspace } from "./ui";
import { t } from "./i18n";
export default function AccountSettings() {
  const { user } = useWorkspace();
  const [current, setCurrent] = useState(""),
    [password, setPassword] = useState(""),
    [repeat, setRepeat] = useState("");
  const change = useMutation({
    mutationFn: () =>
      post("/account/password", { current_password: current, password }),
    onSuccess: () => {
      setCurrent("");
      setPassword("");
      setRepeat("");
    },
  });
  return (
    <section className="panel">
      <h2>{t("我的账号")}</h2>
      <p>
        {user?.username} ·{" "}
        {(user?.roles || []).map((role: any) => role.name).join(" / ")}
      </p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          change.mutate();
        }}
      >
        <h3>{t("修改密码")}</h3>
        <p>{t("修改密码将撤销其他登录会话，当前会话保留。")}</p>
        <Field label={t("当前密码")}>
          <input
            type="password"
            required
            value={current}
            autoComplete="current-password"
            onChange={(e) => setCurrent(e.target.value)}
          />
        </Field>
        <Field label={t("新密码")}>
          <input
            type="password"
            required
            minLength={12}
            value={password}
            autoComplete="new-password"
            onChange={(e) => setPassword(e.target.value)}
          />
        </Field>
        <Field label={t("确认密码")}>
          <input
            type="password"
            required
            minLength={12}
            value={repeat}
            autoComplete="new-password"
            onChange={(e) => setRepeat(e.target.value)}
          />
        </Field>
        <ErrorBox error={change.error} />
        {change.isSuccess && <p role="status">{t("密码已更新。")}</p>}
        <Button
          variant="primary"
          disabled={change.isPending || password !== repeat}
        >
          {t("保存密码")}
        </Button>
      </form>
    </section>
  );
}
