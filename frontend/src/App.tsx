import { Navigate, Route, Routes } from "react-router-dom";
import { type ReactNode } from "react";
import { useAuth, canEdit } from "./lib/auth";
import Login from "./pages/Login";
import Dashboards from "./pages/Dashboards";
import DashboardView from "./pages/DashboardView";
import DashboardEditor from "./pages/DashboardEditor";
import Jobs from "./pages/Jobs";
import JobEditor from "./pages/JobEditor";
import Ingest from "./pages/Ingest";

function FullScreenLoader() {
  return (
    <div className="flex h-screen items-center justify-center bg-slate-50 dark:bg-slate-950">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
    </div>
  );
}

function Protected({ children }: { children: ReactNode }) {
  const { user, ready } = useAuth();
  if (!ready) return <FullScreenLoader />;
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function EditorsOnly({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  if (!canEdit(user?.role)) return <Navigate to="/" replace />;
  return <>{children}</>;
}

export default function App() {
  const { user, ready } = useAuth();

  return (
    <Routes>
      <Route
        path="/login"
        element={
          ready && user ? <Navigate to="/" replace /> : <Login />
        }
      />
      <Route
        path="/"
        element={
          <Protected>
            <Dashboards />
          </Protected>
        }
      />
      <Route
        path="/d/:key"
        element={
          <Protected>
            <DashboardView />
          </Protected>
        }
      />
      <Route
        path="/d/:key/edit"
        element={
          <Protected>
            <EditorsOnly>
              <DashboardEditor />
            </EditorsOnly>
          </Protected>
        }
      />
      <Route
        path="/jobs"
        element={
          <Protected>
            <EditorsOnly>
              <Jobs />
            </EditorsOnly>
          </Protected>
        }
      />
      <Route
        path="/jobs/:key"
        element={
          <Protected>
            <EditorsOnly>
              <JobEditor />
            </EditorsOnly>
          </Protected>
        }
      />
      <Route
        path="/ingest"
        element={
          <Protected>
            <EditorsOnly>
              <Ingest />
            </EditorsOnly>
          </Protected>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
