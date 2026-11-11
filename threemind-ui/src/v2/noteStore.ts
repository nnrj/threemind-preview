import { api, ApiError } from "./api";
import { t } from "./i18n";
import type { JSONContent } from "@tiptap/core";

export type NoteBody =
  | { format: "markdown"; text: string }
  | { format: "document"; content: JSONContent };
export type NoteDraft = {
  title: string;
  kind: "draft" | "note";
  collection_id: string | null;
  body: NoteBody;
};
export type NoteRow = NoteDraft & {
  id: string;
  revision: number;
  archived_at: string | null;
  updated_at: string;
  content_hash: string;
  version_metadata: Omit<NoteDraft, "body">;
};
type Pending = NoteDraft & { operation_id: string; expected_revision: number };
type Snapshot = {
  id: string;
  draft: NoteDraft;
  revision: number;
  saving: boolean;
  dirty: boolean;
  error: unknown;
  cacheError: boolean;
};
type Recovery = {
  id: string;
  draft: NoteDraft;
  revision: number;
  saved: string;
  pending: Pending | null;
};
const fingerprint = (draft: NoteDraft) => JSON.stringify(draft);
const activeSessions = new Map<string, symbol>();
export const blankNote = (): NoteDraft => ({
  title: t("未命名笔记"),
  kind: "draft",
  collection_id: null,
  body: { format: "markdown", text: "" },
});
export const noteDraft = (row: NoteDraft): NoteDraft => ({
  title: row.title,
  kind: row.kind,
  collection_id: row.collection_id,
  body: row.body,
});

export function clearNoteRecovery() {
  activeSessions.clear();
  try {
    sessionStorage.removeItem("tm2.note.identity");
    for (const key of Object.keys(sessionStorage))
      if (key.startsWith("tm2.note.recovery:")) sessionStorage.removeItem(key);
  } catch {
    /* Storage may be disabled. Database editing still works. */
  }
}
export function setNoteIdentity(user: string) {
  try {
    if (sessionStorage.getItem("tm2.note.identity") !== user)
      clearNoteRecovery();
    sessionStorage.setItem("tm2.note.identity", user);
  } catch {
    /* A visible cache status is provided by the authoring controller. */
  }
}

// A single writer serializes saves and retains uncertain requests verbatim.
// React unmounting does not cancel a save or clear its recoverable draft.
export class NoteSession {
  private listeners = new Set<() => void>();
  private pending: Pending | null = null;
  private saved: string;
  private current: Snapshot;
  private flight: Promise<boolean> | null = null;
  private key: string;
  private cacheToken = Symbol();
  private cacheTimer: ReturnType<typeof setTimeout> | undefined;
  constructor(
    private project: string,
    private user: string,
    private changed: () => void,
  ) {
    const draft = blankNote();
    this.saved = fingerprint(draft);
    this.current = {
      id: crypto.randomUUID(),
      draft,
      revision: 0,
      saving: false,
      dirty: false,
      error: null,
      cacheError: false,
    };
    this.key = `tm2.note.recovery:${user}:${project}`;
    activeSessions.set(this.key, this.cacheToken);
  }
  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };
  snapshot = () => this.current;
  private publish(changes: Partial<Snapshot> = {}) {
    this.current = { ...this.current, ...changes };
    this.current.dirty =
      fingerprint(this.current.draft) !== this.saved || this.pending !== null;
    clearTimeout(this.cacheTimer);
    this.cacheTimer = setTimeout(() => this.persist(), 350);
    this.listeners.forEach((fn) => fn());
  }
  persist = () => {
    clearTimeout(this.cacheTimer);
    let failed = false;
    try {
      if (
        activeSessions.get(this.key) === this.cacheToken &&
        sessionStorage.getItem("tm2.note.identity") === this.user
      ) {
        if (this.current.dirty)
          sessionStorage.setItem(
            this.key,
            JSON.stringify({
              id: this.current.id,
              draft: this.current.draft,
              revision: this.current.revision,
              saved: this.saved,
              pending: this.pending,
            }),
          );
        else sessionStorage.removeItem(this.key);
      }
    } catch {
      failed = true;
    }
    if (this.current.cacheError !== failed) {
      this.current = { ...this.current, cacheError: failed };
      this.listeners.forEach((fn) => fn());
    }
  };
  recovery(): Recovery | null {
    try {
      const raw = JSON.parse(sessionStorage.getItem(this.key) ?? "null");
      if (
        raw &&
        typeof raw.id === "string" &&
        raw.draft &&
        Number.isSafeInteger(raw.revision) &&
        typeof raw.saved === "string"
      )
        return raw;
    } catch {
      /* Ignore malformed browser cache. */
    }
    return null;
  }
  recover(raw: Recovery) {
    this.saved = raw.saved;
    this.pending = raw.pending;
    this.publish({
      id: raw.id,
      draft: raw.draft,
      revision: raw.revision,
      error: null,
    });
  }
  discardRecovery() {
    try {
      sessionStorage.removeItem(this.key);
    } catch {
      /* No cache. */
    }
  }
  edit(changes: Partial<NoteDraft>) {
    const error = this.current.error;
    this.publish({
      draft: { ...this.current.draft, ...changes },
      error: error instanceof ApiError && error.status === 422 ? null : error,
    });
  }
  replace(row: NoteRow | null, draft = blankNote()) {
    if (this.flight) throw new Error(t("请等待当前保存完成。"));
    const next = row ? noteDraft(row) : draft;
    this.saved = fingerprint(next);
    this.pending = null;
    this.publish({
      id: row?.id ?? crypto.randomUUID(),
      draft: next,
      revision: row?.revision ?? 0,
      error: null,
    });
  }
  copy() {
    if (this.flight) return;
    const draft = this.current.draft;
    this.saved = "";
    this.pending = null;
    this.publish({
      id: crypto.randomUUID(),
      revision: 0,
      draft: {
        ...draft,
        title: t("{title}（副本）", { title: draft.title }).slice(0, 200),
      },
      error: null,
    });
  }
  flush = (): Promise<boolean> => {
    if (this.flight) return this.flight;
    const perform = async () => {
      this.publish({ saving: true, error: null });
      try {
        while (this.current.dirty) {
          this.pending ??= {
            ...structuredClone(this.current.draft),
            operation_id: crypto.randomUUID(),
            expected_revision: this.current.revision,
          };
          this.publish();
          const sent = this.pending;
          this.persist();
          const result = await api(
            `/projects/${this.project}/notes/${this.current.id}`,
            { method: "PUT", body: JSON.stringify(sent) },
          );
          const draft = noteDraft(sent);
          // The default notebook is assigned atomically by the database.
          if (
            result.collection_id &&
            draft.kind === "note" &&
            !draft.collection_id
          )
            draft.collection_id = result.collection_id;
          const current = this.current.draft;
          this.saved = fingerprint(draft);
          this.pending = null;
          this.publish({
            revision: result.revision,
            draft:
              fingerprint(current) === fingerprint(noteDraft(sent))
                ? draft
                : current,
          });
          this.changed();
        }
        return true;
      } catch (error) {
        if (
          error instanceof ApiError &&
          [409, 422, 403, 404].includes(error.status)
        )
          this.pending = null;
        this.publish({ error });
        return false;
      } finally {
        this.publish({ saving: false });
      }
    };
    this.flight = perform().finally(() => {
      this.flight = null;
    });
    return this.flight;
  };
}
