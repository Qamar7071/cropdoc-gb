import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Bot, ChevronLeft, ChevronRight, ExternalLink, FileSearch, Leaf, PhoneCall, ShieldAlert, Sprout, Stethoscope, Zap } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router";

import { BiHeading, BiList, BiText, ReviewNote, RiskBadge } from "../components/report/Bilingual";
import type { DiseaseReport } from "../lib/api";

import { PageShell } from "../components/PageShell";
import { Card, CategoryBadge, Disclaimer, ErrorBanner, Skeleton } from "../components/ui";
import { useI18n } from "../i18n";
import { api } from "../lib/api";

export function Carousel({ images, label }: { images: string[]; label: (n: number) => string }) {
  const { t } = useI18n();
  const [index, setIndex] = useState(0);
  if (images.length === 0) return null;
  const go = (delta: number) => setIndex((current) => (current + delta + images.length) % images.length);
  return (
    <div data-testid="carousel">
      <div className="relative overflow-hidden rounded-2xl bg-gray-100">
        <img src={images[index]} alt={label(index + 1)} className="aspect-[4/3] w-full object-cover" />
        {images.length > 1 && (
          <>
            <button type="button" onClick={() => go(-1)} className="absolute start-2 top-1/2 -translate-y-1/2 rounded-full bg-white/90 p-2 shadow" aria-label={t("library.prev")}>
              <ChevronLeft className="h-5 w-5 rtl:rotate-180" aria-hidden="true" />
            </button>
            <button type="button" onClick={() => go(1)} className="absolute end-2 top-1/2 -translate-y-1/2 rounded-full bg-white/90 p-2 shadow" aria-label={t("library.next")}>
              <ChevronRight className="h-5 w-5 rtl:rotate-180" aria-hidden="true" />
            </button>
          </>
        )}
      </div>
      <div className="mt-2 flex gap-2">
        {images.map((src, i) => (
          <button
            key={src}
            type="button"
            onClick={() => setIndex(i)}
            aria-label={label(i + 1)}
            aria-current={i === index}
            className={`overflow-hidden rounded-lg ring-2 ${i === index ? "ring-brand-700" : "ring-transparent"}`}
          >
            <img src={src} alt="" className="h-14 w-16 object-cover" />
          </button>
        ))}
      </div>
    </div>
  );
}

/** Full bilingual explanation + treatment guide (anchor #treatment). */
export function DiseaseKnowledge({ report }: { report: DiseaseReport }) {
  const { t } = useI18n();
  return (
    <div className="mt-8 space-y-7" data-testid="disease-knowledge">
      <section className="space-y-3">
        <BiHeading level={2} en="Disease overview" ur="بیماری کا جائزہ" icon={<Leaf className="h-6 w-6 text-brand-700" aria-hidden="true" />} />
        <BiText text={report.description} />
        <BiText className="text-sm text-gray-600" text={{ en: `Commonly affects: ${report.crop.en}. Cause: ${report.pathogen || "—"}.`, ur: `عام طور پر متاثرہ فصل: ${report.crop.ur}۔` }} />
        <RiskBadge level={report.risk_level} reason={report.risk_reason} />
        <p className="text-xs text-gray-500">{t("report.riskNote")}</p>
      </section>
      {!report.healthy && (
        <section className="space-y-3">
          <BiHeading level={2} en="Symptoms" ur="علامات" icon={<Stethoscope className="h-6 w-6 text-brand-700" aria-hidden="true" />} />
          <BiHeading en="Early stage" ur="ابتدائی مرحلہ" />
          <BiList list={report.symptoms_early} />
          <BiHeading en="Advanced stage" ur="بڑھا ہوا مرحلہ" />
          <BiList list={report.symptoms_advanced} />
        </section>
      )}
      {report.causes.en.length > 0 && (
        <section className="space-y-3">
          <BiHeading level={2} en="Causes and spread" ur="وجوہات اور پھیلاؤ" icon={<FileSearch className="h-6 w-6 text-brand-700" aria-hidden="true" />} />
          <BiList list={report.causes} />
          <BiText className="text-sm" text={report.spread} />
        </section>
      )}
      <section className="space-y-4 rounded-2xl border border-brand-200 bg-brand-50/60 p-5" id="treatment" data-testid="treatment-guide">
        <BiHeading level={2} en="Treatment guide" ur="علاج کی رہنمائی" icon={<Sprout className="h-6 w-6 text-brand-700" aria-hidden="true" />} />
        <BiHeading en="Immediate actions" ur="فوری اقدامات" icon={<Zap className="h-5 w-5 text-amber-500" aria-hidden="true" />} />
        <BiList list={report.immediate_actions} bullet="✓" />
        <BiHeading en="Prevention and natural (non-chemical) practices" ur="بچاؤ اور قدرتی (غیر کیمیائی) طریقے" icon={<Leaf className="h-5 w-5 text-brand-700" aria-hidden="true" />} />
        <BiList list={report.prevention} />
        {report.treatment_categories.en.length > 0 && (
          <>
            <BiHeading en="Treatment category (ask before using any product)" ur="علاج کی قسم (کوئی بھی دوا استعمال کرنے سے پہلے پوچھیں)" icon={<ShieldAlert className="h-5 w-5 text-amber-600" aria-hidden="true" />} />
            <BiList list={report.treatment_categories} />
          </>
        )}
        {report.call_expert_when.en.length > 0 && (
          <>
            <BiHeading en="When to call an agriculture expert" ur="زرعی ماہر کو کب بلائیں" icon={<PhoneCall className="h-5 w-5 text-red-700" aria-hidden="true" />} />
            <BiList list={report.call_expert_when} />
          </>
        )}
        {!report.healthy && <BiText className="rounded-lg bg-white p-3 text-sm font-semibold" text={report.extension_fallback} />}
        <BiText
          className="text-sm text-gray-700"
          text={{
            en: "Safety: if a product is used, read the label, wear gloves and a mask, keep children away, and never reuse empty containers.",
            ur: "حفاظت: اگر کوئی دوا استعمال ہو تو لیبل پڑھیں، دستانے اور ماسک پہنیں، بچوں کو دور رکھیں، اور خالی ڈبے دوبارہ استعمال نہ کریں۔",
          }}
        />
        <ReviewNote urdu={report.urdu_needs_review} />
        <Link
          to={`/assistant?class_id=${encodeURIComponent(report.id)}`}
          className="inline-flex items-center gap-2 rounded-xl bg-brand-700 px-4 py-2.5 text-[15px] font-semibold text-white hover:bg-brand-800"
        >
          <Bot className="h-4 w-4" aria-hidden="true" />
          {t("report.askAssistant")}
        </Link>
      </section>
    </div>
  );
}

export function DiseaseDetailPage() {
  const { id = "" } = useParams();
  const { hash } = useLocation();
  const { t, crop } = useI18n();
  const disease = useQuery({ queryKey: ["disease", id], queryFn: () => api.disease(id) });
  const d = disease.data;

  // "Treatment Guide" links to #treatment: scroll there once the content has loaded
  useEffect(() => {
    if (d && hash) document.getElementById(hash.slice(1))?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [d, hash]);

  return (
    <PageShell
      title={d ? d.disease : t("library.title")}
      lead={d ? crop(d.crop) : undefined}
      actions={
        <Link to="/library" className="inline-flex items-center gap-2 rounded-xl bg-white/10 px-4 py-2 font-semibold text-white hover:bg-white/20">
          <ArrowLeft className="h-4 w-4 rtl:rotate-180" aria-hidden="true" />
          {t("library.back")}
        </Link>
      }
    >
      {disease.isPending && <Skeleton className="h-96 w-full" />}
      {disease.isError && <ErrorBanner error={disease.error} />}
      {d && (
        <Card>
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
            <Carousel images={d.images} label={(n) => t("library.photo", { n })} />
            <div className="space-y-4">
              {d.needs_review && (
                <p className="flex items-start gap-2 rounded-xl border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950">
                  <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                  {t("library.reviewBanner")}
                </p>
              )}
              <p className="text-lg text-gray-800">{d.description}</p>
              <dl className="divide-y divide-gray-100 rounded-xl border border-gray-200">
                <div className="grid grid-cols-[10rem_1fr] gap-3 p-3">
                  <dt className="font-semibold text-gray-700">{t("library.category")}</dt>
                  <dd>
                    <CategoryBadge category={d.category} />
                  </dd>
                </div>
                {d.pathogen && (
                  <div className="grid grid-cols-[10rem_1fr] gap-3 p-3">
                    <dt className="font-semibold text-gray-700">{t("library.pathogen")}</dt>
                    <dd className="latin italic text-gray-900">{d.pathogen}</dd>
                  </div>
                )}
                <div className="grid grid-cols-[10rem_1fr] gap-3 p-3">
                  <dt className="font-semibold text-gray-700">{t("library.spread")}</dt>
                  <dd className="text-gray-900">{d.spread}</dd>
                </div>
                <div className="grid grid-cols-[10rem_1fr] gap-3 p-3">
                  <dt className="font-semibold text-gray-700">{t("library.part")}</dt>
                  <dd className="text-gray-900">{d.most_affected_part}</dd>
                </div>
              </dl>
            </div>
          </div>
          <div className="mt-6 grid gap-6 lg:grid-cols-2">
            <section>
              <h2 className="mb-2 text-lg font-bold">{t("library.symptoms")}</h2>
              <ul className="list-disc space-y-1 ps-5 text-gray-800">
                {d.symptoms.map((s) => (
                  <li key={s}>{s}</li>
                ))}
              </ul>
            </section>
            <section>
              <h2 className="mb-2 text-lg font-bold">{t("library.management")}</h2>
              <ul className="list-disc space-y-1 ps-5 text-gray-800">
                {d.general_management.map((s) => (
                  <li key={s}>{s}</li>
                ))}
              </ul>
              {d.category !== "healthy" && <p className="mt-3 rounded-lg bg-brand-50 p-3 text-sm font-semibold text-brand-900">{t("library.extension")}</p>}
            </section>
          </div>
          {d.sources.length > 0 && (
            <section className="mt-6">
              <h2 className="mb-2 text-lg font-bold">{t("library.sources")}</h2>
              <ul className="space-y-1 text-sm">
                {d.sources.map((url) => (
                  <li key={url}>
                    <a href={url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 break-all text-brand-800 underline latin">
                      {url.replace(/^https?:\/\//, "").slice(0, 90)}
                      <ExternalLink className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                    </a>
                  </li>
                ))}
              </ul>
            </section>
          )}
          {d.report && <DiseaseKnowledge report={d.report} />}
          <div className="mt-6">
            <Disclaimer />
          </div>
        </Card>
      )}
    </PageShell>
  );
}
