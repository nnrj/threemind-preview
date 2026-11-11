import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "./api";
import { Button, ErrorBox, Field, Modal, useWorkspace } from "./ui";
import { t } from "./i18n";
import DestinationSelector from "./DestinationSelector";
import { useAccess } from "./access";
export default function DraftResource({
  kind,
  onClose,
}: {
  kind: "note" | "record" | "report";
  onClose: () => void;
}) {
  const workspace = useWorkspace(),
    navigate = useNavigate(),
    client = useQueryClient(),
    allowed = useAccess();
  const [identity] = useState(() => crypto.randomUUID()),
    [operation] = useState(() => crypto.randomUUID());
  const [title, setTitle] = useState(""),
    [text, setText] = useState(""),
    [destination, setDestination] = useState(
      workspace.project?.role !== "viewer" ? workspace.project?.id || "" : "",
    );
  const save = useMutation({
    mutationFn: () =>
      api(
        `/projects/${destination}/${kind === "note" ? "notes" : "research-documents"}/${identity}`,
        {
          method: "PUT",
          body: JSON.stringify(
            kind === "note"
              ? {
                  title,
                  kind: "note",
                  collection_id: null,
                  body: { format: "markdown", text },
                  expected_revision: 0,
                  operation_id: operation,
                }
              : {
                  spec: {
                    schema_version: "threemind.research-document/1",
                    kind,
                    title,
                    sources: [],
                    blocks: [
                      {
                        id: operation,
                        type: "commentary",
                        section: "purpose",
                        markdown: text,
                      },
                    ],
                  },
                  review: "draft",
                  expected_revision: 0,
                  operation_id: operation,
                },
          ),
        },
      ),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["browse-resources"] });
      onClose();
      navigate(
        kind === "note"
          ? `/notes?note=${identity}&project=${destination}&tab=write`
          : `/reports?document=${identity}&project=${destination}&tab=${kind}`,
      );
    },
  });
  const permission = kind === "note" ? "notes.write" : "reports.write";
  return (
    <Modal
      open
      wide
      title={
        kind === "note"
          ? t("新建笔记")
          : kind === "record"
            ? t("新建实验记录")
            : t("新建实验报告")
      }
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      description={t(
        "先编辑正文，保存时选择项目；保存后可继续关联数据与编辑完整内容。",
      )}
    >
      <form
        onSubmit={(event) => {
          event.preventDefault();
          save.mutate();
        }}
      >
        <Field label={t("标题")}>
          <input
            value={title}
            required
            maxLength={200}
            onChange={(event) => setTitle(event.target.value)}
          />
        </Field>
        <Field label={t("Markdown 正文")}>
          <textarea
            rows={12}
            value={text}
            onChange={(event) => setText(event.target.value)}
          />
        </Field>
        <DestinationSelector
          value={destination}
          onChange={setDestination}
          disabled={save.isPending}
        />
        <ErrorBox error={save.error} />
        <div className="form-actions">
          <Button type="button" onClick={onClose}>
            {t("取消")}
          </Button>
          <Button
            variant="primary"
            disabled={
              !destination ||
              !title.trim() ||
              !allowed(permission) ||
              save.isPending
            }
          >
            {t("保存并继续编辑")}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
