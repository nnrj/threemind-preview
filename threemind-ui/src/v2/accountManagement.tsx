import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, ShieldCheck, KeyRound } from "lucide-react";
import { api, post } from "./api";
import {
  useAccess,
  type AccountRole,
  type Permission,
  type AccessScope,
} from "./access";
import {
  Button,
  Empty,
  ErrorBox,
  Field,
  Loading,
  Modal,
  PageTitle,
  useWorkspace,
} from "./ui";
import { t } from "./i18n";

type Role = AccountRole & { revision: number; permissions: Permission[] };
type User = {
  id: string;
  username: string;
  enabled: boolean;
  superadmin: boolean;
  roles: AccountRole[];
};
type Catalogue = {
  actions: {
    id: string;
    title: string;
    category: string;
    scopes: AccessScope[];
  }[];
  scopes: { id: AccessScope; title: string }[];
};
const update = (path: string, body: unknown) =>
  api(path, { method: "PUT", body: JSON.stringify(body) });

export default function AccountManagement() {
  const allowed = useAccess(),
    { user: actor } = useWorkspace();
  const client = useQueryClient();
  const [tab, setTab] = useState(allowed("accounts.read") ? "users" : "roles");
  const users = useQuery<{ users: User[] }>({
    queryKey: ["account-users"],
    queryFn: () => api("/accounts/users"),
    enabled: allowed("accounts.read"),
  });
  const roles = useQuery<{ roles: Role[] }>({
    queryKey: ["account-roles"],
    queryFn: () => api("/accounts/roles"),
    enabled: allowed("roles.read"),
  });
  const catalogue = useQuery<Catalogue>({
    queryKey: ["permission-catalogue"],
    queryFn: () => api("/permissions/catalog"),
    enabled: allowed("roles.read"),
  });
  const [editingUser, setEditingUser] = useState<User | "new" | null>(null);
  const [editingRole, setEditingRole] = useState<Role | "new" | null>(null);
  const [passwordUser, setPasswordUser] = useState<User | null>(null);
  const [deleteRole, setDeleteRole] = useState<Role | null>(null);
  const changed = () => {
    client.invalidateQueries({ queryKey: ["account-users"] });
    client.invalidateQueries({ queryKey: ["account-roles"] });
    client.invalidateQueries({ queryKey: ["session"] });
  };
  const enable = useMutation({
    mutationFn: (row: User) =>
      update(`/accounts/users/${row.id}/enabled`, { enabled: !row.enabled }),
    onSuccess: changed,
  });
  const remove = useMutation({
    mutationFn: () =>
      api(`/accounts/roles/${deleteRole!.id}`, { method: "DELETE" }),
    onSuccess: () => {
      changed();
      setDeleteRole(null);
    },
  });
  const availableRoles = (roles.data?.roles ?? []).filter(
    (role) => actor?.superadmin || role.key !== "superadmin",
  );
  return (
    <div className="account-management">
      <PageTitle
        eyebrow="ACCOUNTS AND PERMISSIONS"
        title={t("用户与权限")}
        description={t(
          "在同一界面管理用户、多角色和功能授权。科研资料仍保留原有身份与修订。",
        )}
      />
      <div className="tabs" aria-label={t("账户管理分类")}>
        {allowed("accounts.read") && (
          <Button
            variant={tab === "users" ? "primary" : ""}
            onClick={() => setTab("users")}
          >
            {t("用户")}
          </Button>
        )}
        {allowed("roles.read") && (
          <Button
            variant={tab === "roles" ? "primary" : ""}
            onClick={() => setTab("roles")}
          >
            {t("角色与权限")}
          </Button>
        )}
      </div>
      <ErrorBox
        error={users.error || roles.error || catalogue.error || enable.error}
      />
      {tab === "users" && allowed("accounts.read") && (
        <section className="panel">
          <div className="panel-heading">
            <div>
              <h2>{t("用户与角色分配")}</h2>
              <p>
                {t(
                  "一个用户可拥有多个角色。角色提供功能权限，资料范围另行核验。",
                )}
              </p>
            </div>
            {allowed("accounts.manage") && (
              <Button variant="primary" onClick={() => setEditingUser("new")}>
                <Plus size={16} />
                {t("添加用户")}
              </Button>
            )}
          </div>
          {users.isPending ? (
            <Loading />
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>{t("账号")}</th>
                    <th>{t("角色")}</th>
                    <th>{t("状态")}</th>
                    <th>{t("操作")}</th>
                  </tr>
                </thead>
                <tbody>
                  {users.data?.users.map((row) => (
                    <tr key={row.id}>
                      <td>{row.username}</td>
                      <td>
                        {row.roles.map((role) => role.name).join("、") || "—"}
                      </td>
                      <td>{row.enabled ? t("启用") : t("停用")}</td>
                      <td>
                        <div className="form-actions">
                          {allowed("accounts.manage") && (
                            <>
                              <Button
                                variant="small"
                                onClick={() => setEditingUser(row)}
                                disabled={row.superadmin && !actor?.superadmin}
                              >
                                <Pencil size={14} />
                                {t("分配角色")}
                              </Button>
                              <Button
                                variant="small"
                                onClick={() => setPasswordUser(row)}
                                disabled={row.superadmin && !actor?.superadmin}
                              >
                                <KeyRound size={14} />
                                {t("重置密码")}
                              </Button>
                              <Button
                                variant="small"
                                onClick={() => enable.mutate(row)}
                                disabled={
                                  enable.isPending ||
                                  row.id === actor?.id ||
                                  (row.superadmin && !actor?.superadmin)
                                }
                              >
                                {row.enabled ? t("停用并撤销会话") : t("启用")}
                              </Button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
      {tab === "roles" && allowed("roles.read") && (
        <section className="panel">
          <div className="panel-heading">
            <div>
              <h2>{t("角色与功能权限")}</h2>
              <p>
                {t(
                  "权限同时约束菜单、按钮和后台接口。超管可访问全部资料；科学锁和历史版本约束仍然有效。",
                )}
              </p>
            </div>
            {allowed("roles.manage") && (
              <Button variant="primary" onClick={() => setEditingRole("new")}>
                <Plus size={16} />
                {t("新建角色")}
              </Button>
            )}
          </div>
          {roles.isPending ? (
            <Loading />
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>{t("角色")}</th>
                    <th>{t("角色标识")}</th>
                    <th>{t("功能授权")}</th>
                    <th>{t("操作")}</th>
                  </tr>
                </thead>
                <tbody>
                  {roles.data?.roles.map((row) => (
                    <tr key={row.id}>
                      <td>
                        <ShieldCheck size={14} /> {row.name}
                        {row.builtin && <small> · {t("内置角色")}</small>}
                      </td>
                      <td>
                        <code>{row.key}</code>
                      </td>
                      <td>
                        {row.key === "superadmin"
                          ? t("全部功能与资料")
                          : row.permissions.length}
                      </td>
                      <td>
                        {allowed("roles.manage") &&
                          row.key !== "superadmin" && (
                            <div className="form-actions">
                              <Button
                                variant="small"
                                onClick={() => setEditingRole(row)}
                              >
                                {t("编辑权限")}
                              </Button>
                              {!row.builtin && (
                                <Button
                                  variant="small"
                                  onClick={() => {
                                    remove.reset();
                                    setDeleteRole(row);
                                  }}
                                >
                                  {t("删除角色")}
                                </Button>
                              )}
                            </div>
                          )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
      {editingUser && (
        <UserEditor
          row={editingUser}
          roles={availableRoles}
          onClose={() => setEditingUser(null)}
          onSaved={changed}
        />
      )}
      {editingRole && catalogue.data && (
        <RoleEditor
          row={editingRole}
          catalogue={catalogue.data}
          onClose={() => setEditingRole(null)}
          onSaved={changed}
        />
      )}
      {passwordUser && (
        <PasswordReset
          row={passwordUser}
          onClose={() => setPasswordUser(null)}
          onSaved={changed}
        />
      )}
      <Modal
        open={!!deleteRole}
        title={t("删除角色")}
        onOpenChange={(open) => !open && setDeleteRole(null)}
      >
        <p>{t("仅未分配给用户的自定义角色可以删除。内置角色不可删除。")}</p>
        <strong>{deleteRole?.name}</strong>
        <ErrorBox error={remove.error} />
        <div className="form-actions">
          <Button onClick={() => setDeleteRole(null)}>{t("取消")}</Button>
          <Button
            variant="primary"
            disabled={remove.isPending}
            onClick={() => remove.mutate()}
          >
            {t("确认删除角色")}
          </Button>
        </div>
      </Modal>
    </div>
  );
}

function UserEditor({
  row,
  roles,
  onClose,
  onSaved,
}: {
  row: User | "new";
  roles: Role[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [username, setUsername] = useState(row === "new" ? "" : row.username);
  const [password, setPassword] = useState("");
  const [selected, setSelected] = useState(
    row === "new"
      ? roles.filter((role) => role.key === "user").map((role) => role.id)
      : row.roles.map((role) => role.id),
  );
  const save = useMutation({
    mutationFn: () =>
      row === "new"
        ? post("/accounts/users", { username, password, role_ids: selected })
        : update(`/accounts/users/${row.id}/roles`, { role_ids: selected }),
    onSuccess: () => {
      onSaved();
      onClose();
    },
  });
  return (
    <Modal
      open
      title={row === "new" ? t("添加用户") : t("分配角色")}
      onOpenChange={(open) => !open && onClose()}
    >
      <form
        onSubmit={(event) => {
          event.preventDefault();
          save.mutate();
        }}
      >
        <Field label={t("账号")}>
          <input
            value={username}
            required
            minLength={3}
            maxLength={80}
            disabled={row !== "new"}
            autoComplete="off"
            onChange={(event) => setUsername(event.target.value)}
          />
        </Field>
        {row === "new" && (
          <Field
            label={t("初始密码")}
            hint={t("至少 12 个字符。密码不会进入日志或研究记录。")}
          >
            <input
              type="password"
              required
              minLength={12}
              value={password}
              autoComplete="new-password"
              onChange={(event) => setPassword(event.target.value)}
            />
          </Field>
        )}
        <fieldset className="permission-roles">
          <legend>{t("角色")}</legend>
          {roles.map((role) => (
            <label className="check" key={role.id}>
              <input
                type="checkbox"
                checked={selected.includes(role.id)}
                onChange={(event) =>
                  setSelected((old) =>
                    event.target.checked
                      ? [...old, role.id]
                      : old.filter((id) => id !== role.id),
                  )
                }
              />
              {role.name}
            </label>
          ))}
        </fieldset>
        <ErrorBox error={save.error} />
        <div className="form-actions">
          <Button type="button" onClick={onClose}>
            {t("取消")}
          </Button>
          <Button
            variant="primary"
            disabled={save.isPending || !selected.length}
          >
            {t("保存")}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function RoleEditor({
  row,
  catalogue,
  onClose,
  onSaved,
}: {
  row: Role | "new";
  catalogue: Catalogue;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState(row === "new" ? "" : row.name);
  const [key, setKey] = useState(row === "new" ? "" : row.key);
  const [permissions, setPermissions] = useState<Permission[]>(
    row === "new" ? [] : row.permissions,
  );
  const save = useMutation({
    mutationFn: () =>
      row === "new"
        ? post("/accounts/roles", { key, name, permissions })
        : update(`/accounts/roles/${row.id}`, {
            name,
            permissions,
            expected_revision: row.revision,
          }),
    onSuccess: () => {
      onSaved();
      onClose();
    },
  });
  const categories = [
    ...new Set(catalogue.actions.map((action) => action.category)),
  ];
  return (
    <Modal
      open
      wide
      title={t("角色与权限")}
      onOpenChange={(open) => !open && onClose()}
    >
      <form
        onSubmit={(event) => {
          event.preventDefault();
          save.mutate();
        }}
      >
        <div className="form-grid">
          <Field label={t("角色名称")}>
            <input
              required
              maxLength={80}
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </Field>
          <Field label={t("角色标识")}>
            <input
              required
              value={key}
              disabled={row !== "new"}
              pattern="[a-z][a-z0-9_.-]*"
              minLength={3}
              maxLength={64}
              onChange={(event) => setKey(event.target.value)}
            />
          </Field>
        </div>
        <p>{t("勾选功能及可用资料范围。菜单可见不等于拥有资料操作权限。")}</p>
        <div className="permission-tree">
          {categories.map((category) => (
            <details key={category} open>
              <summary>{t(category)}</summary>
              {catalogue.actions
                .filter((action) => action.category === category)
                .map((action) => (
                  <div key={action.id} className="permission-action">
                    <div>
                      <strong>{t(action.title)}</strong>
                      <code>{action.id}</code>
                    </div>
                    <div>
                      {action.scopes.map((scope) => (
                        <label className="check" key={scope}>
                          <input
                            type="checkbox"
                            checked={permissions.some(
                              (permission) =>
                                permission.action === action.id &&
                                permission.scope === scope,
                            )}
                            onChange={(event) =>
                              setPermissions((old) =>
                                event.target.checked
                                  ? [...old, { action: action.id, scope }]
                                  : old.filter(
                                      (permission) =>
                                        permission.action !== action.id ||
                                        permission.scope !== scope,
                                    ),
                              )
                            }
                          />
                          {t(
                            catalogue.scopes.find((item) => item.id === scope)
                              ?.title ?? scope,
                          )}
                        </label>
                      ))}
                    </div>
                  </div>
                ))}
            </details>
          ))}
        </div>
        <ErrorBox error={save.error} />
        <div className="form-actions">
          <Button type="button" onClick={onClose}>
            {t("取消")}
          </Button>
          <Button variant="primary" disabled={save.isPending}>
            {t("保存权限")}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function PasswordReset({
  row,
  onClose,
  onSaved,
}: {
  row: User;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [password, setPassword] = useState("");
  const save = useMutation({
    mutationFn: () => post(`/accounts/users/${row.id}/password`, { password }),
    onSuccess: () => {
      onSaved();
      onClose();
    },
  });
  return (
    <Modal
      open
      title={t("重置密码")}
      onOpenChange={(open) => !open && onClose()}
    >
      <form
        onSubmit={(event) => {
          event.preventDefault();
          save.mutate();
        }}
      >
        <p>
          {row.username} · {t("保存后该用户的旧会话将被撤销。")}
        </p>
        <Field label={t("新密码")}>
          <input
            type="password"
            required
            minLength={12}
            value={password}
            autoComplete="new-password"
            onChange={(event) => setPassword(event.target.value)}
          />
        </Field>
        <ErrorBox error={save.error} />
        <div className="form-actions">
          <Button type="button" onClick={onClose}>
            {t("取消")}
          </Button>
          <Button variant="primary" disabled={save.isPending}>
            {t("保存新密码")}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
