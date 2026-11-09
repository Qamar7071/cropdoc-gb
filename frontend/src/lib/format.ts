/* Formatting helpers. Numbers are always formatted from real values; null/undefined → "—". */

export function percent(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

/** Probabilities for people: never claim certainty. 0.99998 → "> 99.9%", 0.00001 → "< 0.1%". */
export function probability(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  if (value >= 0.9995) return "> 99.9%";
  if (value < 0.0005) return "< 0.1%";
  return percent(value);
}

export function decimal(value: number | null | undefined, digits = 3): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toFixed(digits);
}

export function formatDate(iso: string, lang: string): string {
  try {
    return new Intl.DateTimeFormat(lang === "ur" ? "ur-PK" : "en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    }).format(new Date(iso));
  } catch {
    return iso.slice(0, 10);
  }
}

export function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}
