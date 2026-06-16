import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import Layout from "../components/Layout";
import CodeEditor from "../components/CodeEditor";
import {
  EmptyState,
  ErrorBanner,
  Skeleton,
  StatusBadge,
} from "../components/States";
import { PlayIcon } from "../components/icons";
import {
  jobsApi,
  tablesApi,
  errMsg,
  type JobRun,
  type VersionMeta,
  type TableInfo,
} from "../lib/api";

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

/** Başlangıç–bitiş arası süreyi insan-okur biçimde verir. */
function fmtDuration(start?: string | null, end?: string | null) {
  if (!start) return "—";
  const s = new Date(start).getTime();
  const e = end ? new Date(end).getTime() : Date.now();
  const ms = e - s;
  if (!Number.isFinite(ms) || ms < 0) return "—";
  if (ms < 1000) return `${ms} ms`;
  const sec = ms / 1000;
  if (sec < 60) return `${sec.toFixed(1)} sn`;
  const m = Math.floor(sec / 60);
  return `${m} dk ${Math.round(sec % 60)} sn`;
}

/** Canlı job ilerlemesi: yüzde çubuğu + güncel mesaj + adım sayacı. */
function JobProgressView({ run }: { run: JobRun }) {
  const live = run.status === "running" || run.status === "pending";
  const pct = run.progress?.percent ?? (run.status === "success" ? 100 : 0);
  // Yüzde 0 ve canlı ise belirsiz (indeterminate) görünüm — sürekli akış.
  const indeterminate = live && pct === 0;
  const barColor =
    run.status === "error"
      ? "bg-red-500"
      : run.status === "success"
      ? "bg-emerald-500"
      : "bg-brand-500";
  return (
    <div className="mb-3 rounded-lg border border-slate-200 bg-slate-50 p-3 dark:border-slate-800 dark:bg-slate-800/40">
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="font-semibold text-slate-700 dark:text-slate-200">
          {live ? "İlerleme (canlı)" : "İlerleme"}
          {run.progress?.total ? (
            <span className="ml-1.5 font-normal text-slate-400">
              · adım {run.progress.step}/{run.progress.total}
            </span>
          ) : null}
        </span>
        {!indeterminate && (
          <span className="tabular-nums font-medium text-brand-600 dark:text-brand-400">
            %{pct}
          </span>
        )}
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
        <div
          className={`h-full rounded-full transition-all duration-500 ${barColor} ${
            indeterminate ? "w-1/3 animate-pulse" : live ? "animate-pulse" : ""
          }`}
          style={indeterminate ? undefined : { width: `${pct}%` }}
        />
      </div>
      {run.progress?.message && (
        <p className="mt-1.5 text-xs text-slate-500 dark:text-slate-400">
          {run.progress.message}
        </p>
      )}
    </div>
  );
}

export default function JobEditor() {
  const { key = "" } = useParams();
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [versions, setVersions] = useState<VersionMeta[]>([]);
  const [runs, setRuns] = useState<JobRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<JobRun | null>(null);
  const [running, setRunning] = useState(false);
  const [tables, setTables] = useState<TableInfo[]>([]);
  const [openTable, setOpenTable] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  const loadVersions = () =>
    jobsApi.versions(key).then((r) => setVersions(r.data)).catch(() => {});
  const loadRuns = () =>
    jobsApi.runs(key).then((r) => setRuns(r.data)).catch(() => {});

  useEffect(() => {
    setLoading(true);
    jobsApi
      .getCode(key)
      .then((r) => setCode(r.data.code ?? ""))
      .catch((e) => setError(errMsg(e)))
      .finally(() => setLoading(false));
    loadVersions();
    // Açılışta zaten çalışan bir kayıt varsa onu seç ve canlı izlemeyi başlat.
    jobsApi
      .runs(key)
      .then((r) => {
        setRuns(r.data);
        const active = r.data.find(
          (x) => x.status === "running" || x.status === "pending"
        );
        if (active) {
          setRunning(true);
          jobsApi.runDetail(active.id).then((d) => setSelectedRun(d.data)).catch(() => {});
          startPolling(active.id);
        }
      })
      .catch(() => {});
    tablesApi.list().then((r) => setTables(r.data)).catch(() => {});
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const startPolling = (runId: number) => {
    if (pollRef.current) window.clearInterval(pollRef.current);
    pollRef.current = window.setInterval(async () => {
      try {
        const r = await jobsApi.runDetail(runId);
        setSelectedRun(r.data);
        if (r.data.status === "success" || r.data.status === "error") {
          if (pollRef.current) window.clearInterval(pollRef.current);
          pollRef.current = null;
          setRunning(false);
          loadRuns();
        }
      } catch {
        if (pollRef.current) window.clearInterval(pollRef.current);
        pollRef.current = null;
        setRunning(false);
      }
    }, 2000);
  };

  const save = async () => {
    setSaving(true);
    setError("");
    try {
      await jobsApi.putCode(key, code);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
      loadVersions();
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setSaving(false);
    }
  };

  const run = async () => {
    setRunning(true);
    setError("");
    try {
      const r = await jobsApi.run(key);
      const runId = r.data.run_id;
      const detail = await jobsApi.runDetail(runId);
      setSelectedRun(detail.data);
      loadRuns();
      startPolling(runId);
    } catch (e) {
      setError(errMsg(e));
      setRunning(false);
    }
  };

  const loadVersion = async (vid: string) => {
    if (!vid) return;
    try {
      const r = await jobsApi.version(key, Number(vid));
      setCode(r.data.code);
    } catch (e) {
      setError(errMsg(e));
    }
  };

  const selectRun = async (run: JobRun) => {
    try {
      const r = await jobsApi.runDetail(run.id);
      setSelectedRun(r.data);
    } catch {
      setSelectedRun(run);
    }
  };

  return (
    <Layout
      title={`Job: ${key}`}
      actions={
        <div className="flex items-center gap-2">
          {versions.length > 0 && (
            <select
              onChange={(e) => loadVersion(e.target.value)}
              defaultValue=""
              className="rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            >
              <option value="">Versiyon geçmişi</option>
              {versions.map((v) => (
                <option key={v.id} value={v.id}>
                  #{v.id} · {fmtTime(v.created_at)}
                </option>
              ))}
            </select>
          )}
          <Link
            to="/jobs"
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm dark:border-slate-700"
          >
            Liste
          </Link>
          <button
            onClick={save}
            disabled={saving}
            className="rounded-lg border border-brand-500 px-3 py-1.5 text-sm font-medium text-brand-600 transition hover:bg-brand-50 disabled:opacity-60 dark:text-brand-400 dark:hover:bg-brand-950/40"
          >
            {saved ? "Kaydedildi ✓" : saving ? "Kaydediliyor..." : "Kaydet"}
          </button>
          <button
            onClick={run}
            disabled={running}
            className="flex items-center gap-1.5 rounded-lg bg-brand-500 px-3 py-1.5 text-sm font-medium text-white transition hover:bg-brand-600 disabled:opacity-60"
          >
            <PlayIcon width={14} height={14} />
            {running ? "Çalışıyor..." : "Çalıştır"}
          </button>
        </div>
      }
    >
      {error && (
        <div className="mb-4">
          <ErrorBanner message={error} />
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-4">
        {/* Editör */}
        <div className="lg:col-span-3">
          <div className="h-[55vh] min-h-[320px]">
            {loading ? (
              <Skeleton className="h-full w-full" />
            ) : (
              <CodeEditor value={code} onChange={setCode} language="python" />
            )}
          </div>

          {/* Çalıştırma çıktısı */}
          <div className="mt-4 rounded-xl border border-slate-200 bg-white p-4 shadow-card dark:border-slate-800 dark:bg-slate-900">
            <div className="mb-2 flex items-center gap-2">
              <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">
                Çalıştırma Çıktısı
              </p>
              {selectedRun && <StatusBadge status={selectedRun.status} />}
            </div>
            {selectedRun ? (
              <>
                <div className="mb-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500 dark:text-slate-400">
                  <span>Tetikleyen: {selectedRun.triggered_by ?? "—"}</span>
                  <span>Süre: {fmtDuration(selectedRun.started_at, selectedRun.finished_at)}</span>
                  <span>Satır: {fmtInt(selectedRun.rows_out)}</span>
                </div>
                {(selectedRun.progress ||
                  selectedRun.status === "running" ||
                  selectedRun.status === "pending") && (
                  <JobProgressView run={selectedRun} />
                )}
                {selectedRun.error && (
                  <div className="mb-2">
                    <ErrorBanner message={selectedRun.error} />
                  </div>
                )}
                <pre className="max-h-64 overflow-auto rounded-lg bg-slate-950 p-3 text-xs leading-relaxed text-slate-200">
                  {selectedRun.log || "(çıktı yok)"}
                </pre>
              </>
            ) : (
              <p className="py-4 text-center text-sm text-slate-400">
                Çalıştırın veya geçmişten bir kayıt seçin.
              </p>
            )}
          </div>
        </div>

        {/* Yan panel */}
        <div className="space-y-4">
          {/* Tablo introspection */}
          <div className="rounded-xl border border-slate-200 bg-white p-3 shadow-card dark:border-slate-800 dark:bg-slate-900">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
              Tablolar
            </p>
            <div className="max-h-60 space-y-1 overflow-auto">
              {tables.length === 0 && (
                <p className="text-xs text-slate-400">Tablo bulunamadı.</p>
              )}
              {tables.map((t) => {
                const id = `${t.schema}.${t.table}`;
                const open = openTable === id;
                return (
                  <div key={id}>
                    <button
                      onClick={() => setOpenTable(open ? null : id)}
                      className="w-full rounded-md px-2 py-1 text-left font-mono text-xs text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800"
                    >
                      {id}
                    </button>
                    {open && (
                      <div className="ml-2 border-l border-slate-200 pl-2 dark:border-slate-700">
                        {t.columns.map((c) => (
                          <p
                            key={c.name}
                            className="py-0.5 font-mono text-[11px] text-slate-500 dark:text-slate-400"
                          >
                            {c.name}{" "}
                            <span className="text-slate-400 dark:text-slate-500">
                              {c.type}
                            </span>
                          </p>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Çalıştırma geçmişi */}
          <div className="rounded-xl border border-slate-200 bg-white p-3 shadow-card dark:border-slate-800 dark:bg-slate-900">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
              Geçmiş
            </p>
            {runs.length === 0 ? (
              <EmptyState title="Çalıştırma yok" />
            ) : (
              <div className="max-h-72 space-y-1 overflow-auto">
                {runs.map((r) => {
                  const live = r.status === "running" || r.status === "pending";
                  return (
                    <button
                      key={r.id}
                      onClick={() => selectRun(r)}
                      className={`flex w-full flex-col gap-1 rounded-md px-2 py-1.5 text-left text-xs transition hover:bg-slate-100 dark:hover:bg-slate-800 ${
                        selectedRun?.id === r.id
                          ? "bg-slate-100 dark:bg-slate-800"
                          : ""
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-slate-500 dark:text-slate-400">
                          {fmtTime(r.started_at)}
                        </span>
                        <span className="flex items-center gap-1.5">
                          {live && r.percent != null && r.percent > 0 && (
                            <span className="tabular-nums font-medium text-brand-600 dark:text-brand-400">
                              %{r.percent}
                            </span>
                          )}
                          <StatusBadge status={r.status} />
                        </span>
                      </div>
                      <span className="text-[11px] text-slate-400 dark:text-slate-500">
                        {fmtDuration(r.started_at, r.finished_at)}
                        {r.rows_out != null && ` · ${fmtInt(r.rows_out)} satır`}
                      </span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </Layout>
  );
}
