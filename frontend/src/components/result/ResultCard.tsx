/* Plant Analysis Report: the model's answer + bilingual (English/Urdu) knowledge, side by side.
   Variants: healthy, disease detected, not sure, not recognised, and "please take another photo". */
import {
  AlertOctagon,
  BookOpen,
  Bot,
  Camera,
  CheckCircle2,
  ClipboardList,
  Download,
  FileSearch,
  Leaf,
  Lightbulb,
  RotateCcw,
  Save,
  Share2,
  Stethoscope,
  Zap,
} from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";

import { useI18n } from "../../i18n";
import type { PredictResponse } from "../../lib/api";
import { percent, probability } from "../../lib/format";
import { useDistrict } from "../../state/district";
import { BiHeading, BiList, BiText, RetakeAdvice, ReviewNote, RiskBadge, StatusPill, viewOf } from "../report/Bilingual";
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
  /** "Scan another plant": clears the current photo and result. */
  onReset?: () => void;
}

function Row({ label, labelUr, children }: { label: string; labelUr: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-1 border-b border-gray-100 py-2.5 last:border-0 sm:grid-cols-[11rem_1fr] sm:gap-3">
      <dt className="text-sm font-semibold text-gray-600">
        <span lang="en">{label}</span> <span aria-hidden="true">/</span>{" "}
        <span lang="ur" dir="rtl" className="urdu">{labelUr}</span>
      </dt>
      <dd className="text-gray-900">{children}</dd>
    </div>
  );
}

export function ResultCard({ result, previewUrl, loading, error, onSave, saving, onReset }: Props) {
  const { t, crop, lang } = useI18n();
  const { district } = useDistrict();
  const [copied, setCopied] = useState(false);
  const report = result?.disease_info.report ?? null;
  const view = result ? viewOf(result.status, result.healthy) : null;
  const showsDisease = view === "healthy" || view === "disease" || view === "unsure";

  async function share() {
    if (!result) return;
    const name = report ? `${report.name.en} / ${report.name.ur}` : result.disease;
    const text = `CropDoc GB: ${name} (${result.crop}), ${t("result.confidence")} ${percent(result.confidence)}. ${result.disclaimer}`;
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
        <span className="flex h-10 w-10 items-center justify-center rounded-full bg-brand-700 text-white" aria-hidden="true">
          <ClipboardList className="h-6 w-6" />
        </span>
        <h2 className="flex flex-1 flex-wrap items-baseline gap-x-3 text-xl font-bold text-gray-900 sm:text-2xl">
          <span lang="en">{t("report.title")}</span>
          <span lang="ur" dir="rtl" className="urdu text-lg font-semibold text-gray-700">پودے کی تجزیاتی رپورٹ</span>
        </h2>
        {result && view !== "retake" && (
          <span
            className={`flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-sm font-bold ${view === "unsure" || view === "unsupported" ? "bg-amber-100 text-amber-900" : "bg-brand-100 text-brand-800"}`}
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

      {!loading && error == null && result && view && (
        <div className="space-y-5">
          {!showsDisease && <StatusPill view={view} />}

          {view === "retake" && <RetakeAdvice issues={result.quality?.issues ?? []} />}

          {(view === "unsure" || view === "unsupported") && (
            <div
              className={`flex items-start gap-3 rounded-xl border p-4 ${view === "unsupported" ? "border-red-200 bg-red-50 text-red-950" : "border-amber-300 bg-amber-50 text-amber-950"}`}
              role="alert"
              data-testid="uncertain-warning"
            >
              <AlertOctagon className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
              <div className="flex-1">
                <p className="font-bold">{view === "unsupported" ? t("result.unsupported") : t("result.lowConfidence")}</p>
                <p className="mt-1 text-sm">{view === "unsupported" ? t("result.unsupportedBody") : t("result.lowConfidenceBody")}</p>
                <p lang="ur" dir="rtl" className="urdu mt-1 text-right text-sm">
                  {view === "unsupported"
                    ? "یہ معاون پتا نہیں لگتا، یا یہ ایسی فصل ہو سکتی ہے جسے ماڈل نہیں جانتا۔ براہ کرم زرعی ماہر سے مشورہ کریں۔"
                    : "ماڈل کو اس تصویر پر یقین نہیں۔ دن کی روشنی میں ایک پتے کی صاف قریبی تصویر لیں، یا پتا کسی ماہر کو دکھائیں۔"}
                </p>
              </div>
            </div>
          )}

          {showsDisease && (
            <div className="grid gap-5 md:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
              {previewUrl && <img src={previewUrl} alt={t("upload.preview")} className="aspect-square w-full rounded-xl object-cover shadow-sm" />}
              <dl className={`rounded-xl border px-4 ${view === "unsure" ? "border-gray-200 bg-gray-50" : "border-brand-100 bg-brand-50/60"} ${previewUrl ? "" : "md:col-span-2"}`} data-testid="report-table">
                <Row label="Plant" labelUr="پودا">
                  <span className="me-3">{report?.crop.en || crop(result.crop)}</span>
                  {report?.crop.ur && <span lang="ur" dir="rtl" className="urdu inline-block text-gray-700">{report.crop.ur}</span>}
                </Row>
                <Row label={view === "unsure" ? "Possible disease" : "Disease"} labelUr={view === "unsure" ? "ممکنہ بیماری" : "بیماری"}>
                  <span className="block text-lg font-bold" data-testid="disease-name">{result.disease}</span>
                  {report?.name.ur && <span lang="ur" dir="rtl" className="urdu block text-right text-lg font-semibold text-gray-800 sm:text-left">{report.name.ur}</span>}
                </Row>
                <Row label="Status" labelUr="صورتحال">
                  <StatusPill view={view} />
                </Row>
                <Row label="Confidence" labelUr="تشخیص کا اعتماد">
                  <span dir="ltr" className="latin font-semibold">{probability(result.confidence)}</span>
                  <span className="ms-2 text-xs text-gray-500">{t("report.confidenceNote")}</span>
                </Row>
                {report?.risk_level && (
                  <Row label="Severity (risk)" labelUr="بیماری کی شدت (خطرہ)">
                    <RiskBadge level={report.risk_level} reason={report.risk_reason} compact />
                    <p className="mt-1 text-xs text-gray-500">{t("report.riskNote")}</p>
                  </Row>
                )}
              </dl>
            </div>
          )}

          {showsDisease && report && (
            <>
              <BiText text={report.description} />
              {report.risk_level && report.risk_level !== "none" && <RiskBadge level={report.risk_level} reason={report.risk_reason} />}
              <section className="space-y-2" data-testid="report-symptoms">
                <BiHeading en="Symptoms" ur="علامات" icon={<Stethoscope className="h-5 w-5 text-brand-700" aria-hidden="true" />} />
                <BiList list={{ en: [...report.symptoms_early.en, ...report.symptoms_advanced.en], ur: [...report.symptoms_early.ur, ...report.symptoms_advanced.ur] }} />
              </section>
              {report.causes.en.length > 0 && (
                <section className="space-y-2" data-testid="report-causes">
                  <BiHeading en="Possible causes" ur="بیماری کی وجوہات" icon={<FileSearch className="h-5 w-5 text-brand-700" aria-hidden="true" />} />
                  <BiList list={report.causes} />
                </section>
              )}
              <section className="space-y-2 rounded-xl border border-gray-100 bg-white p-4 shadow-sm" data-testid="report-actions">
                <BiHeading en="Recommended actions" ur="تجویز کردہ اقدامات" icon={<Lightbulb className="h-5 w-5 text-amber-500" aria-hidden="true" />} />
                <BiList list={report.immediate_actions} bullet="✓" />
                {!report.healthy && <BiText className="rounded-lg bg-brand-50 p-3 text-sm font-semibold" text={report.extension_fallback} />}
                <ReviewNote urdu={report.urdu_needs_review} />
              </section>
            </>
          )}

          {showsDisease && !report && view !== "unsure" && result.disease_info.recommendations.length > 0 && (
            <div className="rounded-xl border border-gray-100 bg-white p-4 shadow-sm">
              {result.disease_info.description && <p className="mb-3 text-[15px] text-gray-800">{result.disease_info.description}</p>}
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
            </div>
          )}

          {showsDisease && (
            <div className="grid gap-5 md:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
              <TopPredictions items={result.top3} />
              <GradcamViewer overlay={result.gradcam_png} heatmap={result.heatmap_png} modelView={result.model_view_jpeg} />
            </div>
          )}

          <Disclaimer />
          {result.thresholds.provisional && <p className="text-xs text-gray-500">{t("result.provisional")}</p>}

          <div className="no-print space-y-3">
            {showsDisease && (
              <div className="flex flex-wrap gap-2" data-testid="report-buttons">
                <Link to={`/library/${encodeURIComponent(result.class_id)}`} className="inline-flex items-center gap-2 rounded-xl bg-brand-700 px-4 py-2.5 text-[15px] font-semibold text-white hover:bg-brand-800">
                  <BookOpen className="h-4 w-4" aria-hidden="true" />
                  {t("report.fullDetails")}
                </Link>
                {!result.healthy && (
                  <Link to={`/library/${encodeURIComponent(result.class_id)}#treatment`} className="inline-flex items-center gap-2 rounded-xl border border-brand-700 bg-white px-4 py-2.5 text-[15px] font-semibold text-brand-800 hover:bg-brand-50">
                    <Stethoscope className="h-4 w-4" aria-hidden="true" />
                    {t("report.treatment")}
                  </Link>
                )}
                <Link
                  to={`/assistant?class_id=${encodeURIComponent(result.class_id)}`}
                  className="inline-flex items-center gap-2 rounded-xl border border-brand-700 bg-white px-4 py-2.5 text-[15px] font-semibold text-brand-800 hover:bg-brand-50"
                  data-testid="ask-assistant"
                >
                  <Bot className="h-4 w-4" aria-hidden="true" />
                  {t("report.askAssistant")}
                </Link>
              </div>
            )}
            {showsDisease && <FeedbackControl key={result.scan_id ?? "unsaved"} scanId={result.scan_id} />}
            <div className="flex flex-wrap items-center gap-2">
              {result.saved ? (
                <span className="flex items-center gap-1.5 text-sm font-semibold text-brand-800" data-testid="saved-indicator">
                  <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                  {t("result.saved")}
                </span>
              ) : (
                onSave &&
                showsDisease && (
                  <Button variant="secondary" onClick={onSave} disabled={saving}>
                    <Save className="h-4 w-4" aria-hidden="true" />
                    {t("report.save")}
                  </Button>
                )
              )}
              {onReset && (
                <Button variant="accent" onClick={onReset} data-testid="scan-another">
                  {view === "retake" ? <Camera className="h-4 w-4" aria-hidden="true" /> : <RotateCcw className="h-4 w-4" aria-hidden="true" />}
                  {view === "retake" ? t("report.retake") : t("report.scanAnother")}
                </Button>
              )}
              {showsDisease && (
                <>
                  <Button variant="ghost" onClick={share}>
                    <Share2 className="h-4 w-4" aria-hidden="true" />
                    {t("result.share")}
                  </Button>
                  <Button variant="ghost" onClick={() => window.print()}>
                    <Download className="h-4 w-4" aria-hidden="true" />
                    {t("result.download")}
                  </Button>
                </>
              )}
              {copied && <span className="text-sm text-gray-600" role="status">{t("result.copied")}</span>}
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}
