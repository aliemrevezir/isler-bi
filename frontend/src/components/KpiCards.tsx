import type { Kpi } from "../lib/api";
import { formatValue } from "../lib/format";

export default function KpiCards({ kpis }: { kpis: Kpi[] }) {
  if (!kpis || kpis.length === 0) return null;
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {kpis.map((k) => (
        <div
          key={k.key}
          className="rounded-xl border border-slate-200 bg-white p-5 shadow-card transition hover:border-brand-300 dark:border-slate-800 dark:bg-slate-900 dark:hover:border-brand-700"
        >
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
            {k.label}
          </p>
          <p className="mt-2 text-2xl font-bold tabular-nums text-slate-900 dark:text-slate-50">
            {formatValue(k.value, k.format)}
          </p>
        </div>
      ))}
    </div>
  );
}
