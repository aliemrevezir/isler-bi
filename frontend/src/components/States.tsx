import type { ReactNode } from "react";

export function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800 ${className}`}
    />
  );
}

export function CardSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="rounded-xl border border-slate-200 bg-white p-5 shadow-card dark:border-slate-800 dark:bg-slate-900"
        >
          <Skeleton className="mb-3 h-4 w-1/3" />
          <Skeleton className="mb-2 h-8 w-2/3" />
          <Skeleton className="h-3 w-full" />
        </div>
      ))}
    </div>
  );
}

export function TableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-10 w-full" />
      ))}
    </div>
  );
}

export function EmptyState({
  title = "Veri yok",
  message,
  icon,
  action,
}: {
  title?: string;
  message?: string;
  icon?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-white px-6 py-14 text-center dark:border-slate-700 dark:bg-slate-900">
      <div className="mb-3 text-slate-400 dark:text-slate-500">
        {icon ?? (
          <svg
            width="40"
            height="40"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
          >
            <path
              d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        )}
      </div>
      <p className="text-base font-medium text-slate-700 dark:text-slate-200">
        {title}
      </p>
      {message && (
        <p className="mt-1 max-w-md text-sm text-slate-500 dark:text-slate-400">
          {message}
        </p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorBanner({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex items-start gap-3 rounded-xl border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-300">
      <svg
        className="mt-0.5 shrink-0"
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
      >
        <circle cx="12" cy="12" r="9" />
        <path d="M12 8v4M12 16h.01" strokeLinecap="round" />
      </svg>
      <div className="flex-1">
        <p className="font-medium">Bir hata oluştu</p>
        <p className="mt-0.5 break-words opacity-90">{message}</p>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="rounded-md border border-red-300 px-2 py-1 text-xs font-medium transition hover:bg-red-100 dark:border-red-800 dark:hover:bg-red-900/40"
        >
          Yeniden dene
        </button>
      )}
    </div>
  );
}

export function StatusBadge({ status }: { status?: string | null }) {
  const s = (status ?? "").toLowerCase();
  let cls =
    "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300";
  let label = status ?? "—";
  if (s === "success" || s === "ok") {
    cls = "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-400";
    label = "Başarılı";
  } else if (s === "error" || s === "failed") {
    cls = "bg-red-100 text-red-700 dark:bg-red-950/50 dark:text-red-400";
    label = "Hata";
  } else if (s === "running") {
    cls = "bg-blue-100 text-blue-700 dark:bg-blue-950/50 dark:text-blue-400";
    label = "Çalışıyor";
  } else if (s === "pending" || s === "queued") {
    cls = "bg-amber-100 text-amber-700 dark:bg-amber-950/50 dark:text-amber-400";
    label = "Beklemede";
  }
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}
    >
      {label}
    </span>
  );
}
