import { useEffect, useRef, useState } from "react";
import Layout from "../components/Layout";
import {
  EmptyState,
  ErrorBanner,
  StatusBadge,
  TableSkeleton,
} from "../components/States";
import {
  ingestApi,
  errMsg,
  type IngestSource,
  type IngestRun,
  type IngestProgress,
} from "../lib/api";
import { useAuth } from "../lib/auth";
import { formatValue } from "../lib/format";

function fmtTime(s?: string | null) {
  if (!s) return "—";
  try {
    return new Date(s).toLocaleString("tr-TR");
  } catch {
    return s;
  }
}

function fmtInt(n?: number | null) {
  if (n == null) return "—";
  return new Intl.NumberFormat("tr-TR").format(Math.round(n));
}

const STATUS_TR: Record<string, string> = {
  pending: "bekliyor",
  running: "çekiliyor",
  done: "tamam",
  error: "hata",
};

/** Canlı ingest ilerlemesi: genel çubuk + kaynak-bazlı çubuklar. */
function ProgressView({
  progress,
  live,
}: {
  progress: IngestProgress;
  live: boolean;
}) {
  return (
    <div className="mb-3 rounded-lg border border-slate-200 bg-slate-50 p-3 dark:border-slate-800 dark:bg-slate-800/40">
      {/* Genel ilerleme */}
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="font-semibold text-slate-700 dark:text-slate-200">
          {live ? "Genel İlerleme (canlı)" : "Genel İlerleme"}
        </span>
        <span className="tabular-nums font-medium text-brand-600 dark:text-brand-400">
          %{progress.overall_percent}
        </span>
      </div>
      <div className="mb-3 h-2 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
        <div
          className={`h-full rounded-full bg-brand-500 transition-all duration-500 ${
            live ? "animate-pulse" : ""
          }`}
          style={{ width: `${progress.overall_percent}%` }}
        />
      </div>

      {/* Kaynak-bazlı */}
      <div className="space-y-2">
        {progress.sources.map((s) => {
          const isCur = progress.current === s.source;
          const barColor =
            s.status === "error"
              ? "bg-red-500"
              : s.status === "done"
              ? "bg-emerald-500"
              : "bg-brand-500";
          return (
            <div key={s.source}>
              <div className="flex items-center justify-between text-xs">
                <span className="flex items-center gap-1.5">
                  <span className="font-medium text-slate-700 dark:text-slate-200">
                    {s.source}
                  </span>
                  <span className="text-slate-400 dark:text-slate-500">
                    {STATUS_TR[s.status] ?? s.status}
                    {isCur && live ? " •" : ""}
                  </span>
                </span>
                <span className="tabular-nums text-slate-500 dark:text-slate-400">
                  {fmtInt(s.rows)}
                  {s.total ? ` / ${fmtInt(s.total)}` : ""}
                  {s.total ? ` · %${s.percent}` : ""}
                </span>
              </div>
              <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${barColor}`}
                  style={{
                    width: `${
                      s.status === "done" ? 100 : s.total ? s.percent : isCur ? 50 : 0
                    }%`,
                  }}
                />
              </div>
              {s.detail && (s.status === "running" || s.status === "error") && (
                <p className="mt-0.5 text-[11px] text-slate-400 dark:text-slate-500">
                  {s.detail}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function Ingest() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  const [sources, setSources] = useState<IngestSource[]>([]);
  const [runs, setRuns] = useState<IngestRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [running, setRunning] = useState(false);
  const [selectedRun, setSelectedRun] = useState<IngestRun | null>(null);
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const pollRef = useRef<number | null>(null);

  const loadRuns = () =>
    ingestApi.runs().then((r) => setRuns(r.data)).catch(() => {});

  const loadSources = () =>
    ingestApi.sources().then((r) => setSources(r.data)).catch((e) =>
      setError(errMsg(e))
    );

  useEffect(() => {
    loadSources();
    ingestApi
      .runs()
      .then((r) => {
        setRuns(r.data);
        // Açılışta zaten çalışan bir ingest varsa canlı izlemeyi başlat
        if (r.data.some((x) => x.status === "running" || x.status === "pending")) {
          startPolling();
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const startPolling = () => {
    if (pollRef.current) window.clearInterval(pollRef.current);
    pollRef.current = window.setInterval(async () => {
      const rs = await ingestApi.runs().then((r) => r.data).catch(() => null);
      if (rs) setRuns(rs);
      loadSources();
      const active = rs?.find(
        (r) => r.status === "running" || r.status === "pending"
      );
      if (active) {
        setRunning(true);
        try {
          const d = await ingestApi.run_detail(active.id);
          setSelectedRun(d.data);
        } catch {
          /* yok say */
        }
      } else {
        if (pollRef.current) window.clearInterval(pollRef.current);
        pollRef.current = null;
        setRunning(false);
        // bittiğinde seçili çalıştırmayı son haliyle tazele
        if (selectedRun) {
          ingestApi
            .run_detail(selectedRun.id)
            .then((d) => setSelectedRun(d.data))
            .catch(() => {});
        }
      }
    }, 2000);
  };

  const toggle = (s: string) =>
    setSelected((prev) =>
      prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]
    );

  const triggerRun = async (
    srcs: string[] | null,
    mode: "incremental" | "backfill",
    extra?: { from_date?: string; to_date?: string }
  ) => {
    setRunning(true);
    setError("");
    try {
      await ingestApi.run({ sources: srcs, mode, ...extra });
      loadRuns();
      startPolling();
      setTimeout(() => setRunning(false), 4000);
    } catch (e) {
      setError(errMsg(e));
      setRunning(false);
    }
  };

  const selectRun = async (run: IngestRun) => {
    try {
      const r = await ingestApi.run_detail(run.id);
      setSelectedRun(r.data);
    } catch {
      setSelectedRun(run);
    }
  };

  const inputCls =
    "rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/30 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100";

  return (
    <Layout
      title="Veri Çekme (Ingest)"
      actions={
        <button
          onClick={() => triggerRun(null, "incremental")}
          disabled={running}
          className="rounded-lg bg-brand-500 px-3 py-1.5 text-sm font-medium text-white transition hover:bg-brand-600 disabled:opacity-60"
        >
          {running ? "Çekiliyor..." : "Şimdi Çek (Tümü)"}
        </button>
      }
    >
      {error && (
        <div className="mb-4">
          <ErrorBanner message={error} onRetry={loadSources} />
        </div>
      )}

      {/* Eylem çubuğu */}
      <div className="mb-6 flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-card dark:border-slate-800 dark:bg-slate-900">
        <button
          onClick={() => triggerRun(selected, "incremental")}
          disabled={running || selected.length === 0}
          className="rounded-lg border border-brand-500 px-4 py-1.5 text-sm font-medium text-brand-600 transition hover:bg-brand-50 disabled:opacity-50 dark:text-brand-400 dark:hover:bg-brand-950/40"
        >
          Seçilenleri Çek ({selected.length})
        </button>

        {isAdmin && (
          <div className="ml-auto flex flex-wrap items-end gap-2">
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium text-slate-500 dark:text-slate-400">
                Başlangıç
              </label>
              <input
                type="date"
                value={from}
                onChange={(e) => setFrom(e.target.value)}
                className={inputCls}
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium text-slate-500 dark:text-slate-400">
                Bitiş
              </label>
              <input
                type="date"
                value={to}
                onChange={(e) => setTo(e.target.value)}
                className={inputCls}
              />
            </div>
            <button
              onClick={() =>
                triggerRun(selected.length ? selected : null, "backfill", {
                  from_date: from || undefined,
                  to_date: to || undefined,
                })
              }
              disabled={running || !from}
              className="rounded-lg border border-amber-500 px-4 py-1.5 text-sm font-medium text-amber-600 transition hover:bg-amber-50 disabled:opacity-50 dark:text-amber-400 dark:hover:bg-amber-950/30"
            >
              Backfill (Geriye Dönük)
            </button>
          </div>
        )}
      </div>

      {/* Kaynaklar tablosu */}
      <h2 className="mb-2 text-sm font-semibold text-slate-700 dark:text-slate-200">
        Kaynaklar
      </h2>
      {loading ? (
        <TableSkeleton rows={5} />
      ) : sources.length === 0 ? (
        <EmptyState title="Kaynak yok" message="Tanımlı veri kaynağı bulunamadı." />
      ) : (
        <div className="mb-8 overflow-auto rounded-xl border border-slate-200 bg-white shadow-card dark:border-slate-800 dark:bg-slate-900">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 dark:bg-slate-800/80">
              <tr className="text-left text-slate-600 dark:text-slate-300">
                <th className="px-3 py-2.5"></th>
                <th className="px-4 py-2.5 font-semibold">Kaynak</th>
                <th className="px-4 py-2.5 font-semibold">Tip</th>
                <th className="px-4 py-2.5 font-semibold">Hedef Tablo</th>
                <th className="px-4 py-2.5 font-semibold">Son Watermark</th>
                <th className="px-4 py-2.5 font-semibold">Son Çalışma</th>
                <th className="px-4 py-2.5 font-semibold">Durum</th>
                <th className="px-4 py-2.5 text-right font-semibold">Son Satır</th>
              </tr>
            </thead>
            <tbody>
              {sources.map((s) => (
                <tr
                  key={s.source}
                  className="border-b border-slate-100 transition hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-800/40"
                >
                  <td className="px-3 py-2.5">
                    <input
                      type="checkbox"
                      checked={selected.includes(s.source)}
                      onChange={() => toggle(s.source)}
                      className="accent-brand-500"
                    />
                  </td>
                  <td className="px-4 py-2.5 font-medium text-slate-800 dark:text-slate-100">
                    {s.source}
                  </td>
                  <td className="px-4 py-2.5 text-slate-500 dark:text-slate-400">
                    {s.kind}
                  </td>
                  <td className="px-4 py-2.5 font-mono text-xs text-slate-600 dark:text-slate-300">
                    {s.db}.{s.table}
                  </td>
                  <td className="px-4 py-2.5 text-xs text-slate-500 dark:text-slate-400">
                    {s.last_watermark ?? "—"}
                  </td>
                  <td className="px-4 py-2.5 text-xs text-slate-500 dark:text-slate-400">
                    {fmtTime(s.last_run_at)}
                  </td>
                  <td className="px-4 py-2.5">
                    <StatusBadge status={s.last_status} />
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums text-slate-700 dark:text-slate-200">
                    {formatValue(s.rows_last, "int")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Çalıştırma geçmişi */}
      <h2 className="mb-2 text-sm font-semibold text-slate-700 dark:text-slate-200">
        Çalıştırma Geçmişi
      </h2>
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="overflow-auto rounded-xl border border-slate-200 bg-white shadow-card dark:border-slate-800 dark:bg-slate-900">
          {runs.length === 0 ? (
            <EmptyState title="Çalıştırma yok" />
          ) : (
            <table className="min-w-full text-sm">
              <thead className="bg-slate-50 dark:bg-slate-800/80">
                <tr className="text-left text-slate-600 dark:text-slate-300">
                  <th className="px-4 py-2.5 font-semibold">Başlangıç</th>
                  <th className="px-4 py-2.5 font-semibold">Mod</th>
                  <th className="px-4 py-2.5 font-semibold">Durum</th>
                  <th className="px-4 py-2.5 text-right font-semibold">Satır</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((r) => (
                  <tr
                    key={r.id}
                    onClick={() => selectRun(r)}
                    className={`cursor-pointer border-b border-slate-100 transition hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-800/40 ${
                      selectedRun?.id === r.id ? "bg-slate-50 dark:bg-slate-800/40" : ""
                    }`}
                  >
                    <td className="px-4 py-2.5 text-xs text-slate-600 dark:text-slate-300">
                      {fmtTime(r.started_at)}
                    </td>
                    <td className="px-4 py-2.5 text-slate-500 dark:text-slate-400">
                      {r.mode}
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="flex items-center gap-2">
                        <StatusBadge status={r.status} />
                        {(r.status === "running" || r.status === "pending") &&
                          r.overall_percent != null && (
                            <span className="text-xs font-medium tabular-nums text-brand-600 dark:text-brand-400">
                              %{r.overall_percent}
                            </span>
                          )}
                      </div>
                    </td>
                    <td className="px-4 py-2.5 text-right tabular-nums text-slate-700 dark:text-slate-200">
                      {formatValue(r.rows_out, "int")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-card dark:border-slate-800 dark:bg-slate-900">
          <p className="mb-2 text-sm font-semibold text-slate-700 dark:text-slate-200">
            Çalıştırma Detayı
          </p>
          {selectedRun ? (
            <>
              <div className="mb-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500 dark:text-slate-400">
                <span>Mod: {selectedRun.mode}</span>
                <span>Tetikleyen: {selectedRun.triggered_by ?? "—"}</span>
                <span>Bitiş: {fmtTime(selectedRun.finished_at)}</span>
              </div>
              {selectedRun.progress && (
                <ProgressView
                  progress={selectedRun.progress}
                  live={selectedRun.status === "running" || selectedRun.status === "pending"}
                />
              )}
              {selectedRun.error && (
                <div className="my-2">
                  <ErrorBanner message={selectedRun.error} />
                </div>
              )}
              <pre className="mt-2 max-h-60 overflow-auto rounded-lg bg-slate-950 p-3 text-xs leading-relaxed text-slate-200">
                {selectedRun.log || "(çıktı yok)"}
              </pre>
            </>
          ) : (
            <p className="py-6 text-center text-sm text-slate-400">
              Detay için bir çalıştırma seçin.
            </p>
          )}
        </div>
      </div>
    </Layout>
  );
}
