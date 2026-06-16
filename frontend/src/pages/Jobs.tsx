import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../components/Layout";
import {
  EmptyState,
  ErrorBanner,
  TableSkeleton,
} from "../components/States";
import { jobsApi, errMsg, type Job } from "../lib/api";

export default function Jobs() {
  const navigate = useNavigate();
  const [items, setItems] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    key: "",
    title: "",
    description: "",
    schedule: "",
  });

  const load = () => {
    setLoading(true);
    setError("");
    jobsApi
      .list()
      .then((r) => setItems(r.data))
      .catch((e) => setError(errMsg(e)))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await jobsApi.create(form);
      navigate(`/jobs/${form.key}`);
    } catch (err) {
      setError(errMsg(err));
      setSaving(false);
    }
  };

  const inputCls =
    "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/30 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100";

  return (
    <Layout
      title="İşler (Jobs)"
      actions={
        <button
          onClick={() => setCreating((c) => !c)}
          className="rounded-lg bg-brand-500 px-3 py-1.5 text-sm font-medium text-white transition hover:bg-brand-600"
        >
          Yeni Job
        </button>
      }
    >
      {creating && (
        <form
          onSubmit={create}
          className="mb-6 grid gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-card dark:border-slate-800 dark:bg-slate-900 sm:grid-cols-2"
        >
          <input
            required
            placeholder="anahtar (key)"
            value={form.key}
            onChange={(e) => setForm({ ...form, key: e.target.value })}
            className={inputCls}
          />
          <input
            required
            placeholder="Başlık"
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
            className={inputCls}
          />
          <input
            placeholder="Açıklama"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            className={inputCls}
          />
          <input
            placeholder="Zamanlama (cron) — ör. 0 6 * * *"
            value={form.schedule}
            onChange={(e) => setForm({ ...form, schedule: e.target.value })}
            className={inputCls}
          />
          <div className="sm:col-span-2 flex gap-2">
            <button
              type="submit"
              disabled={saving}
              className="rounded-lg bg-brand-500 px-4 py-1.5 text-sm font-medium text-white transition hover:bg-brand-600 disabled:opacity-60"
            >
              {saving ? "Oluşturuluyor..." : "Oluştur ve Düzenle"}
            </button>
            <button
              type="button"
              onClick={() => setCreating(false)}
              className="rounded-lg border border-slate-300 px-4 py-1.5 text-sm dark:border-slate-700"
            >
              İptal
            </button>
          </div>
        </form>
      )}

      {loading ? (
        <TableSkeleton rows={6} />
      ) : error ? (
        <ErrorBanner message={error} onRetry={load} />
      ) : items.length === 0 ? (
        <EmptyState
          title="Henüz job yok"
          message="Ham veriyi türetilmiş veriye dönüştürmek için ilk job'ı oluşturun."
        />
      ) : (
        <div className="overflow-auto rounded-xl border border-slate-200 bg-white shadow-card dark:border-slate-800 dark:bg-slate-900">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 dark:bg-slate-800/80">
              <tr className="text-left text-slate-600 dark:text-slate-300">
                <th className="px-4 py-2.5 font-semibold">Anahtar</th>
                <th className="px-4 py-2.5 font-semibold">Başlık</th>
                <th className="px-4 py-2.5 font-semibold">Zamanlama</th>
                <th className="px-4 py-2.5 font-semibold">Durum</th>
              </tr>
            </thead>
            <tbody>
              {items.map((j) => (
                <tr
                  key={j.key}
                  onClick={() => navigate(`/jobs/${j.key}`)}
                  className="cursor-pointer border-b border-slate-100 transition hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-800/40"
                >
                  <td className="px-4 py-2.5 font-mono text-xs text-slate-700 dark:text-slate-200">
                    {j.key}
                  </td>
                  <td className="px-4 py-2.5 text-slate-800 dark:text-slate-100">
                    {j.title}
                    {j.description && (
                      <span className="block text-xs text-slate-400">
                        {j.description}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-2.5 font-mono text-xs text-slate-500 dark:text-slate-400">
                    {j.schedule || "—"}
                  </td>
                  <td className="px-4 py-2.5">
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                        j.enabled
                          ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-400"
                          : "bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400"
                      }`}
                    >
                      {j.enabled ? "Aktif" : "Pasif"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Layout>
  );
}
