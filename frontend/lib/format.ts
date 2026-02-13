/**
 * Locale-aware number / date / time formatting helpers.
 *
 * Arabic locale uses `ar-SA` with `numberingSystem: "latn"` so that
 * numbers remain Western digits (0-9) — required for accounting clarity.
 */

function resolveLocale(locale: string): string {
  return locale === "ar" ? "ar-SA-u-nu-latn" : "en-US";
}

/** Format a number with 2-4 decimal places (money). */
export function fmtNumber(
  value: string | number,
  locale: string,
  { zeroBlank = false }: { zeroBlank?: boolean } = {},
): string {
  const n = Number(value);
  if (zeroBlank && n === 0) return "";
  return n.toLocaleString(resolveLocale(locale), {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

/** Format a date string (ISO) to a short readable date. */
export function fmtDate(iso: string, locale: string): string {
  return new Date(iso).toLocaleDateString(resolveLocale(locale), {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

/** Format a date string (ISO) to time. */
export function fmtTime(iso: string, locale: string): string {
  return new Date(iso).toLocaleTimeString(resolveLocale(locale), {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}
