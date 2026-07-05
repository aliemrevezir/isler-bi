import { useState } from "react";
import type { FilterDef } from "../lib/api";

type Values = Record<string, unknown>;

const inputCls =
  "rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-800 shadow-sm outline-none transition focus:border-brand-500 focus:ring-2 focus:ring-brand-500/30 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100";

function MultiSelect({
  def,
  value,
  onChange,
}: {
  def: FilterDef;
  value: string[];
  onChange: (v: string[]) => void;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const opts = def.options ?? [];
  const filtered = opts.filter((o) =>
    o.label.toLocaleLowerCase("tr-TR").includes(search.toLocaleLowerCase("tr-TR"))
  );
  const toggle = (v: string) => {
    if (value.includes(v)) onChange(value.filter((x) => x !== v));
    else onChange([...value, v]);
  };
  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className={`${inputCls} flex min-w-[180px] items-center justify-between text-left`}
      >
        <span className="truncate">
          {value.length ? `${value.length} seçili` : "Seçiniz"}
        </span>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M6 9l6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
      {open && (
        <div className="absolute z-30 mt-1 w-64 rounded-lg border border-slate-200 bg-white p-2 shadow-lg dark:border-slate-700 dark:bg-slate-900">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Ara..."
            className={`${inputCls} mb-2 w-full`}
          />
          <div className="max-h-56 overflow-auto">
            {filtered.length === 0 && (
              <p className="px-2 py-3 text-center text-xs text-slate-400">Sonuç yok</p>
            )}
            {filtered.map((o) => (
              <label
                key={o.value}
                className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-slate-100 dark:hover:bg-slate-800"
              >
                <input
                  type="checkbox"
                  checked={value.includes(o.value)}
                  onChange={() => toggle(o.value)}
                  className="accent-brand-500"
                />
                <span className="truncate">{o.label}</span>
              </label>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function Filters({
  defs,
  values,
  setValues,
  onApply,
  onExport,
  loading,
}: {
  defs: FilterDef[];
  values: Values;
  setValues: (v: Values) => void;
  onApply: () => void;
  onExport?: () => void;
  loading?: boolean;
}) {
  const set = (key: string, v: unknown) => setValues({ ...values, [key]: v });

  return (
    <div className="flex flex-wrap items-end gap-4 rounded-xl border border-slate-200 bg-white p-4 shadow-card dark:border-slate-800 dark:bg-slate-900">
      {defs.map((def) => (
        <div key={def.key} className="flex flex-col gap-1">
          <label className="text-xs font-medium text-slate-500 dark:text-slate-400">
            {def.label}
          </label>
          {def.type === "month" && (
            <input
              type="month"
              min={def.min}
              max={def.max}
              value={(values[def.key] as string) ?? def.default ?? ""}
              onChange={(e) => set(def.key, e.target.value)}
              className={inputCls}
            />
          )}
          {def.type === "text" && (
            <input
              type="text"
              placeholder={def.placeholder ?? "İçerir..."}
              value={(values[def.key] as string) ?? def.default ?? ""}
              onChange={(e) => set(def.key, e.target.value)}
              className={inputCls}
            />
          )}
          {def.type === "select" && (
            <select
              value={(values[def.key] as string) ?? def.default ?? ""}
              onChange={(e) => set(def.key, e.target.value)}
              className={inputCls}
            >
              {!def.default && <option value="">Tümü</option>}
              {(def.options ?? []).map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          )}
          {def.type === "multiselect" && (
            <MultiSelect
              def={def}
              value={(values[def.key] as string[]) ?? []}
              onChange={(v) => set(def.key, v)}
            />
          )}
          {def.type === "toggle" && (
            <div className="flex rounded-lg border border-slate-300 p-0.5 dark:border-slate-700">
              {(def.options ?? [
                { value: "true", label: "Evet" },
                { value: "false", label: "Hayır" },
              ]).map((o) => {
                const active =
                  ((values[def.key] as string) ?? def.default) === o.value;
                return (
                  <button
                    key={o.value}
                    type="button"
                    onClick={() => set(def.key, o.value)}
                    className={`rounded-md px-3 py-1 text-sm font-medium transition ${
                      active
                        ? "bg-brand-500 text-white"
                        : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
                    }`}
                  >
                    {o.label}
                  </button>
                );
              })}
            </div>
          )}
        </div>
      ))}

      <div className="ml-auto flex items-end gap-2">
        <button
          onClick={onApply}
          disabled={loading}
          className="rounded-lg bg-brand-500 px-4 py-1.5 text-sm font-medium text-white shadow-sm transition hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading ? "Yükleniyor..." : "Uygula"}
        </button>
        {onExport && (
          <button
            onClick={onExport}
            className="rounded-lg border border-slate-300 px-4 py-1.5 text-sm font-medium text-slate-700 transition hover:bg-slate-100 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
          >
            Excel
          </button>
        )}
      </div>
    </div>
  );
}
