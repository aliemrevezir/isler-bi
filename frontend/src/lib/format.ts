export type FormatKind = "int" | "money" | "num" | "pct" | "text" | string;

const intFmt = new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 0 });
const moneyFmt = new Intl.NumberFormat("tr-TR", {
  style: "currency",
  currency: "TRY",
  maximumFractionDigits: 0,
});
const numFmt = new Intl.NumberFormat("tr-TR", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});
const pctFmt = new Intl.NumberFormat("tr-TR", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

export function formatValue(value: unknown, format: FormatKind): string {
  if (value === null || value === undefined || value === "") return "—";

  const num = typeof value === "number" ? value : Number(value);
  const isNum = typeof value === "number" || (!Number.isNaN(num) && value !== "");

  switch (format) {
    case "int":
      return isNum ? intFmt.format(Math.round(num)) : String(value);
    case "money":
      return isNum ? moneyFmt.format(num) : String(value);
    case "num":
      return isNum ? numFmt.format(num) : String(value);
    case "pct":
      return isNum ? `%${pctFmt.format(num)}` : String(value);
    default:
      return String(value);
  }
}

export const NUMERIC_FORMATS = new Set(["int", "money", "num", "pct"]);
