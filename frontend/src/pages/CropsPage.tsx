/* Crop Information: important Pakistani crops, their common diseases, prevention and seasonal care. */
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, CalendarDays, ExternalLink, Leaf, ScanLine, ShieldAlert, Sprout } from "lucide-react";
import { Link, useParams } from "react-router";

import { PageShell } from "../components/PageShell";
import { BiHeading, BiList, BiText, Ur } from "../components/report/Bilingual";
import { Card, Disclaimer, ErrorBanner, Skeleton } from "../components/ui";
import { useI18n } from "../i18n";
import { api } from "../lib/api";

export function CropsPage() {
  const { t } = useI18n();
  const crops = useQuery({ queryKey: ["crops"], queryFn: api.crops, staleTime: Infinity });
  return (
    <PageShell title={t("crops.title")} lead={t("crops.lead")}>
      {crops.isPending && <Skeleton className="h-72 w-full" />}
      {crops.isError && <ErrorBanner error={crops.error} onRetry={() => crops.refetch()} />}
      {crops.data && (
        <>
          <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3" data-testid="crop-grid">
            {crops.data.items.map((crop) => (
              <li key={crop.id}>
                <Link
                  to={`/crops/${crop.id}`}
                  className="flex h-full flex-col gap-2 rounded-2xl bg-white p-5 shadow-[0_10px_30px_-12px_rgba(6,39,22,0.35)] transition hover:ring-4 hover:ring-brand-200"
                  data-testid={`crop-${crop.id}`}
                >
                  <div className="flex items-center gap-3">
                    <span className="flex h-11 w-11 items-center justify-center rounded-full bg-brand-100 text-brand-700" aria-hidden="true">
                      <Sprout className="h-6 w-6" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-xl font-bold text-gray-900">
                        {crop.name.en} <span lang="ur" dir="rtl" className="urdu font-semibold text-gray-700">{crop.name.ur}</span>
                      </p>
                      <p className="text-xs text-gray-600">{crop.season.en}</p>
                    </div>
                  </div>
                  <p className="text-sm text-gray-700">{crop.summary.en}</p>
                  <Ur className="text-sm text-gray-700">{crop.summary.ur}</Ur>
                  <span
                    className={`mt-auto inline-flex w-fit items-center gap-1 rounded-full px-2.5 py-1 text-xs font-bold ${crop.scanner_supported ? "bg-brand-100 text-brand-800" : "bg-gray-100 text-gray-700"}`}
                  >
                    <ScanLine className="h-3.5 w-3.5" aria-hidden="true" />
                    {crop.scanner_supported ? t("crops.scannerYes") : t("crops.scannerNo")}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
          {crops.data.meta.scanner_note && (
            <BiText className="mt-5 rounded-xl bg-white/80 p-4 text-sm" text={crops.data.meta.scanner_note} />
          )}
        </>
      )}
    </PageShell>
  );
}

export function CropDetailPage() {
  const { id = "" } = useParams();
  const { t } = useI18n();
  const crop = useQuery({ queryKey: ["crop", id], queryFn: () => api.crop(id) });
  const c = crop.data;
  return (
    <PageShell
      title={c ? `${c.name.en} · ${c.name.ur}` : t("crops.title")}
      lead={c?.season.en}
      actions={
        <Link to="/crops" className="inline-flex items-center gap-2 rounded-xl bg-white/10 px-4 py-2 font-semibold text-white hover:bg-white/20">
          <ArrowLeft className="h-4 w-4 rtl:rotate-180" aria-hidden="true" />
          {t("crops.back")}
        </Link>
      }
    >
      {crop.isPending && <Skeleton className="h-96 w-full" />}
      {crop.isError && <ErrorBanner error={crop.error} />}
      {c && (
        <Card className="space-y-7" data-testid="crop-detail">
          <section className="space-y-3">
            <BiHeading level={2} en="About this crop" ur="فصل کے بارے میں" icon={<Leaf className="h-6 w-6 text-brand-700" aria-hidden="true" />} />
            <BiText text={c.summary} />
            <BiText className="text-sm text-gray-600" text={c.season} />
            {c.needs_review && (
              <p className="flex items-start gap-2 rounded-xl border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950">
                <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                {t("library.reviewBanner")}
              </p>
            )}
          </section>
          <section className="space-y-4">
            <BiHeading level={2} en="Common diseases" ur="عام بیماریاں" icon={<ShieldAlert className="h-6 w-6 text-brand-700" aria-hidden="true" />} />
            {c.diseases.map((d) => (
              <div key={d.name.en} className="space-y-2 rounded-xl border border-gray-100 p-4 shadow-sm" data-testid="crop-disease">
                <BiHeading en={d.name.en} ur={d.name.ur} />
                <BiText text={d.symptoms} />
                <p className="text-sm font-semibold text-gray-700">
                  {t("crops.prevention")} / <span lang="ur" className="urdu">بچاؤ</span>
                </p>
                <BiList list={d.prevention} bullet="✓" />
              </div>
            ))}
          </section>
          <section className="space-y-3">
            <BiHeading level={2} en="Seasonal care" ur="موسمی دیکھ بھال" icon={<CalendarDays className="h-6 w-6 text-brand-700" aria-hidden="true" />} />
            <BiList list={c.seasonal_care} />
          </section>
          <section className="space-y-3 rounded-xl bg-brand-50 p-4">
            <BiHeading en="Scan this crop" ur="اس فصل کو اسکین کریں" icon={<ScanLine className="h-5 w-5 text-brand-700" aria-hidden="true" />} />
            {c.scanner_diseases.length ? (
              <>
                <p className="text-sm text-gray-700">{t("crops.scannerKnows")}</p>
                <ul className="flex flex-wrap gap-2">
                  {c.scanner_diseases.map((d) => (
                    <li key={d.id}>
                      <Link to={`/library/${encodeURIComponent(d.id)}`} className="inline-flex items-center gap-1 rounded-full bg-white px-3 py-1 text-sm font-semibold text-brand-800 ring-1 ring-brand-200">
                        {d.name.en} <span lang="ur" className="urdu">({d.name.ur})</span>
                      </Link>
                    </li>
                  ))}
                </ul>
                <Link to="/live" className="inline-flex items-center gap-2 rounded-xl bg-brand-700 px-4 py-2 font-semibold text-white hover:bg-brand-800">
                  <ScanLine className="h-4 w-4" aria-hidden="true" />
                  {t("home.liveCta")}
                </Link>
              </>
            ) : (
              c.meta.scanner_note && <BiText className="text-sm" text={c.meta.scanner_note} />
            )}
          </section>
          {c.sources.length > 0 && (
            <section>
              <h2 className="mb-2 text-lg font-bold">{t("library.sources")}</h2>
              <ul className="space-y-1 text-sm">
                {c.sources.map((url) => (
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
          <Disclaimer />
        </Card>
      )}
    </PageShell>
  );
}
