/* Prediction Result card (matches the primary design), with low-confidence / unsupported variants. */
import { AlertOctagon, CheckCircle2, Download, Leaf, Lightbulb, Save, Share2, ShieldQuestion, Zap } from "lucide-react";
import { useState } from "react";

import { useI18n } from "../../i18n";
import type { PredictResponse } from "../../lib/api";
import { percent, probability } from "../../lib/format";
import { useDistrict } from "../../state/district";
import { Button, Card, Disclaimer, ErrorBanner, Skeleton } from "../ui";
import { FeedbackControl } from "./FeedbackControl";
import { GradcamViewer } from "./GradcamViewer";
import { TopPredictions } from "./TopPredictions";

interface Props {
  result: PredictResponse | null;
  previewUrl: string | null;
  loading: boolean;
  error: unknown;
  onSave?: () => void;
  saving?: boolean;
}

export function ResultCard({ result, previewUrl, loading, error, onSave, saving }: Props) {
  const { t, crop, lang } = useI18n();
  const { district } = useDistrict();
  const [copied, setCopied] = useState(false);
  const confident = result?.status === "confident";
  const unsupported = result?.status === "not_a_leaf_or_unsupported_crop";

  async function share() {
    if (!result) return;
    const text = `CropDoc GB: ${result.disease} (${result.crop}), ${t("result.confidence")} ${percent(result.confidence)}. ${result.disclaimer}`;
    if (navigator.share) {
      try {
        await navigator.share({ title: "CropDoc GB", text });
        return;
      } catch {
        /* cancelled: fall back to copying */
      }
    }
    await navigator.clipboard?.writeText(text);
    setCopied(true);
  }

  return (
    <Card className="print-card" aria-live="polite" data-testid="result-card">
      <div className="print-only mb-4">
        <h1 className="text-2xl font-bold">{t("result.reportTitle")}</h1>
        <p className="text-sm">
          {t("result.reportDate")}: {new Date().toLocaleString(lang === "ur" ? "ur-PK" : "en-GB")} {district && `· ${district}`}
        </p>
      </div>
      <div className="mb-5 flex flex-wrap items-center gap-3">
        <span
          className={`flex h-10 w-10 items-center justify-center rounded-full ${result && !confident ? "bg-amber-500" : "bg-brand-700"} text-white`}
          aria-hidden="true"
        >
          {result && !confident ? <ShieldQuestion className="h-6 w-6" /> : <CheckCircle2 className="h-6 w-6" />}
        </span>
        <h2 className="flex-1 text-xl font-bold text-gray-900 sm:text-2xl">{t("result.title")}</h2>
        {result && (
          <span
            className={`flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-sm font-bold ${confident ? "bg-brand-100 text-brand-800" : "bg-amber-100 text-amber-900"}`}
            data-testid="confidence-badge"
          >
            <Zap className="h-4 w-4" aria-hidden="true" />
            {t("result.confidence")}: <span dir="ltr" className="latin">{probability(result.confidence)}</span>
          </span>
        )}
      </div>

      {loading && (
        <div className="space-y-4" data-testid="result-loading">
          <p className="text-sm font-semibold text-brand-800">{t("result.analyzing")}</p>
          <div className="grid gap-5 md:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
            <Skeleton className="aspect-square w-full" />
            <div className="space-y-3">
              <Skeleton className="h-28 w-full" />
              <Skeleton className="h-32 w-full" />
            </div>
          </div>
          <Skeleton className="h-24 w-full" />
        </div>
      )}

      {!loading && error != null && <ErrorBanner error={error} />}

      {!loading && error == null && !result && (
        <div className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-gray-200 px-6 py-16 text-center text-gray-600" data-testid="result-empty">
          <Leaf className="mb-3 h-10 w-10 text-brand-600" aria-hidden="true" />
          <p className="max-w-sm">{t("result.empty")}</p>
        </div>
      )}

      {!loading && error == null && result && (
        <div className="space-y-5">
          {!confident && (
            <div
              className={`flex items-start gap-3 rounded-xl border p-4 ${unsupported ? "border-red-200 bg-red-50 text-red-950" : "border-amber-300 bg-amber-50 text-amber-950"}`}
              role="alert"
              data-testid="uncertain-warning"
            >
              <AlertOctagon className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
              <div>
                <p className="font-bold">{unsupported ? t("result.unsupported") : t("result.lowConfidence")}</p>
                <p className="mt-1 text-sm">{unsupported ? t("result.unsupportedBody") : t("result.lowConfidenceBody")}</p>
              </div>
            </div>
          )}

          <div className="grid gap-5 md:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
            {previewUrl && (
              <img src={previewUrl} alt={t("upload.preview")} className="aspect-square w-full rounded-xl object-cover shadow-sm" />
            )}
            <div className="space-y-4">
              <div className={`rounded-xl border p-4 ${confident ? "border-brand-100 bg-brand-50" : "border-gray-200 bg-gray-50"}`}>
                {!confident && <p className="mb-1 text-xs font-bold uppercase tracking-wide text-gray-600">{t("result.bestGuess")}</p>}
                <div className="flex items-start gap-3">
                  <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-brand-200 text-brand-800" aria-hidden="true">
                    <Leaf className="h-6 w-6" />
                  </span>
                  <div>
                    <p className="text-2xl font-bold text-gray-900" data-testid="disease-name">
                      {result.disease}
                    </p>
                    <p className="text-gray-700">({crop(result.crop)})</p>
                  </div>
                </div>
                {result.disease_info.description && <p className="mt-3 text-[15px] text-gray-800">{result.disease_info.description}</p>}
              </div>
              {!unsupported && result.disease_info.recommendations.length > 0 && (
                <div className="rounded-xl border border-gray-100 bg-white p-4 shadow-sm">
                  <h3 className="mb-3 flex items-center gap-2 text-base font-bold text-gray-900">
                    <Lightbulb className="h-5 w-5 text-amber-500" aria-hidden="true" />
                    {t("result.recommendations")}
                  </h3>
                  <ul className="space-y-2">
                    {result.disease_info.recommendations.map((tip) => (
                      <li key={tip} className="flex items-start gap-2.5 text-[15px] text-gray-800">
                        <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-brand-700" aria-hidden="true" />
                        {tip}
                      </li>
                    ))}
                  </ul>
                  {result.disease_info.needs_review && <p className="mt-3 text-xs text-gray-500">{t("result.needsReview")}</p>}
                </div>
              )}
            </div>
          </div>

          <div className="grid gap-5 md:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
            <TopPredictions items={result.top3} />
            <GradcamViewer overlay={result.gradcam_png} heatmap={result.heatmap_png} modelView={result.model_view_jpeg} />
          </div>

          <Disclaimer />
          {result.thresholds.provisional && <p className="text-xs text-gray-500">{t("result.provisional")}</p>}

          <div className="no-print space-y-3">
            <FeedbackControl key={result.scan_id ?? "unsaved"} scanId={result.scan_id} />
            <div className="flex flex-wrap items-center gap-2">
              {result.saved ? (
                <span className="flex items-center gap-1.5 text-sm font-semibold text-brand-800" data-testid="saved-indicator">
                  <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                  {t("result.saved")}
                </span>
              ) : (
                onSave && (
                  <Button variant="secondary" onClick={onSave} disabled={saving}>
                    <Save className="h-4 w-4" aria-hidden="true" />
                    {t("result.save")}
                  </Button>
                )
              )}
              <Button variant="ghost" onClick={share}>
                <Share2 className="h-4 w-4" aria-hidden="true" />
                {t("result.share")}
              </Button>
              <Button variant="ghost" onClick={() => window.print()}>
                <Download className="h-4 w-4" aria-hidden="true" />
                {t("result.download")}
              </Button>
              {copied && <span className="text-sm text-gray-600" role="status">{t("result.copied")}</span>}
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}
