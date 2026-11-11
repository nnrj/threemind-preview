import { t } from "./i18n";
import { useQuery } from "@tanstack/react-query";
import { Bell } from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "./api";
import { useWorkspace } from "./ui";

export default function NotificationBell() {
  const { user } = useWorkspace();
  const count = useQuery({
    queryKey: ["notification-unread", user?.id],
    queryFn: () =>
      api<{ unread: number }>(
        "/notifications/unread",
      ),
    enabled: !!user,
    refetchInterval: 5000,
    refetchIntervalInBackground: false,
  });

  const unread = count.data?.unread;
  return (
    <Link
      className="icon-button notification-bell"
      to="/settings?section=notifications&view=history"
      aria-label={
        unread == null
          ? t("查看通知")
          : t("查看通知，{count} 条未读", { count: unread })
      }
      title={count.error ? t("通知暂时无法读取") : t("我的通知")}
    >
      <Bell size={17} />
      {unread != null && unread > 0 && (
        <span>{unread > 99 ? "99+" : unread}</span>
      )}
    </Link>
  );
}
