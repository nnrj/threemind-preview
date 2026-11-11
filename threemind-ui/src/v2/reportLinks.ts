const uuid =
  "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}";
const projectPath = new RegExp(`^/(?:api/v2/)?projects/${uuid}$`);
const resourcePath = new RegExp(`^/(note-assets|artifacts)/${uuid}$`);

// Private report previews may reference their own authenticated project blobs.
// Public shares have no project base; arbitrary URLs never become image requests.
export function projectResourceHref(
  href: string | undefined,
  base?: string,
  imageOnly = false,
): string | undefined {
  if (!base || !projectPath.test(base)) return;
  // API callers use /projects/...; image/link elements need the full API path.
  const canonical = base.startsWith("/api/v2/") ? base : `/api/v2${base}`;
  if (!href?.startsWith(canonical + "/")) return;
  const resource = resourcePath.exec(href.slice(canonical.length));
  if (!resource || (imageOnly && resource[1] !== "note-assets")) return;
  return href;
}
