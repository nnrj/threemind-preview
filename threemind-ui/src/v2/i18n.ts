import { usePreferences, preferences } from "./preferences";
import english from "./locales/en";

export type Locale = "zh-CN" | "en";
// Mark source-owned dynamic label maps for the source catalogue audit.
// Values remain keys until render, so language changes never freeze a module's copy.
export function messageKeys<T extends Record<string, string>>(values: T): T {
  return values;
}
export function resolveLocale(
  value: string,
  languages: readonly string[] = navigator.languages,
): Locale {
  if (value === "zh-CN" || value === "en") return value;
  for (const language of languages) {
    if (/^zh(?:-|$)/i.test(language)) return "zh-CN";
    if (/^en(?:-|$)/i.test(language)) return "en";
  }
  return "zh-CN";
}
export function locale(): Locale {
  return resolveLocale(preferences().locale);
}
export function useLocale(): Locale {
  return resolveLocale(usePreferences().locale);
}
export function translate(
  source: string,
  language: Locale,
  values: Record<string, string | number> = {},
): string {
  const key = source.trim().replace(/\s+/g, " ");
  const translated =
    language === "en" && Object.hasOwn(english, key)
      ? (source.match(/^\s*/)?.[0] ?? "") +
        english[key] +
        (source.match(/\s*$/)?.[0] ?? "")
      : source;
  return translated.replace(
    /\{([a-zA-Z_][a-zA-Z_0-9]*)\}/g,
    (token, key: string) =>
      Object.hasOwn(values, key) ? String(values[key]) : token,
  );
}
// Call only for source-owned UI copy. User names, notes, stimuli, protocol JSON,
// model data and server error payloads are never passed through this lookup.
export function t(
  source: string,
  values?: Record<string, string | number>,
): string {
  return translate(source, locale(), values);
}
export function dateLabel(value: string | Date): string {
  return new Date(value).toLocaleString(locale());
}
