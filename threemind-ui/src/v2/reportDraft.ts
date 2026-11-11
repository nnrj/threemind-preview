// Temporary recovery only. PostgreSQL revisions remain authoritative.
const prefix = "tm2.report-draft:",
  identity = "tm2.report-identity";
const writers = new Map<string, symbol>();
export const reportDraftKey = (actor: string, base: string, id: string) =>
  `${prefix}${actor}:${base}:${id}`;
export function clearReportRecovery() {
  writers.clear();
  try {
    sessionStorage.removeItem(identity);
    for (const key of Object.keys(sessionStorage))
      if (key.startsWith(prefix)) sessionStorage.removeItem(key);
  } catch {
    /* Optional browser storage. */
  }
}
export function openReportDraft(actor: string, key: string) {
  const token = Symbol();
  let data: any = null;
  try {
    if (sessionStorage.getItem(identity) !== actor) clearReportRecovery();
    sessionStorage.setItem(identity, actor);
    data = JSON.parse(sessionStorage.getItem(key) ?? "null");
  } catch {
    /* The database editor still works without a local recovery cache. */
  }
  writers.set(key, token);
  return {
    data,
    activate() {
      writers.set(key, token);
    },
    write(value: any) {
      try {
        if (
          writers.get(key) === token &&
          sessionStorage.getItem(identity) === actor
        )
          sessionStorage.setItem(key, JSON.stringify(value));
      } catch {
        /* No effect on durable saves. */
      }
    },
    clear() {
      try {
        if (writers.get(key) === token) sessionStorage.removeItem(key);
      } catch {
        /* Optional storage. */
      }
    },
    close() {
      if (writers.get(key) === token) writers.delete(key);
    },
  };
}
