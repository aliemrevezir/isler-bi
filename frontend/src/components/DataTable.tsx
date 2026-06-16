import type { Column } from "../lib/api";
import { formatValue, NUMERIC_FORMATS } from "../lib/format";
import { EmptyState } from "./States";

export default function DataTable({
  columns,
  rows,
}: {
  columns: Column[];
  rows: Record<string, unknown>[];
}) {
  if (!rows || rows.length === 0) {
    return <EmptyState title="Veri yok" message="Gösterilecek satır bulunamadı." />;
  }

  return (
    <div className="overflow-auto rounded-xl border border-slate-200 bg-white shadow-card dark:border-slate-800 dark:bg-slate-900">
      <table className="min-w-full text-sm">
        <thead className="sticky top-0 z-10 bg-slate-50 dark:bg-slate-800/80">
          <tr>
            {columns.map((c) => {
              const numeric = NUMERIC_FORMATS.has(c.format);
              return (
                <th
                  key={c.key}
                  className={`whitespace-nowrap border-b border-slate-200 px-4 py-2.5 font-semibold text-slate-600 dark:border-slate-700 dark:text-slate-300 ${
                    numeric ? "text-right" : "text-left"
                  }`}
                >
                  {c.label}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr
              key={i}
              className="border-b border-slate-100 transition hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-800/40"
            >
              {columns.map((c) => {
                const numeric = NUMERIC_FORMATS.has(c.format);
                return (
                  <td
                    key={c.key}
                    className={`whitespace-nowrap px-4 py-2 text-slate-700 dark:text-slate-200 ${
                      numeric ? "text-right tabular-nums" : "text-left"
                    }`}
                  >
                    {formatValue(row[c.key], c.format)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
