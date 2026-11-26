/* Live Scan: point the camera at a leaf and the answer appears on screen, like a scanner. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Camera, History, Lock, RotateCcw, ScanLine, VideoOff, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";

import { LiveDetails } from "../components/live/LiveDetails";
import { LiveViewport } from "../components/live/LiveViewport";
import { PhoneConnect } from "../components/live/PhoneConnect";
import { ResultCard } from "../components/result/ResultCard";
import { useCamera, type CameraProblem } from "../components/live/useCamera";
import { canvasToBlob, cropReticle, grabReticle, useLiveScan } from "../components/live/useLiveScan";
import { Button } from "../components/ui";
import { useI18n } from "../i18n";
import { api, ApiError, type PredictResponse } from "../lib/api";
import { checkFile } from "../lib/files";
import { useDistrict } from "../state/district";

const REPORT_SIDE = 896; // the saved photo for the full report: sharper than live frames

export function LiveScanPage() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { district } = useDistrict();
  const videoRef = useRef<HTMLVideoElement>(null);
  const viewRef = useRef<HTMLDivElement>(null);
  const photoInput = useRef<HTMLInputElement>(null);

  const [paused, setPaused] = useState(false);
  const [showHeatmap, setShowHeatmap] = useState(true);
  const [cropHint, setCropHint] = useState("");
  const [still, setStill] = useState<{ file: File; url: string } | null>(null);
  const [stillError, setStillError] = useState<unknown>(null);
  // the full report is shown straight from the server's answer (works even where saved scans are temporary)
  const [fullReport, setFullReport] = useState<{ result: PredictResponse; url: string } | null>(null);

  const model = useQuery({ queryKey: ["model"], queryFn: api.model, staleTime: Infinity });
  const camera = useCamera(videoRef, still === null);
  const running = camera.stream !== null && !paused && still === null && fullReport === null;
  const live = useLiveScan({ video: videoRef, view: viewRef, running, cropHint });
  const { liveView, showStill, reset } = live;

  // a short buzz on phones when a disease is recognised (no sound in a quiet field)
  useEffect(() => {
    if (liveView.justLocked && typeof navigator.vibrate === "function") navigator.vibrate(60);
  }, [liveView.justLocked, liveView.result]);

  // release the photo preview URL when it changes or the page closes
  useEffect(() => () => {
    if (still) URL.revokeObjectURL(still.url);
  }, [still]);

  const currentReticle = useCallback(
    async (side: number): Promise<HTMLCanvasElement | null> => {
      const view = viewRef.current;
      if (!view) return null;
      if (still) {
        const image = new Image();
        image.src = still.url;
        await image.decode();
        return cropReticle(image, { width: image.naturalWidth, height: image.naturalHeight }, view, side);
      }
      return videoRef.current ? grabReticle(videoRef.current, view, side) : null;
    },
    [still],
  );

  // analyse a still photo (camera app or file) with the same live pipeline
  useEffect(() => {
    if (!still) return;
    let alive = true;
    const frame = requestAnimationFrame(async () => {
      try {
        const canvas = await currentReticle(384);
        const blob = canvas && (await canvasToBlob(canvas));
        if (!blob || !alive) return;
        const answer = await api.predictLive(blob, { cropHint: cropHint || undefined });
        if (alive) showStill(answer);
      } catch (error) {
        if (alive) setStillError(error);
      }
    });
    return () => {
      alive = false;
      cancelAnimationFrame(frame);
    };
  }, [still, cropHint, currentReticle, showStill]);

  const report = useMutation({
    mutationFn: async () => {
      const canvas = await currentReticle(REPORT_SIDE);
      const blob = canvas && (await canvasToBlob(canvas, 0.92));
      if (!blob) throw new ApiError(400, t("live.noFrame"));
      const file = new File([blob], "live-scan.jpg", { type: "image/jpeg" });
      const result = await api.predict(file, { cropHint: cropHint || undefined, district: district || undefined, save: true });
      return { result, url: URL.createObjectURL(blob) };
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["scans"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
      setFullReport(data);
    },
  });

  function closeReport() {
    if (fullReport) URL.revokeObjectURL(fullReport.url);
    setFullReport(null);
  }

  function acceptPhoto(file: File | undefined) {
    if (!file) return;
    if (checkFile(file)) {
      setStillError(new ApiError(415, t("upload.errorType")));
      return;
    }
    setStillError(null);
    reset();
    setStill({ file, url: URL.createObjectURL(file) });
  }

  function backToCamera() {
    setStill(null);
    setStillError(null);
    reset();
    camera.retry();
  }

  const fallback = <CameraFallback problem={camera.problem} onPhoto={() => photoInput.current?.click()} onRetry={camera.retry} />;

  return (
    <div className="bg-gray-950 lg:bg-[linear-gradient(180deg,#0b3d1f_0,#0b3d1f_300px,#dcebdf_300px,#e7f2e9_100%)]">
      <div className="mx-auto grid max-w-[1480px] gap-0 lg:grid-cols-[minmax(0,1.3fr)_minmax(380px,0.7fr)] lg:gap-6 lg:px-6 lg:py-5">
        <div className="h-[min(66dvh,640px)] min-h-[380px] lg:sticky lg:top-[100px] lg:h-[calc(100dvh-128px)] lg:overflow-hidden lg:rounded-3xl lg:shadow-2xl">
          <LiveViewport
            videoRef={videoRef}
            viewRef={viewRef}
            liveView={liveView}
            lighting={still ? "ok" : live.lighting}
            running={running}
            paused={paused}
            mirrored={camera.facing === "user"}
            showHeatmap={showHeatmap}
            problem={camera.problem}
            starting={camera.starting && !still}
            canSwitch={camera.canSwitch}
            torchSupported={camera.torchSupported}
            torchOn={camera.torchOn}
            busyCapture={report.isPending}
            stillUrl={still?.url ?? null}
            onTogglePause={() => setPaused((p) => !p)}
            onSwitch={camera.switchCamera}
            onTorch={camera.toggleTorch}
            onHeatmap={() => setShowHeatmap((s) => !s)}
            onCapture={() => report.mutate()}
            onRetry={backToCamera}
            onPhoto={() => photoInput.current?.click()}
            fallback={fallback}
          />
        </div>

        <div className="rounded-t-3xl bg-white px-4 pt-5 pb-8 lg:rounded-3xl lg:p-6 lg:shadow-[0_10px_30px_-12px_rgba(6,39,22,0.35)]">
          <header className="mb-4">
            <h1 className="flex items-center gap-2 text-2xl font-bold text-gray-900">
              <ScanLine className="h-7 w-7 text-brand-700" aria-hidden="true" />
              {t("live.title")}
            </h1>
            <p className="mt-1 text-sm text-gray-600">{t("live.subtitle")}</p>
          </header>
          <LiveDetails
            liveView={liveView}
            stats={live.stats}
            error={still ? stillError : live.error}
            cropHint={cropHint}
            crops={model.data?.crops ?? []}
            onCropHint={(next) => {
              setCropHint(next); // a new crop hint changes what the model may answer: start the vote again
              reset();
            }}
            onCapture={() => report.mutate()}
            busyCapture={report.isPending}
            canCapture={running || still !== null}
            captureError={report.error}
          />
          {still && (
            <Button variant="secondary" className="mt-4 w-full" onClick={backToCamera}>
              <RotateCcw className="h-4 w-4" aria-hidden="true" />
              {t("live.backToCamera")}
            </Button>
          )}
          <div className="mt-5 hidden lg:block">
            <PhoneConnect compact />
          </div>
        </div>
      </div>

      {fullReport && (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/70 sm:items-center sm:p-4" role="dialog" aria-modal="true" aria-label={t("result.title")} data-testid="live-report">
          <div className="max-h-[94dvh] w-full max-w-5xl overflow-y-auto rounded-t-3xl bg-brand-50 p-3 sm:rounded-3xl sm:p-4">
            <div className="mb-3 flex flex-wrap items-center justify-end gap-2">
              {fullReport.result.scan_id && (
                <Button variant="secondary" onClick={() => navigate(`/history/${fullReport.result.scan_id}`)} data-testid="live-report-history">
                  <History className="h-4 w-4" aria-hidden="true" />
                  {t("live.openInHistory")}
                </Button>
              )}
              <Button variant="primary" onClick={closeReport} data-testid="live-report-close">
                <X className="h-4 w-4" aria-hidden="true" />
                {t("live.backToScan")}
              </Button>
            </div>
            <ResultCard result={fullReport.result} previewUrl={fullReport.url} loading={false} error={null} />
          </div>
        </div>
      )}

      <input
        ref={photoInput}
        type="file"
        accept="image/jpeg,image/png"
        capture="environment"
        className="hidden"
        data-testid="live-photo-input"
        onChange={(event) => {
          acceptPhoto(event.target.files?.[0]);
          event.target.value = "";
        }}
      />
    </div>
  );
}

function CameraFallback({ problem, onPhoto, onRetry }: { problem: CameraProblem | null; onPhoto: () => void; onRetry: () => void }) {
  const { t } = useI18n();
  const Icon = problem === "insecure" ? Lock : VideoOff;
  return (
    <div className="w-full max-w-md rounded-2xl bg-white p-5 text-gray-900 shadow-xl" role="alert" data-testid="live-camera-problem">
      <p className="flex items-center gap-2 text-lg font-bold">
        <Icon className="h-6 w-6 text-amber-500" aria-hidden="true" />
        {t(`live.problem.${problem ?? "other"}.title`)}
      </p>
      <p className="mt-2 text-sm text-gray-700">{t(`live.problem.${problem ?? "other"}.body`)}</p>
      <div className="mt-4 flex flex-wrap gap-2">
        <Button onClick={onPhoto} data-testid="live-take-photo">
          <Camera className="h-4 w-4" aria-hidden="true" />
          {t("live.takePhoto")}
        </Button>
        {problem !== "insecure" && problem !== "unsupported" && (
          <Button variant="secondary" onClick={onRetry}>
            <RotateCcw className="h-4 w-4" aria-hidden="true" />
            {t("live.retry")}
          </Button>
        )}
      </div>
      {problem === "insecure" && (
        <div className="mt-4">
          <PhoneConnect compact />
        </div>
      )}
    </div>
  );
}
