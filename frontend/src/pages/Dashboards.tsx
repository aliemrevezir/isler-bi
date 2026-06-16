import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import Layout from "../components/Layout";
import {
  CardSkeleton,
  EmptyState,
  ErrorBanner,
} from "../components/States";
import { dashApi, errMsg, type Dashboard } from "../lib/api";
import { useAuth, canEdit } from "../lib/auth";

function fmtDate(s?: string) {
  if (!s) return "—";
  try {
    return new Date(s).toLocaleDateString("tr-TR", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  } catch {
    return s;
  }
}

export default function Dashboards() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const editor = canEdit(user?.role);
  const [items, setItems] = useState<Dashboard[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ key: "", title: "", description: "" });
  const [saving, setSaving] = useState(false);

  const load = () => {
    setLoading(true);
    setError("");
    dashApi
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
      await dashApi.create(form);
      navigate(`/d/${form.key}/edit`);
    } catch (err) {
      setError(errMsg(err));
      setSaving(false);
    }
  };

  const inputCls =
    "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/30 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100";

  return (
    <Layout
      title="Dashboardlar"
      actions={
        editor ? (
          <button
            onClick={() => setCreating((c) => !c)}
            className="rounded-lg bg-brand-500 px-3 py-1.5 text-sm font-medium text-white transition hover:bg-brand-600"
          >
            Yeni Dashboard
          </button>
        ) : undefined
      }
    >
      {creating && editor && (
        <form
          onSubmit={create}
          className="mb-6 grid gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-card dark:border-slate-800 dark:bg-slate-900 sm:grid-cols-3"
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
          <div className="sm:col-span-3 flex gap-2">
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
        <CardSkeleton rows={6} />
      ) : error ? (
        <ErrorBanner message={error} onRetry={load} />
      ) : items.length === 0 ? (
        <EmptyState
          title="Henüz dashboard yok"
          message="Verilerinizi görselleştirmek için ilk dashboard'ı oluşturun."
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((d) => (
            <div
              key={d.key}
              className="group flex flex-col rounded-xl border border-slate-200 bg-white p-5 shadow-card transition hover:border-brand-300 hover:shadow-md dark:border-slate-800 dark:bg-slate-900 dark:hover:border-brand-700"
            >
              <Link to={`/d/${d.key}`} className="flex-1">
                <h3 className="font-semibold text-slate-900 group-hover:text-brand-600 dark:text-slate-50 dark:group-hover:text-brand-400">
                  {d.title}
                </h3>
                {d.description && (
                  <p className="mt-1 line-clamp-2 text-sm text-slate-500 dark:text-slate-400">
                    {d.description}
                  </p>
                )}
              </Link>
              <div className="mt-4 flex items-center justify-between border-t border-slate-100 pt-3 text-xs text-slate-400 dark:border-slate-800">
                <span>Güncellendi: {fmtDate(d.updated_at)}</span>
                {editor && (
                  <Link
                    to={`/d/${d.key}/edit`}
                    className="font-medium text-brand-600 hover:underline dark:text-brand-400"
                  >
                    Düzenle
                  </Link>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </Layout>
  );
}
