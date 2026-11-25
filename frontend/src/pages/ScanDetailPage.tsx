import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Columns2, Share2, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router";

import { FeedbackControl } from "../components/result/FeedbackControl";
import { TopPredictions } from "../components/result/TopPredictions";
import { Button, Card, Disclaimer, ErrorBanner, Skeleton } from "../components/ui";
import { useI18n } from "../i18n";
import { api } from "../lib/api";
import { formatDate, percent, probability } from "../lib/format";

export function ScanDetailPage() {
  const { id = "" } = useParams();
  const { t, lang, crop } = useI18n();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [compare, setCompare] = useState(false);
  const scan = useQuery({ queryKey: ["scan", id], queryFn: () => api.scan(id) });
  const reference = useQuery({
    queryKey: ["disease", scan.data?.class_id],
    queryFn: () => api.disease(scan.data!.class_id),
    enabled: !!scan.data,
  });
  const remove = useMutation({
    mutationFn: () => api.deleteScan(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["scans"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
      navigate("/history");
    },
  });
  const s = scan.data;

  async function share() {
    if (!s) return;
    const text = `CropDoc GB: ${s.disease} (${s.crop}), ${percent(s.confidence)}. ${t("result.disclaimer")}`;
    if (navigator.share) await navigator.share({ title: "CropDoc GB", text }).catch(() => undefined);
    else await navigator.clipboard?.writeText(text);
  }

  return (
    <div className="page-backdrop min-h-[60vh]">
      <div className="mx-auto max-w-2xl px-4 py-6">
        {scan.isPending && <Skeleton className="h-96 w-full" />}
        {scan.isError && <ErrorBanner error={scan.error} />}
        {s && (
          <Card className="overflow-hidden p-0 sm:p-0">
            <div className="relative">
              <img src={s.image_url} alt={t("history.yourPhoto")} className="aspect-[4/3] w-full object-cover" />
              <Link to="/history" className="absolute start-3 top-3 rounded-full bg-white p-2 shadow" aria-label={t("history.back")}>
                <ArrowLeft className="h-5 w-5 text-brand-800 rtl:rotate-180" aria-hidden="true" />
              </Link>
              <button type="button" onClick={share} className="absolute end-3 top-3 flex items-center gap-1.5 rounded-xl bg-white px-3 py-2 text-sm font-semibold text-brand-800 shadow">
                <Share2 className="h-4 w-4" aria-hidden="true" />
                {t("result.share")}
              </button>
            </div>
            <div className="space-y-4 p-5">
              <div>
                <p className="font-bold text-gray-900">{t("history.recognition")}</p>
                <p className="text-sm text-gray-600 latin">{formatDate(s.created_at, lang)}</p>
              </div>
              <p className="font-semibold text-gray-800">{t("history.topMatch")}</p>
              <div className="rounded-xl bg-brand-50 p-4">
                <p className="text-xl font-bold text-gray-900" data-testid="scan-disease">
                  {s.disease} <span className="text-base font-normal text-gray-700">({crop(s.crop)})</span>
                </p>
                <p className="text-sm text-gray-700">
                  {t("result.confidence")}: <span dir="ltr" className="latin">{probability(s.confidence)}</span> · {t(`status.${s.status}`)}
                </p>
              </div>
              <FeedbackControl scanId={s.id} existing={s.feedback} />
              <Button variant="secondary" onClick={() => setCompare((open) => !open)} aria-expanded={compare}>
                <Columns2 className="h-4 w-4" aria-hidden="true" />
                {t("history.compare")}
              </Button>
              {compare && (
                <div className="grid grid-cols-2 gap-3" data-testid="compare">
                  <figure>
                    <img src={s.image_url} alt={t("history.yourPhoto")} className="aspect-square w-full rounded-xl object-cover" />
                    <figcaption className="mt-1 text-center text-sm font-semibold">{t("history.yourPhoto")}</figcaption>
                  </figure>
                  <figure>
                    {reference.data?.images[0] ? (
                      <img src={reference.data.images[0]} alt={t("history.reference")} className="aspect-square w-full rounded-xl object-cover" />
                    ) : (
                      <div className="aspect-square w-full rounded-xl bg-gray-100" />
                    )}
                    <figcaption className="mt-1 text-center text-sm font-semibold">
                      {t("history.reference")}: {s.disease}
                    </figcaption>
                  </figure>
                </div>
              )}
              {s.gradcam_url && (
                <figure>
                  <img src={s.gradcam_url} alt={t("result.gradcam")} className="mx-auto w-full max-w-xs rounded-xl" />
                  <figcaption className="mt-1 text-center text-xs text-gray-600">{t("result.gradcamHelp")}</figcaption>
                </figure>
              )}
              <TopPredictions items={s.top3} />
              <Disclaimer />
              <div className="flex justify-between">
                <Link to={`/library/${encodeURIComponent(s.class_id)}`} className="font-semibold text-brand-800 underline">
                  {t("nav.library")}
                </Link>
                <Button variant="ghost" className="text-red-700" onClick={() => window.confirm(t("history.confirmDelete")) && remove.mutate()}>
                  <Trash2 className="h-4 w-4" aria-hidden="true" />
                  {t("history.delete")}
                </Button>
              </div>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
