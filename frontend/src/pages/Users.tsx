import { useEffect, useState } from "react";
import Layout from "../components/Layout";
import { EmptyState, ErrorBanner, TableSkeleton } from "../components/States";
import { usersApi, errMsg, type AdminUser, type Role } from "../lib/api";
import { useAuth } from "../lib/auth";

const ROLES: Role[] = ["admin", "analyst", "viewer"];
const ROLE_LABEL: Record<Role, string> = {
  admin: "Yönetici",
  analyst: "Analist",
  viewer: "İzleyici",
};

const inputCls =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/30 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100";

export default function Users() {
  const { user: me } = useAuth();
  const [items, setItems] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [form, setForm] = useState({
    username: "",
    full_name: "",
    password: "",
    role: "viewer" as Role,
  });

  const load = () => {
    setLoading(true);
    setError("");
    usersApi
      .list()
      .then((r) => setItems(r.data))
      .catch((e) => setError(errMsg(e)))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      await usersApi.create(form);
      setForm({ username: "", full_name: "", password: "", role: "viewer" });
      setCreating(false);
      load();
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setSaving(false);
    }
  };

  const patch = async (
    u: AdminUser,
    body: Partial<{ role: Role; is_active: boolean }>
  ) => {
    setBusyId(u.id);
    setError("");
    try {
      await usersApi.update(u.id, body);
      load();
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setBusyId(null);
    }
  };

  const resetPw = async (u: AdminUser) => {
    const pw = window.prompt(`"${u.username}" için yeni parola (en az 6 karakter):`);
    if (pw == null) return;
    setBusyId(u.id);
    setError("");
    try {
      await usersApi.setPassword(u.id, pw);
      window.alert(`"${u.username}" parolası güncellendi.`);
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setBusyId(null);
    }
  };

  const remove = async (u: AdminUser) => {
    if (
      !window.confirm(
        `"${u.username}" kullanıcısı kalıcı olarak silinsin mi? Bu işlem geri alınamaz.`
      )
    )
      return;
    setBusyId(u.id);
    setError("");
    try {
      await usersApi.remove(u.id);
      load();
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setBusyId(null);
    }
  };

  return (
    <Layout
      title="Kullanıcılar"
      actions={
        <button
          onClick={() => setCreating((c) => !c)}
          className="rounded-lg bg-brand-500 px-3 py-1.5 text-sm font-medium text-white transition hover:bg-brand-600"
        >
          Yeni Kullanıcı
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
            placeholder="Kullanıcı adı"
            autoComplete="off"
            value={form.username}
            onChange={(e) => setForm({ ...form, username: e.target.value })}
            className={inputCls}
          />
          <input
            placeholder="Ad Soyad (opsiyonel)"
            value={form.full_name}
            onChange={(e) => setForm({ ...form, full_name: e.target.value })}
            className={inputCls}
          />
          <input
            required
            type="password"
            placeholder="Parola (en az 6 karakter)"
            autoComplete="new-password"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            className={inputCls}
          />
          <select
            value={form.role}
            onChange={(e) => setForm({ ...form, role: e.target.value as Role })}
            className={inputCls}
          >
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {ROLE_LABEL[r]}
              </option>
            ))}
          </select>
          <div className="flex gap-2 sm:col-span-2">
            <button
              type="submit"
              disabled={saving}
              className="rounded-lg bg-brand-500 px-4 py-1.5 text-sm font-medium text-white transition hover:bg-brand-600 disabled:opacity-60"
            >
              {saving ? "Oluşturuluyor..." : "Oluştur"}
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

      {error && !loading && <div className="mb-4"><ErrorBanner message={error} onRetry={load} /></div>}

      {loading ? (
        <TableSkeleton rows={5} />
      ) : items.length === 0 ? (
        <EmptyState
          title="Kullanıcı yok"
          message="İlk kullanıcıyı oluşturmak için 'Yeni Kullanıcı'ya tıklayın."
        />
      ) : (
        <div className="overflow-auto rounded-xl border border-slate-200 bg-white shadow-card dark:border-slate-800 dark:bg-slate-900">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 dark:bg-slate-800/80">
              <tr className="text-left text-slate-600 dark:text-slate-300">
                <th className="px-4 py-2.5 font-semibold">Kullanıcı</th>
                <th className="px-4 py-2.5 font-semibold">Rol</th>
                <th className="px-4 py-2.5 font-semibold">Durum</th>
                <th className="px-4 py-2.5 text-right font-semibold">İşlemler</th>
              </tr>
            </thead>
            <tbody>
              {items.map((u) => {
                const self = u.id === me?.id;
                const busy = busyId === u.id;
                return (
                  <tr
                    key={u.id}
                    className="border-b border-slate-100 dark:border-slate-800"
                  >
                    <td className="px-4 py-2.5">
                      <div className="font-medium text-slate-800 dark:text-slate-100">
                        {u.username}
                        {self && (
                          <span className="ml-2 rounded bg-brand-500/10 px-1.5 py-0.5 text-xs text-brand-600 dark:text-brand-300">
                            siz
                          </span>
                        )}
                      </div>
                      {u.full_name && (
                        <span className="text-xs text-slate-400">{u.full_name}</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5">
                      <select
                        value={u.role}
                        disabled={busy}
                        onChange={(e) =>
                          patch(u, { role: e.target.value as Role })
                        }
                        className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-sm outline-none focus:border-brand-500 disabled:opacity-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                      >
                        {ROLES.map((r) => (
                          <option key={r} value={r}>
                            {ROLE_LABEL[r]}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="px-4 py-2.5">
                      <button
                        onClick={() => patch(u, { is_active: !u.is_active })}
                        disabled={busy || self}
                        title={self ? "Kendi hesabınızı pasifleştiremezsiniz" : "Durumu değiştir"}
                        className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium transition disabled:cursor-not-allowed disabled:opacity-60 ${
                          u.is_active
                            ? "bg-emerald-100 text-emerald-700 hover:bg-emerald-200 dark:bg-emerald-950/50 dark:text-emerald-400"
                            : "bg-slate-100 text-slate-500 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-400"
                        }`}
                      >
                        {u.is_active ? "Aktif" : "Pasif"}
                      </button>
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="flex justify-end gap-2">
                        <button
                          onClick={() => resetPw(u)}
                          disabled={busy}
                          className="rounded-lg border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-600 transition hover:bg-slate-50 disabled:opacity-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
                        >
                          Parola
                        </button>
                        <button
                          onClick={() => remove(u)}
                          disabled={busy || self}
                          title={self ? "Kendi hesabınızı silemezsiniz" : "Kullanıcıyı sil"}
                          className="rounded-lg border border-red-300 px-2.5 py-1 text-xs font-medium text-red-600 transition hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-red-900/60 dark:text-red-400 dark:hover:bg-red-950/30"
                        >
                          Sil
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Layout>
  );
}
