import { useState, type ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { useAuth, canEdit } from "../lib/auth";
import { useTheme } from "../lib/theme";
import {
  DashboardIcon,
  JobsIcon,
  IngestIcon,
  UsersIcon,
  SunIcon,
  MoonIcon,
  LogoutIcon,
  MenuIcon,
} from "./icons";

interface NavItem {
  to: string;
  label: string;
  icon: typeof DashboardIcon;
  editorsOnly?: boolean;
  adminOnly?: boolean;
}

const NAV: NavItem[] = [
  { to: "/", label: "Dashboardlar", icon: DashboardIcon },
  { to: "/jobs", label: "İşler", icon: JobsIcon, editorsOnly: true },
  { to: "/ingest", label: "Veri Çekme", icon: IngestIcon, editorsOnly: true },
  { to: "/users", label: "Kullanıcılar", icon: UsersIcon, adminOnly: true },
];

const ROLE_LABEL: Record<string, string> = {
  admin: "Yönetici",
  analyst: "Analist",
  viewer: "İzleyici",
};

export default function Layout({
  title,
  children,
  actions,
}: {
  title: string;
  children: ReactNode;
  actions?: ReactNode;
}) {
  const { user, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const [open, setOpen] = useState(false);
  const editor = canEdit(user?.role);
  const isAdmin = user?.role === "admin";
  const items = NAV.filter(
    (i) => (!i.editorsOnly || editor) && (!i.adminOnly || isAdmin)
  );

  const Sidebar = (
    <aside className="flex h-full w-64 flex-col border-r border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-center gap-2 px-5 py-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-500 text-white">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
            <path d="M4 14l5-5 4 4 7-7" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M4 20h16" strokeLinecap="round" />
          </svg>
        </div>
        <div>
          <p className="text-sm font-bold leading-tight text-slate-900 dark:text-slate-50">
            İşler Platform
          </p>
          <p className="text-xs text-slate-400">Veri Platformu</p>
        </div>
      </div>

      <nav className="flex-1 space-y-1 px-3 py-2">
        {items.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              onClick={() => setOpen(false)}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
                  isActive
                    ? "bg-brand-500/10 text-brand-600 dark:bg-brand-500/15 dark:text-brand-300"
                    : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
                }`
              }
            >
              <Icon />
              {item.label}
            </NavLink>
          );
        })}
      </nav>

      <div className="border-t border-slate-200 p-3 dark:border-slate-800">
        <div className="mb-2 px-2">
          <p className="truncate text-sm font-medium text-slate-800 dark:text-slate-100">
            {user?.full_name || user?.username}
          </p>
          <p className="text-xs text-slate-400">
            {ROLE_LABEL[user?.role ?? ""] ?? user?.role}
          </p>
        </div>
        <button
          onClick={logout}
          className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-slate-600 transition hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
        >
          <LogoutIcon />
          Çıkış
        </button>
      </div>
    </aside>
  );

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50 dark:bg-slate-950">
      {/* Masaüstü sidebar */}
      <div className="hidden md:block">{Sidebar}</div>

      {/* Mobil sidebar */}
      {open && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div
            className="absolute inset-0 bg-black/40"
            onClick={() => setOpen(false)}
          />
          <div className="absolute left-0 top-0 h-full">{Sidebar}</div>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-3 border-b border-slate-200 bg-white px-4 py-3 dark:border-slate-800 dark:bg-slate-900 md:px-6">
          <button
            onClick={() => setOpen(true)}
            className="rounded-lg p-1.5 text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800 md:hidden"
          >
            <MenuIcon />
          </button>
          <h1 className="truncate text-lg font-semibold text-slate-900 dark:text-slate-50">
            {title}
          </h1>
          <div className="ml-auto flex items-center gap-2">
            {actions}
            <span className="hidden rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300 sm:inline">
              {ROLE_LABEL[user?.role ?? ""] ?? user?.role}
            </span>
            <button
              onClick={toggle}
              title="Tema değiştir"
              className="rounded-lg p-1.5 text-slate-600 transition hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
            >
              {theme === "dark" ? <SunIcon /> : <MoonIcon />}
            </button>
          </div>
        </header>

        <main className="flex-1 overflow-auto p-4 md:p-6">{children}</main>
      </div>
    </div>
  );
}
