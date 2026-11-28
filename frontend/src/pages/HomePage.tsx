import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Bot, FlaskConical, History, Languages, Lightbulb, Microscope, Sprout, Upload, Video, Wheat } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router";

import { WeatherCard } from "../components/WeatherCard";
import { TipCard } from "./TipsPage";

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

function Tile({ to, icon, title, titleUr, body, testId, onClick }: { to?: string; icon: ReactNode; title: string; titleUr: string; body: string; testId: string; onClick?: () => void }) {
  const content = (
    <>
      <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-brand-700 text-white shadow-md" aria-hidden="true">
        {icon}
      </span>
      <span className="min-w-0 flex-1 text-start">
        <span className="block text-lg font-bold text-gray-900">{title}</span>
        <span lang="ur" dir="rtl" className="urdu block text-base font-semibold text-gray-700">{titleUr}</span>
        <span className="mt-0.5 block text-sm text-gray-600">{body}</span>
      </span>
    </>
  );
  const className = "flex min-h-[7rem] w-full items-center gap-4 rounded-2xl bg-white p-4 shadow-[0_10px_30px_-12px_rgba(6,39,22,0.35)] transition hover:ring-4 hover:ring-brand-200 focus-visible:ring-4";
  return to ? (
    <Link to={to} className={className} data-testid={testId}>
      {content}
    </Link>
  ) : (
    <button type="button" onClick={onClick} className={className} data-testid={testId}>
      {content}
    </button>
  );
}

export function FarmerDashboard() {
  const { t, lang, setLang } = useI18n();
  const tips = useQuery({ queryKey: ["tips"], queryFn: api.tips, staleTime: Infinity });
  return (
    <section aria-labelledby="dashboard-title" className="space-y-4" data-testid="farmer-dashboard">
      <h2 id="dashboard-title" className="sr-only">{t("home.dashboard")}</h2>
      <div className="rounded-3xl bg-gradient-to-br from-brand-700 to-brand-900 p-5 text-white shadow-lg sm:p-6">
        <p className="text-2xl font-extrabold sm:text-3xl">{t("home.scanTitle")}</p>
        <p lang="ur" dir="rtl" className="urdu text-xl font-semibold">اپنے پودے کو اسکین کریں</p>
        <p className="mt-1 max-w-2xl text-white/90">{t("home.scanBody")}</p>
        <div className="mt-4 flex flex-wrap gap-3">
          <Link to="/live" className="inline-flex min-h-[3.25rem] items-center gap-2 rounded-2xl bg-white px-6 py-3 text-lg font-bold text-brand-800 shadow hover:bg-brand-50" data-testid="home-live-cta">
            <Video className="h-6 w-6" aria-hidden="true" />
            {t("home.liveCta")}
          </Link>
          <Link to="/scanner" className="inline-flex min-h-[3.25rem] items-center gap-2 rounded-2xl border-2 border-white/70 px-6 py-3 text-lg font-bold text-white hover:bg-white/10" data-testid="home-cta">
            <Upload className="h-6 w-6" aria-hidden="true" />
            {t("home.uploadCta")}
          </Link>
        </div>
      </div>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <Tile to="/history" testId="tile-history" icon={<History className="h-7 w-7" />} title={t("nav.history")} titleUr="میری اسکین ہسٹری" body={t("home.historyBody")} />
        <Tile to="/crops" testId="tile-crops" icon={<Wheat className="h-7 w-7" />} title={t("crops.title")} titleUr="فصلوں کی معلومات" body={t("home.cropsBody")} />
        <Tile to="/assistant" testId="tile-assistant" icon={<Bot className="h-7 w-7" />} title={t("assistant.title")} titleUr="زرعی اے آئی اسسٹنٹ" body={t("home.assistantBody")} />
        <Tile to="/tips" testId="tile-tips" icon={<Lightbulb className="h-7 w-7" />} title={t("tips.title")} titleUr="کاشتکاری کے مشورے" body={t("home.tipsBody")} />
        <Tile
          testId="tile-language"
          icon={<Languages className="h-7 w-7" />}
          title={t("home.language")}
          titleUr="زبان کی ترتیبات"
          body={lang === "ur" ? "Switch to English" : "اردو میں تبدیل کریں"}
          onClick={() => setLang(lang === "ur" ? "en" : "ur")}
        />
        <Tile to="/library" testId="tile-library" icon={<Sprout className="h-7 w-7" />} title={t("nav.library")} titleUr="بیماریوں کی لائبریری" body={t("home.libraryBody")} />
      </div>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <WeatherCard />
        <div className="space-y-3">
          <p className="flex items-center gap-2 text-lg font-bold text-gray-900">
            <Lightbulb className="h-5 w-5 text-amber-500" aria-hidden="true" />
            {t("home.tipOfDay")}
          </p>
          {(tips.data?.items ?? []).slice(0, 2).map((tip) => (
            <TipCard key={tip.id} tip={tip} />
          ))}
          <Link to="/tips" className="inline-flex items-center gap-1 font-semibold text-brand-800 underline">
            {t("home.allTips")}
            <ArrowRight className="h-4 w-4 rtl:rotate-180" aria-hidden="true" />
          </Link>
        </div>
      </div>
    </section>
  );
}

export function HomePage() {
  const { t } = useI18n();
  return (
    <div className="page-backdrop">
      <Hero compact />
      <div className="mx-auto max-w-[1480px] space-y-5 px-4 pb-6 lg:px-6">
        <FarmerDashboard />
        <Card>
          <div className="grid gap-6 lg:grid-cols-[1.1fr_1fr] lg:items-center">
            <div>
              <h2 className="text-2xl font-bold text-gray-900 sm:text-3xl">{t("home.title")}</h2>
              <p className="mt-3 text-lg text-gray-700">{t("home.lead")}</p>
              <div className="mt-5 flex flex-wrap gap-3">
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
