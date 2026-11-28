/* Right/bottom panel of the live scanner: what the model sees now, explained for a farmer. */
import { AlertOctagon, BookOpen, CheckCircle2, FileText, Leaf, Lightbulb, ScanLine, Sun, Timer } from "lucide-react";
import { Link } from "react-router";

import { useI18n } from "../../i18n";
import { probability } from "../../lib/format";
import { statusTone, type LiveView } from "../../lib/live";
import { RetakeAdvice } from "../report/Bilingual";
import { CategoryBadge, Disclaimer, ErrorBanner } from "../ui";
import type { LiveStats } from "./useLiveScan";

interface Props {
  liveView: LiveView;
  stats: LiveStats;
  error: unknown;
  cropHint: string;
  crops: string[];
  onCropHint: (crop: string) => void;
  onCapture: () => void;
  busyCapture: boolean;
  canCapture: boolean;
  captureError: unknown;
}

const BAR = { good: "bg-emerald-500", warn: "bg-amber-400", bad: "bg-red-500", idle: "bg-gray-300" } as const;

export function LiveDetails(props: Props) {
  const { t, crop } = useI18n();
  const { liveView, stats } = props;
  const result = liveView.result;
  const tone = statusTone(liveView.phase);
  const locked = liveView.phase === "locked";

  return (
    <div className="flex flex-col gap-4" data-testid="live-details">
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex min-w-0 flex-1 items-center gap-2 text-sm font-semibold text-gray-800">
          <span className="shrink-0">{t("upload.cropHint")}</span>
          <select
            value={props.cropHint}
            onChange={(event) => props.onCropHint(event.target.value)}
            className="min-w-0 flex-1 rounded-lg border border-gray-300 bg-white px-3 py-2 font-normal"
            data-testid="live-crop-hint"
          >
            <option value="">{t("upload.cropAny")}</option>
            {props.crops.map((name) => (
              <option key={name} value={name}>
                {crop(name)}
              </option>
            ))}
          </select>
        </label>
        {stats.roundTripMs != null && (
          <span dir="ltr" className="latin flex items-center gap-1 rounded-full bg-gray-100 px-2.5 py-1 text-xs font-semibold text-gray-700" title={t("live.speedHelp")}>
            <Timer className="h-3.5 w-3.5" aria-hidden="true" />
            {Math.round(stats.roundTripMs)} ms
          </span>
        )}
      </div>

      {props.error != null && <ErrorBanner error={props.error} />}

      {!result ? (
        <div className="rounded-2xl border-2 border-dashed border-brand-200 bg-brand-50/60 p-5" data-testid="live-empty">
          <p className="flex items-center gap-2 text-lg font-bold text-gray-900">
            <ScanLine className="h-6 w-6 text-brand-700" aria-hidden="true" />
            {t("live.howTitle")}
          </p>
          <ol className="mt-3 space-y-2 text-[15px] text-gray-800">
            {["live.tip1", "live.tip2", "live.tip3", "live.tip4"].map((key, index) => (
              <li key={key} className="flex items-start gap-2.5">
                <span className="latin flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-700 text-xs font-bold text-white">{index + 1}</span>
                {t(key)}
              </li>
            ))}
          </ol>
          <p className="mt-3 flex items-center gap-2 text-sm text-gray-600">
            <Sun className="h-4 w-4 text-amber-500" aria-hidden="true" />
            {t("live.tipLight")}
          </p>
        </div>
      ) : liveView.phase === "retake" ? (
        <RetakeAdvice issues={result.quality?.issues ?? []} />
      ) : (
        <>
          {!locked && (
            <div
              className={`flex items-start gap-3 rounded-xl border p-4 ${tone === "bad" ? "border-red-200 bg-red-50 text-red-950" : "border-amber-300 bg-amber-50 text-amber-950"}`}
              role="status"
              data-testid="live-warning"
            >
              <AlertOctagon className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
              <div>
                <p className="font-bold">
                  {liveView.phase === "unsupported" ? t("result.unsupported") : liveView.phase === "steadying" ? t("live.holdSteady") : t("result.lowConfidence")}
                </p>
                <p className="mt-1 text-sm">
                  {liveView.phase === "unsupported" ? t("result.unsupportedBody") : liveView.phase === "steadying" ? t("live.holdSteadyBody") : t("result.lowConfidenceBody")}
                </p>
              </div>
            </div>
          )}

          <div className={`rounded-2xl border p-4 ${locked ? "border-emerald-200 bg-emerald-50/70" : "border-gray-200 bg-gray-50"}`} data-testid="live-result">
            {!locked && <p className="mb-1 text-xs font-bold tracking-wide text-gray-600 uppercase">{t("result.bestGuess")}</p>}
            <div className="flex items-start gap-3">
              <span
                className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-full ${locked ? (result.healthy ? "bg-emerald-600" : "bg-brand-700") : "bg-gray-400"} text-white`}
                aria-hidden="true"
              >
                {result.healthy ? <CheckCircle2 className="h-6 w-6" /> : <Leaf className="h-6 w-6" />}
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-2xl leading-tight font-bold text-gray-900" data-testid="live-disease">
                  {result.disease}
                </p>
                {result.disease_info.report?.name.ur && (
                  <p lang="ur" dir="rtl" className="urdu text-right text-lg font-semibold text-gray-800" data-testid="live-disease-ur">
                    {result.disease_info.report.name.ur} ({result.disease_info.report.crop.ur})
                  </p>
                )}
                <p className="mt-0.5 flex flex-wrap items-center gap-2 text-gray-700">
                  <span>{crop(result.crop)}</span>
                  {result.disease_info.category && <CategoryBadge category={result.disease_info.category} />}
                </p>
              </div>
            </div>

            <div className="mt-4">
              <div className="mb-1 flex items-center justify-between text-sm font-semibold text-gray-800">
                <span>{t("result.confidence")}</span>
                <span dir="ltr" className="latin" data-testid="live-confidence">
                  {probability(liveView.confidence)}
                </span>
              </div>
              <div className="h-2.5 overflow-hidden rounded-full bg-gray-200" role="presentation">
                <div className={`h-full rounded-full transition-all duration-500 ${BAR[tone]}`} style={{ width: `${Math.round(liveView.confidence * 100)}%` }} />
              </div>
              {liveView.window > 1 && (
                <p className="mt-2 flex items-center gap-2 text-xs text-gray-600" data-testid="live-stability">
                  <span className="flex gap-1" aria-hidden="true">
                    {Array.from({ length: liveView.window }, (_, index) => (
                      <span key={index} className={`h-2 w-5 rounded-full ${index < liveView.agreement ? BAR[tone] : "bg-gray-200"}`} />
                    ))}
                  </span>
                  {t("live.stability", { n: liveView.agreement, total: liveView.window })}
                </p>
              )}
            </div>

            {result.disease_info.description && <p className="mt-4 text-[15px] text-gray-800">{result.disease_info.description}</p>}
          </div>

          {result.top3.length > 1 && (
            <div className="rounded-2xl border border-gray-100 bg-white p-4 shadow-sm">
              <h3 className="mb-2 text-sm font-bold text-gray-900">{t("result.top3")}</h3>
              <ul className="space-y-2">
                {result.top3.map((item) => (
                  <li key={item.class_id} className="text-sm">
                    <div className="flex justify-between gap-2">
                      <span className="truncate text-gray-800">
                        {item.disease} <span className="text-gray-500">({crop(item.crop)})</span>
                      </span>
                      <span dir="ltr" className="latin shrink-0 font-semibold text-gray-900">{probability(item.probability)}</span>
                    </div>
                    <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-gray-100">
                      <div className="h-full rounded-full bg-brand-500" style={{ width: `${Math.round(item.probability * 100)}%` }} />
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {liveView.phase !== "unsupported" && result.disease_info.recommendations.length > 0 && (
            <div className="rounded-2xl border border-gray-100 bg-white p-4 shadow-sm">
              <h3 className="mb-2 flex items-center gap-2 text-base font-bold text-gray-900">
                <Lightbulb className="h-5 w-5 text-amber-500" aria-hidden="true" />
                {t("result.recommendations")}
              </h3>
              <ul className="space-y-2">
                {result.disease_info.recommendations.slice(0, 4).map((tip) => (
                  <li key={tip} className="flex items-start gap-2.5 text-[15px] text-gray-800">
                    <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-brand-700" aria-hidden="true" />
                    {tip}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={props.onCapture}
              disabled={!props.canCapture || props.busyCapture}
              className="inline-flex flex-1 items-center justify-center gap-2 rounded-xl bg-brand-700 px-5 py-3 text-[15px] font-semibold text-white shadow-sm hover:bg-brand-800 disabled:cursor-not-allowed disabled:bg-gray-400"
              data-testid="live-full-report"
            >
              <FileText className="h-5 w-5" aria-hidden="true" />
              {props.busyCapture ? t("result.analyzing") : t("live.fullReport")}
            </button>
            <Link
              to={`/library/${encodeURIComponent(result.class_id)}`}
              className="inline-flex items-center justify-center gap-2 rounded-xl border border-brand-700 bg-white px-4 py-3 text-[15px] font-semibold text-brand-800 hover:bg-brand-50"
            >
              <BookOpen className="h-5 w-5" aria-hidden="true" />
              {t("live.openLibrary")}
            </Link>
          </div>
        </>
      )}

      {props.captureError != null && <ErrorBanner error={props.captureError} />}
      <Disclaimer />
    </div>
  );
}
