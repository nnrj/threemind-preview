import type { ReactNode } from "react";
import { t } from "./i18n";
import { Empty, useWorkspace } from "./ui";

export type AccessScope =
  "platform" | "all_projects" | "member_projects" | "own";
export type Permission = { action: string; scope: AccessScope };
export type AccountRole = {
  id: string;
  key: string;
  name: string;
  builtin: boolean;
};
export type Account = {
  id: string;
  username: string;
  superadmin?: boolean;
  roles?: AccountRole[];
  permissions?: Permission[];
};

// This controls the presentation only. The canonical services check the same
// capability and the object's actual ownership, privacy and scientific locks.
export function can(
  user: Account | null | undefined,
  action: string,
  scope?: AccessScope,
): boolean {
  if (!user) return false;
  if (user.superadmin) return true;
  return (user.permissions ?? []).some((permission) => {
    if (permission.action !== action) return false;
    if (!scope || permission.scope === scope) return true;
    return (
      (permission.scope === "all_projects" &&
        ["member_projects", "own"].includes(scope)) ||
      (permission.scope === "member_projects" && scope === "own")
    );
  });
}

export function useAccess() {
  const { user } = useWorkspace();
  return (action: string, scope?: AccessScope) => can(user, action, scope);
}

export function AccessBoundary({
  action,
  children,
}: {
  action: string;
  children: ReactNode;
}) {
  const allowed = useAccess();
  return allowed(action) ? (
    <>{children}</>
  ) : (
    <Empty
      title={t("没有此功能的访问权限")}
      detail={t(
        "可向管理员申请相应功能权限。资料归属和实验状态仍由服务端核验。",
      )}
    />
  );
}
