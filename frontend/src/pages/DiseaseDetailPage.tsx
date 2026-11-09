import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ChevronLeft, ChevronRight, ExternalLink, ShieldAlert } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router";

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

export function DiseaseDetailPage() {
  const { id = "" } = useParams();
  const { t, crop } = useI18n();
  const disease = useQuery({ queryKey: ["disease", id], queryFn: () => api.disease(id) });
  const d = disease.data;

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
          <div className="mt-6">
            <Disclaimer />
          </div>
        </Card>
      )}
    </PageShell>
  );
}
