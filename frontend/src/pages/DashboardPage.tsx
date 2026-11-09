import { useQuery } from "@tanstack/react-query";
import { BarChart3 } from "lucide-react";
import { Link } from "react-router";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { PageShell } from "../components/PageShell";
import { Card, CardTitle, EmptyState, ErrorBanner, Skeleton } from "../components/ui";
import { useI18n } from "../i18n";
import { api, type CountItem } from "../lib/api";

function CountChart({ data, horizontal = false }: { data: CountItem[]; horizontal?: boolean }) {
  const height = horizontal ? Math.max(180, data.length * 38) : 260;
  return (
    <div style={{ height }} dir="ltr">
      <ResponsiveContainer width="100%" height="100%">
        {horizontal ? (
          <BarChart data={data} layout="vertical" margin={{ left: 8, right: 24 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={false} />
            <XAxis type="number" allowDecimals={false} />
            <YAxis type="category" dataKey="label" width={190} tick={{ fontSize: 12 }} />
            <Tooltip />
            <Bar isAnimationActive={false} dataKey="count" fill="#15803d" radius={[0, 6, 6, 0]} />
          </BarChart>
        ) : (
          <BarChart data={data} margin={{ left: -10, right: 8 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="label" tick={{ fontSize: 12 }} />
            <YAxis allowDecimals={false} />
            <Tooltip />
            <Bar isAnimationActive={false} dataKey="count" fill="#15803d" radius={[6, 6, 0, 0]} />
          </BarChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}

export function DashboardPage() {
  const { t, district } = useI18n();
  const stats = useQuery({ queryKey: ["stats"], queryFn: api.stats });

  return (
    <PageShell title={t("dashboard.title")}>
      {stats.isPending && <Skeleton className="h-64 w-full" />}
      {stats.isError && <ErrorBanner error={stats.error} onRetry={() => stats.refetch()} />}
      {stats.data && stats.data.total_scans === 0 && (
        <Card>
          <EmptyState
            icon={<BarChart3 className="h-10 w-10" aria-hidden="true" />}
            title={t("dashboard.empty")}
            body={t("dashboard.emptyBody")}
            action={
              <Link to="/scanner" className="rounded-xl bg-brand-700 px-5 py-2.5 font-semibold text-white hover:bg-brand-800">
                {t("home.cta")}
              </Link>
            }
          />
        </Card>
      )}
      {stats.data && stats.data.total_scans > 0 && (
        <>
          <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4" data-testid="stat-tiles">
            {[
              { label: t("dashboard.total"), value: stats.data.total_scans },
              { label: t("dashboard.healthy"), value: stats.data.healthy_scans },
              { label: t("dashboard.diseased"), value: stats.data.diseased_scans },
              { label: t("dashboard.feedback"), value: `${stats.data.feedback.correct} / ${stats.data.feedback.total}` },
            ].map((tile) => (
              <div key={tile.label} className="rounded-2xl bg-white p-5 shadow-sm">
                <dt className="text-sm text-gray-600">{tile.label}</dt>
                <dd className="mt-1 text-3xl font-bold text-brand-800 latin">{tile.value}</dd>
              </div>
            ))}
          </dl>
          <Card>
            <CardTitle title={t("dashboard.byDisease")} />
            <CountChart data={stats.data.by_disease} horizontal />
          </Card>
          <div className="grid gap-5 lg:grid-cols-2">
            <Card>
              <CardTitle title={t("dashboard.byWeek")} />
              <CountChart data={stats.data.by_week} />
            </Card>
            <Card>
              <CardTitle title={t("dashboard.byDistrict")} />
              <CountChart data={stats.data.by_district.map((d) => ({ ...d, label: district(d.label) }))} />
            </Card>
          </div>
          <p className="text-sm text-gray-600">{t("dashboard.source")}</p>
        </>
      )}
    </PageShell>
  );
}
