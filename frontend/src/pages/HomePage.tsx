import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Camera, FlaskConical, Microscope, Sprout, Video } from "lucide-react";
import { Link } from "react-router";

import { Hero } from "../components/Hero";
import { HowItWorksCard, RecentStatsCard } from "../components/InfoCards";
import { Card, ErrorBanner, Skeleton } from "../components/ui";
import { useI18n } from "../i18n";
import { api } from "../lib/api";
import { asNumber, percent } from "../lib/format";

export function KeyFacts() {
  const { t } = useI18n();
  const model = useQuery({ queryKey: ["model"], queryFn: api.model, staleTime: Infinity });
  if (model.isPending) return <Skeleton className="h-28 w-full" />;
  if (model.isError) return <ErrorBanner error={model.error} onRetry={() => model.refetch()} />;
  if (!model.data.model_loaded) return <ErrorBanner error={{}} />;
  const metrics = model.data.model_card.metrics ?? {};
  const facts = [
    { label: t("home.testAccuracy"), value: percent(asNumber(metrics.test_accuracy)) },
    { label: t("home.macroF1"), value: asNumber(metrics.test_macro_f1)?.toFixed(3) ?? "—" },
    { label: t("home.classes"), value: String(model.data.classes.length) },
    { label: t("home.testImages"), value: asNumber(metrics.test_n)?.toLocaleString("en") ?? "—" },
  ];
  return (
    <div data-testid="key-facts">
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {facts.map((fact) => (
          <div key={fact.label} className="rounded-xl bg-brand-50 p-4">
            <dt className="text-sm text-gray-600">{fact.label}</dt>
            <dd className="mt-1 text-2xl font-bold text-brand-800 latin">{fact.value}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-3 text-sm text-gray-600">{t("home.measuredOn")}</p>
      <p className="mt-1 text-sm font-semibold text-amber-800">{t("home.fieldWarning")}</p>
    </div>
  );
}

export function HomePage() {
  const { t } = useI18n();
  return (
    <div className="page-backdrop">
      <Hero compact />
      <div className="mx-auto max-w-[1480px] space-y-5 px-4 pb-6 lg:px-6">
        <Card>
          <div className="grid gap-6 lg:grid-cols-[1.1fr_1fr] lg:items-center">
            <div>
              <h2 className="text-2xl font-bold text-gray-900 sm:text-3xl">{t("home.title")}</h2>
              <p className="mt-3 text-lg text-gray-700">{t("home.lead")}</p>
              <div className="mt-5 flex flex-wrap gap-3">
                <Link
                  to="/live"
                  className="inline-flex items-center gap-2 rounded-xl bg-brand-700 px-6 py-3 text-base font-semibold text-white shadow hover:bg-brand-800"
                  data-testid="home-live-cta"
                >
                  <Video className="h-5 w-5" aria-hidden="true" />
                  {t("home.liveCta")}
                  <ArrowRight className="h-5 w-5 rtl:rotate-180" aria-hidden="true" />
                </Link>
                <Link
                  to="/scanner"
                  className="inline-flex items-center gap-2 rounded-xl border border-brand-700 px-5 py-3 font-semibold text-brand-800 hover:bg-brand-50"
                  data-testid="home-cta"
                >
                  <Camera className="h-5 w-5" aria-hidden="true" />
                  {t("home.cta")}
                </Link>
                <Link
                  to="/field-intelligence"
                  className="inline-flex items-center gap-2 rounded-xl border border-brand-700 px-5 py-3 font-semibold text-brand-800 hover:bg-brand-50"
                >
                  <FlaskConical className="h-5 w-5" aria-hidden="true" />
                  {t("nav.field")}
                </Link>
              </div>
            </div>
            <div>
              <h3 className="mb-3 flex items-center gap-2 font-bold text-gray-900">
                <Microscope className="h-5 w-5 text-brand-700" aria-hidden="true" />
                {t("home.keyFacts")}
              </h3>
              <KeyFacts />
            </div>
          </div>
        </Card>
        <div className="grid gap-5 lg:grid-cols-2">
          <HowItWorksCard />
          <RecentStatsCard />
        </div>
        <p className="flex items-center justify-center gap-2 text-center text-sm text-gray-700">
          <Sprout className="h-4 w-4 text-brand-700" aria-hidden="true" />
          {t("result.disclaimer")}
        </p>
      </div>
    </div>
  );
}
