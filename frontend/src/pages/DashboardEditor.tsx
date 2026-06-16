import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import Layout from "../components/Layout";
import CodeEditor from "../components/CodeEditor";
import KpiCards from "../components/KpiCards";
import Chart from "../components/Chart";
import DataTable from "../components/DataTable";
import { EmptyState, ErrorBanner, Skeleton } from "../components/States";
import {
  dashApi,
  errMsg,
  type DashResult,
  type VersionMeta,
} from "../lib/api";

export default function DashboardEditor() {
  const { key = "" } = useParams();
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testError, setTestError] = useState("");
  const [preview, setPreview] = useState<DashResult | null>(null);
  const [versions, setVersions] = useState<VersionMeta[]>([]);
  const [saved, setSaved] = useState(false);

  const loadVersions = () => {
    dashApi.versions(key).then((r) => setVersions(r.data)).catch(() => {});
  };

  useEffect(() => {
    setLoading(true);
    dashApi
      .getCode(key)
      .then((r) => setCode(r.data.code ?? ""))
      .catch((e) => setError(errMsg(e)))
      .finally(() => setLoading(false));
    loadVersions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const test = async () => {
    setTesting(true);
    setTestError("");
    try {
      const r = await dashApi.test(key, code, {});
      setPreview(r.data.result);
    } catch (e) {
      setTestError(errMsg(e));
      setPreview(null);
    } finally {
      setTesting(false);
    }
  };

  const save = async () => {
    setSaving(true);
    setError("");
    try {
      await dashApi.putCode(key, code);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
      loadVersions();
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setSaving(false);
    }
  };

  const loadVersion = async (vid: string) => {
    if (!vid) return;
    try {
      const r = await dashApi.version(key, Number(vid));
      setCode(r.data.code);
    } catch (e) {
      setError(errMsg(e));
    }
  };

  return (
    <Layout
      title={`Düzenle: ${key}`}
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
                  #{v.id} · {new Date(v.created_at).toLocaleString("tr-TR")}
                </option>
              ))}
            </select>
          )}
          <Link
            to={`/d/${key}`}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm dark:border-slate-700"
          >
            Görüntüle
          </Link>
          <button
            onClick={test}
            disabled={testing}
            className="rounded-lg border border-brand-500 px-3 py-1.5 text-sm font-medium text-brand-600 transition hover:bg-brand-50 disabled:opacity-60 dark:text-brand-400 dark:hover:bg-brand-950/40"
          >
            {testing ? "Test ediliyor..." : "Test Et"}
          </button>
          <button
            onClick={save}
            disabled={saving}
            className="rounded-lg bg-brand-500 px-3 py-1.5 text-sm font-medium text-white transition hover:bg-brand-600 disabled:opacity-60"
          >
            {saved ? "Kaydedildi ✓" : saving ? "Kaydediliyor..." : "Kaydet"}
          </button>
        </div>
      }
    >
      {error && (
        <div className="mb-4">
          <ErrorBanner message={error} />
        </div>
      )}
      <div className="grid h-[calc(100vh-9rem)] grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="min-h-[300px]">
          {loading ? (
            <Skeleton className="h-full w-full" />
          ) : (
            <CodeEditor value={code} onChange={setCode} language="python" />
          )}
        </div>

        <div className="overflow-auto rounded-xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-800 dark:bg-slate-950/40">
          <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-400">
            Önizleme
          </p>
          {testError ? (
            <ErrorBanner message={testError} />
          ) : preview ? (
            <div className="space-y-4">
              <KpiCards kpis={preview.kpis} />
              {preview.charts.map((c, i) => (
                <Chart key={i} spec={c} />
              ))}
              <DataTable
                columns={preview.table.columns}
                rows={preview.table.rows}
              />
            </div>
          ) : (
            <EmptyState
              title="Önizleme yok"
              message="Kodu çalıştırmak için 'Test Et' butonuna basın."
            />
          )}
        </div>
      </div>
    </Layout>
  );
}
