/* "How It Works" and "Your Recent Scans" cards (inspired by the dark-theme design variant). */
import { useQuery } from "@tanstack/react-query";
import { Info, PieChart } from "lucide-react";
import { Link } from "react-router";

import { useI18n } from "../i18n";
import { api } from "../lib/api";
import { Card, CardTitle, ErrorBanner, IconBubble, Skeleton } from "./ui";

export function HowItWorksCard() {
  const { t } = useI18n();
  return (
    <Card>
      <CardTitle
        icon={
          <IconBubble tone="soft">
            <Info className="h-6 w-6" />
          </IconBubble>
        }
        title={t("how.title")}
      />
      <p className="text-[15px] text-gray-700">{t("how.intro")}</p>
      <div className="mt-4 rounded-xl bg-brand-50 p-4">
        <p className="font-semibold text-gray-900">{t("how.steps")}</p>
        <ol className="mt-2 space-y-2">
          {["how.step1", "how.step2", "how.step3"].map((key, index) => (
            <li key={key} className="flex items-start gap-3 text-[15px] text-gray-800">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-700 text-sm font-bold text-white latin">
                {index + 1}
              </span>
              {t(key)}
            </li>
          ))}
        </ol>
      </div>
      <p className="mt-4 text-sm text-gray-600">{t("how.tip")}</p>
    </Card>
  );
}

export function RecentStatsCard() {
  const { t } = useI18n();
  const stats = useQuery({ queryKey: ["stats"], queryFn: api.stats });
  const items = stats.data?.by_disease.slice(0, 4) ?? [];
  const max = Math.max(1, ...items.map((item) => item.count));
  return (
    <Card>
      <CardTitle
        icon={
          <IconBubble tone="soft">
            <PieChart className="h-6 w-6" />
          </IconBubble>
        }
        title={t("home.recentStats")}
        action={
          <Link to="/dashboard" className="text-sm font-semibold text-brand-800 underline">
            {t("nav.dashboard")}
          </Link>
        }
      />
      {stats.isPending && <Skeleton className="h-32 w-full" />}
      {stats.isError && <ErrorBanner error={stats.error} onRetry={() => stats.refetch()} />}
      {stats.data && items.length === 0 && <p className="text-[15px] text-gray-600">{t("home.recentEmpty")}</p>}
      {items.length > 0 && (
        <ul className="space-y-3">
          {items.map((item) => (
            <li key={item.key} className="rounded-xl bg-gray-50 px-4 py-3">
              <div className="flex items-center justify-between text-[15px]">
                <span className="font-semibold text-gray-900">{item.label}</span>
                <span className="text-sm text-gray-600 latin">{t("home.cases", { count: item.count })}</span>
              </div>
              <div className="mt-2 h-2 rounded-full bg-gray-200" aria-hidden="true">
                <div className="h-2 rounded-full bg-brand-700" style={{ width: `${(item.count / max) * 100}%` }} />
              </div>
            </li>
          ))}
        </ul>
      )}
      {stats.data && <p className="mt-3 text-xs text-gray-500">{t("dashboard.source")}</p>}
    </Card>
  );
}
