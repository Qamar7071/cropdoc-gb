/* Farming Tips: short, general good practice (FAO IPM and pesticide-safety principles), English + Urdu. */
import { useQuery } from "@tanstack/react-query";
import { Droplets, ExternalLink, FlaskConical, Hand, NotebookPen, Repeat, Search, Shield, Sprout, Trash2, type LucideIcon } from "lucide-react";

import { PageShell } from "../components/PageShell";
import { En, Ur } from "../components/report/Bilingual";
import { ErrorBanner, Skeleton } from "../components/ui";
import { useI18n } from "../i18n";
import { api, type Tip } from "../lib/api";

const ICONS: Record<string, LucideIcon> = {
  search: Search, sprout: Sprout, repeat: Repeat, flask: FlaskConical, droplets: Droplets,
  trash: Trash2, shield: Shield, hand: Hand, notebook: NotebookPen,
};

/** One tip in English and Urdu. Pass className="h-full" only where the parent gives it a definite height (a grid row). */
export function TipCard({ tip, className = "" }: { tip: Tip; className?: string }) {
  const Icon = ICONS[tip.icon] ?? Sprout;
  return (
    <div className={`flex gap-3 rounded-2xl bg-white p-4 shadow-[0_10px_30px_-12px_rgba(6,39,22,0.35)] ${className}`} data-testid="tip">
      <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-brand-100 text-brand-700" aria-hidden="true">
        <Icon className="h-5 w-5" />
      </span>
      <div className="min-w-0 flex-1 space-y-1">
        <En className="font-bold text-gray-900">{tip.title.en}</En>
        <En className="text-sm text-gray-700">{tip.body.en}</En>
        <Ur className="font-bold text-gray-900">{tip.title.ur}</Ur>
        <Ur className="text-sm text-gray-700">{tip.body.ur}</Ur>
      </div>
    </div>
  );
}

export function TipsPage() {
  const { t } = useI18n();
  const tips = useQuery({ queryKey: ["tips"], queryFn: api.tips, staleTime: Infinity });
  return (
    <PageShell title={t("tips.title")} lead={t("tips.lead")}>
      {tips.isPending && <Skeleton className="h-72 w-full" />}
      {tips.isError && <ErrorBanner error={tips.error} onRetry={() => tips.refetch()} />}
      {tips.data && (
        <>
          <ul className="grid gap-4 md:grid-cols-2" data-testid="tips-grid">
            {tips.data.items.map((tip) => (
              <li key={tip.id} className="flex">
                <TipCard tip={tip} className="flex-1" />
              </li>
            ))}
          </ul>
          <p className="mt-5 text-sm text-gray-700">{t("tips.sources")}</p>
          <ul className="mt-1 space-y-1 text-sm">
            {tips.data.meta.sources.map((url) => (
              <li key={url}>
                <a href={url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 break-all text-brand-800 underline latin">
                  {url.replace(/^https?:\/\//, "").slice(0, 90)}
                  <ExternalLink className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                </a>
              </li>
            ))}
          </ul>
        </>
      )}
    </PageShell>
  );
}
