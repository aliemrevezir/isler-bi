import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import Layout from "../components/Layout";
import Filters from "../components/Filters";
import KpiCards from "../components/KpiCards";
import Chart from "../components/Chart";
import DataTable from "../components/DataTable";
import {
  CardSkeleton,
  EmptyState,
  ErrorBanner,
  TableSkeleton,
} from "../components/States";
import {
  dashApi,
  downloadBlob,
  errMsg,
  type Dashboard,
  type DashResult,
  type FilterDef,
} from "../lib/api";
import { useAuth, canEdit } from "../lib/auth";

function initialValues(defs: FilterDef[]): Record<string, unknown> {
  const v: Record<string, unknown> = {};
  for (const d of defs) {
    if (d.type === "multiselect") v[d.key] = [];
    else if (d.default !== undefined) v[d.key] = d.default;
  }
  return v;
}

export default function DashboardView() {
  const { key = "" } = useParams();
  const { user } = useAuth();
  const editor = canEdit(user?.role);

  const [dash, setDash] = useState<Dashboard | null>(null);
  const [defs, setDefs] = useState<FilterDef[]>([]);
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [result, setResult] = useState<DashResult | null>(null);
  const [metaLoading, setMetaLoading] = useState(true);
  const [runLoading, setRunLoading] = useState(false);
  const [error, setError] = useState("");

  const run = useCallback(
    async (filters: Record<string, unknown>) => {
      setRunLoading(true);
      setError("");
      try {
        const r = await dashApi.run(key, filters);
        setResult(r.data);
      } catch (e) {
        setError(errMsg(e));
      } finally {
        setRunLoading(false);
      }
    },
    [key]
  );

  useEffect(() => {
    setMetaLoading(true);
    setError("");
    Promise.all([dashApi.get(key), dashApi.meta(key)])
      .then(([dRes, mRes]) => {
        setDash(dRes.data);
        const schema = mRes.data.filter_schema ?? [];
        setDefs(schema);
        const init = initialValues(schema);
        setValues(init);
        run(init);
      })
      .catch((e) => setError(errMsg(e)))
      .finally(() => setMetaLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const exportXlsx = async () => {
    try {
      const r = await dashApi.export(key, values);
      downloadBlob(r.data, `${key}.xlsx`);
    } catch (e) {
      setError(errMsg(e));
    }
  };

  return (
    <Layout
      title={dash?.title ?? "Dashboard"}
      actions={
        editor ? (
          <Link
            to={`/d/${key}/edit`}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 transition hover:bg-slate-100 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
          >
            Düzenle
          </Link>
        ) : undefined
      }
    >
      {dash?.description && (
        <p className="mb-4 text-sm text-slate-500 dark:text-slate-400">
          {dash.description}
        </p>
      )}

      {metaLoading ? (
        <div className="space-y-6">
          <CardSkeleton rows={4} />
          <TableSkeleton />
        </div>
      ) : (
        <div className="space-y-6">
          {defs.length > 0 && (
            <Filters
              defs={defs}
              values={values}
              setValues={setValues}
              onApply={() => run(values)}
              onExport={exportXlsx}
              loading={runLoading}
            />
          )}

          {error && <ErrorBanner message={error} onRetry={() => run(values)} />}

          {runLoading ? (
            <div className="space-y-6">
              <CardSkeleton rows={4} />
              <TableSkeleton />
            </div>
          ) : result ? (
            <>
              <KpiCards kpis={result.kpis} />
              {result.charts.length > 0 && (
                <div className="grid gap-4 xl:grid-cols-2">
                  {result.charts.map((c, i) => (
                    <Chart key={i} spec={c} />
                  ))}
                </div>
              )}
              <DataTable
                columns={result.table.columns}
                rows={result.table.rows}
              />
            </>
          ) : (
            !error && (
              <EmptyState
                title="Veri yok"
                message="Filtreleri ayarlayıp Uygula'ya basın."
              />
            )
          )}
        </div>
      )}
    </Layout>
  );
}
