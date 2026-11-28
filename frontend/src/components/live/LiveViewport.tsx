/* Camera view with the scan box, live heatmap, status chip and camera-app style controls. */
import { Aperture, Camera, Flashlight, FlashlightOff, Layers, Pause, Play, RotateCcw, SwitchCamera, VideoOff } from "lucide-react";
import type { ReactNode, RefObject } from "react";

import { useI18n } from "../../i18n";
import { statusTone, type Lighting, type LiveView } from "../../lib/live";
import { probability } from "../../lib/format";
import type { CameraProblem } from "./useCamera";
import { RETICLE_FRACTION } from "./useLiveScan";

const TONE_COLORS = {
  good: { corner: "border-emerald-400", chip: "bg-emerald-500 text-white", line: "via-emerald-300" },
  warn: { corner: "border-amber-300", chip: "bg-amber-400 text-gray-950", line: "via-amber-200" },
  bad: { corner: "border-red-400", chip: "bg-red-500 text-white", line: "via-red-300" },
  idle: { corner: "border-white", chip: "bg-black/60 text-white", line: "via-white" },
} as const;

interface Props {
  videoRef: RefObject<HTMLVideoElement | null>;
  viewRef: RefObject<HTMLDivElement | null>;
  liveView: LiveView;
  lighting: Lighting;
  running: boolean;
  paused: boolean;
  mirrored: boolean;
  showHeatmap: boolean;
  problem: CameraProblem | null;
  starting: boolean;
  canSwitch: boolean;
  torchSupported: boolean;
  torchOn: boolean;
  busyCapture: boolean;
  stillUrl: string | null;
  onTogglePause: () => void;
  onSwitch: () => void;
  onTorch: () => void;
  onHeatmap: () => void;
  onCapture: () => void;
  onRetry: () => void;
  onPhoto: () => void;
  fallback: ReactNode;
}

export function LiveViewport({ videoRef, viewRef, ...props }: Props) {
  const { t, crop } = useI18n();
  const { liveView, running, paused, problem } = props;
  const tone = running || props.stillUrl ? statusTone(liveView.phase) : "idle";
  const colors = TONE_COLORS[liveView.result ? tone : "idle"];
  const result = liveView.result;
  const boxSide = `min(${RETICLE_FRACTION * 100}cqw, ${RETICLE_FRACTION * 100}cqh)`;

  let message: string;
  if (paused) message = t("live.paused");
  else if (props.lighting === "dark") message = t("live.tooDark");
  else if (props.lighting === "bright") message = t("live.tooBright");
  else if (!result) message = t("live.pointAtLeaf");
  else if (liveView.phase === "locked") message = `${result.disease} · ${crop(result.crop)}`;
  else if (liveView.phase === "steadying") message = t("live.holdSteady");
  else if (liveView.phase === "retake")
    message = result.quality?.issues.includes("too_dark")
      ? t("live.tooDark")
      : result.quality?.issues.includes("too_bright")
        ? t("live.tooBright")
        : t("live.blurry");
  else if (liveView.phase === "unsure") message = t("live.moveCloser");
  else message = t("live.noLeaf");

  return (
    <div
      ref={viewRef}
      className="relative h-full w-full overflow-hidden bg-gray-950 [container-type:size]"
      data-testid="live-viewport"
    >
      {props.stillUrl ? (
        <img src={props.stillUrl} alt={t("upload.preview")} className="absolute inset-0 h-full w-full object-cover" />
      ) : (
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          className={`absolute inset-0 h-full w-full object-cover ${props.mirrored ? "-scale-x-100" : ""}`}
          data-testid="live-video"
        />
      )}

      {problem && !props.stillUrl ? (
        <div className="absolute inset-0 flex items-center justify-center overflow-y-auto bg-gray-950/95 p-5">{props.fallback}</div>
      ) : (
        <>
          {/* darken everything outside the scan box so the farmer knows where to aim */}
          <div
            className="pointer-events-none absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 rounded-3xl shadow-[0_0_0_200vmax_rgba(0,0,0,0.45)]"
            style={{ width: boxSide, height: boxSide }}
            aria-hidden="true"
          >
            {props.showHeatmap && result && (
              <img
                src={`data:image/png;base64,${result.heatmap_png}`}
                alt=""
                className={`absolute inset-[6.25%] h-[87.5%] w-[87.5%] rounded-2xl transition-opacity duration-300 ${props.mirrored && !props.stillUrl ? "-scale-x-100" : ""}`}
                data-testid="live-heatmap"
              />
            )}
            <div className={`absolute inset-0 rounded-3xl ${liveView.phase === "locked" && running ? "animate-live-lock" : ""}`} />
            {(["top-0 left-0 border-t-4 border-l-4 rounded-tl-3xl", "top-0 right-0 border-t-4 border-r-4 rounded-tr-3xl", "bottom-0 left-0 border-b-4 border-l-4 rounded-bl-3xl", "bottom-0 right-0 border-b-4 border-r-4 rounded-br-3xl"] as const).map((corner) => (
              <span key={corner} className={`absolute h-12 w-12 transition-colors duration-300 ${corner} ${colors.corner}`} />
            ))}
            {running && !paused && (
              <span className={`animate-live-sweep absolute inset-x-[6%] h-0.5 rounded-full bg-gradient-to-r from-transparent ${colors.line} to-transparent shadow-[0_0_12px_2px_rgba(255,255,255,0.35)]`} />
            )}
          </div>

          {/* top bar: live indicator */}
          <div className="absolute inset-x-0 top-0 flex items-center justify-between gap-2 p-3">
            <span className="flex items-center gap-2 rounded-full bg-black/55 px-3 py-1.5 text-xs font-bold tracking-wider text-white backdrop-blur">
              {running && !paused ? (
                <>
                  <span className="relative flex h-2.5 w-2.5">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-400 opacity-75" />
                    <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-red-500" />
                  </span>
                  {t("live.live")}
                </>
              ) : props.stillUrl ? (
                <>
                  <Camera className="h-3.5 w-3.5" aria-hidden="true" />
                  {t("live.photo")}
                </>
              ) : (
                <>
                  <Pause className="h-3.5 w-3.5" aria-hidden="true" />
                  {t("live.paused")}
                </>
              )}
            </span>
            {result && liveView.phase === "locked" && (
              <span dir="ltr" className="latin rounded-full bg-black/55 px-3 py-1.5 text-xs font-bold text-white backdrop-blur" data-testid="live-hud-confidence">
                {probability(liveView.confidence)}
              </span>
            )}
          </div>

          {/* status chip above the controls */}
          <div className="absolute inset-x-0 bottom-[92px] flex justify-center px-4" aria-live="polite">
            <span className={`max-w-full truncate rounded-full px-4 py-2 text-sm font-bold shadow-lg backdrop-blur transition-colors ${colors.chip}`} data-testid="live-message">
              {message}
            </span>
          </div>

          {/* controls */}
          <div className="absolute inset-x-0 bottom-0 flex items-center justify-center gap-4 bg-gradient-to-t from-black/70 to-transparent px-4 pt-6 pb-4 sm:gap-6">
            {props.stillUrl ? (
              <RoundButton label={t("live.backToCamera")} onClick={props.onRetry}>
                <RotateCcw className="h-5 w-5" />
              </RoundButton>
            ) : (
              <RoundButton label={paused ? t("live.resume") : t("live.pause")} onClick={props.onTogglePause} testId="live-pause">
                {paused ? <Play className="h-5 w-5" /> : <Pause className="h-5 w-5" />}
              </RoundButton>
            )}
            <RoundButton label={t("live.heatmap")} onClick={props.onHeatmap} pressed={props.showHeatmap} testId="live-heatmap-toggle">
              <Layers className="h-5 w-5" />
            </RoundButton>
            <button
              type="button"
              onClick={props.onCapture}
              disabled={props.busyCapture || (!running && !props.stillUrl)}
              className="flex h-[68px] w-[68px] items-center justify-center rounded-full border-4 border-white bg-white/25 text-white shadow-xl backdrop-blur transition hover:bg-white/40 disabled:opacity-50"
              aria-label={t("live.capture")}
              title={t("live.capture")}
              data-testid="live-capture"
            >
              <Aperture className={`h-8 w-8 ${props.busyCapture ? "animate-spin" : ""}`} aria-hidden="true" />
            </button>
            {props.torchSupported && !props.stillUrl ? (
              <RoundButton label={t("live.torch")} onClick={props.onTorch} pressed={props.torchOn}>
                {props.torchOn ? <FlashlightOff className="h-5 w-5" /> : <Flashlight className="h-5 w-5" />}
              </RoundButton>
            ) : (
              <RoundButton label={t("live.takePhoto")} onClick={props.onPhoto}>
                <Camera className="h-5 w-5" />
              </RoundButton>
            )}
            {props.canSwitch && !props.stillUrl && (
              <RoundButton label={t("live.switchCamera")} onClick={props.onSwitch}>
                <SwitchCamera className="h-5 w-5" />
              </RoundButton>
            )}
          </div>

          {props.starting && (
            <div className="absolute inset-0 flex items-center justify-center bg-gray-950/70 text-white">
              <span className="flex items-center gap-2 text-sm font-semibold">
                <VideoOff className="h-5 w-5 animate-pulse" aria-hidden="true" />
                {t("live.starting")}
              </span>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function RoundButton({ label, onClick, children, pressed, testId }: { label: string; onClick: () => void; children: ReactNode; pressed?: boolean; testId?: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      title={label}
      aria-pressed={pressed}
      className={`flex h-12 w-12 items-center justify-center rounded-full text-white shadow-lg backdrop-blur transition ${pressed ? "bg-brand-600 ring-2 ring-white/70" : "bg-black/50 hover:bg-black/70"}`}
      data-testid={testId}
    >
      <span aria-hidden="true">{children}</span>
    </button>
  );
}
