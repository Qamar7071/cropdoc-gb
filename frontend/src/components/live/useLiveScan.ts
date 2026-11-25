/* The live loop: grab what is inside the scan box, ask the model, smooth the answers, repeat. */
import { useCallback, useEffect, useRef, useState } from "react";

import { api, ApiError } from "../../lib/api";
import { EMPTY_VIEW, lightingOf, LiveSmoother, meanBrightness, reticleSourceRect, type Lighting, type LiveView } from "../../lib/live";

export const RETICLE_FRACTION = 0.72;
const FRAME_SIDE = 384; // pixels sent per frame; the model looks at 224 x 224 anyway
const MIN_INTERVAL_MS = 450; // at most ~2 frames per second: plenty for a steady hand, kind to phones

export interface LiveStats {
  /** Round-trip time of the last frame (camera → server → screen), measured here. */
  roundTripMs: number | null;
  /** Time the server spent on the last frame (decode + model + heatmap). */
  serverMs: number | null;
  frames: number;
}

/** Draw the scan-box part of an image or video (shown with object-fit: cover in `view`) into a square canvas. */
export function cropReticle(
  source: CanvasImageSource,
  sourceSize: { width: number; height: number },
  view: HTMLElement,
  side: number,
): HTMLCanvasElement | null {
  if (!sourceSize.width || !sourceSize.height) return null;
  const box = view.getBoundingClientRect();
  if (!box.width || !box.height) return null;
  const rect = reticleSourceRect({ width: box.width, height: box.height }, sourceSize, RETICLE_FRACTION);
  const canvas = document.createElement("canvas");
  canvas.width = side;
  canvas.height = side;
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (!context) return null;
  context.drawImage(source, rect.x, rect.y, rect.width, rect.height, 0, 0, side, side);
  return canvas;
}

export function grabReticle(video: HTMLVideoElement, view: HTMLElement, side: number): HTMLCanvasElement | null {
  return cropReticle(video, { width: video.videoWidth, height: video.videoHeight }, view, side);
}

export function canvasToBlob(canvas: HTMLCanvasElement, quality = 0.85): Promise<Blob | null> {
  return new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", quality));
}

export function useLiveScan(options: {
  video: React.RefObject<HTMLVideoElement | null>;
  view: React.RefObject<HTMLElement | null>;
  running: boolean;
  cropHint: string;
}) {
  const { video, view, running, cropHint } = options;
  const [liveView, setLiveView] = useState<LiveView>(EMPTY_VIEW);
  const [lighting, setLighting] = useState<Lighting>("ok");
  const [error, setError] = useState<unknown>(null);
  const [stats, setStats] = useState<LiveStats>({ roundTripMs: null, serverMs: null, frames: 0 });
  const smoother = useRef(new LiveSmoother(3, 2));

  useEffect(() => {
    if (!running) return;
    const controller = new AbortController();
    let stopped = false;

    const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

    async function loop() {
      while (!stopped) {
        const started = performance.now();
        if (document.hidden || !video.current || !view.current) {
          await wait(400);
          continue;
        }
        const canvas = grabReticle(video.current, view.current, FRAME_SIDE);
        if (!canvas) {
          await wait(200);
          continue;
        }
        const pixels = canvas.getContext("2d")?.getImageData(0, 0, 64, 64).data;
        if (pixels) setLighting(lightingOf(meanBrightness(pixels, 1)));
        const blob = await canvasToBlob(canvas);
        if (!blob) {
          await wait(200);
          continue;
        }
        try {
          const frame = await api.predictLive(blob, { cropHint: cropHint || undefined, signal: controller.signal });
          if (stopped) return;
          const roundTrip = performance.now() - started;
          setLiveView(smoother.current.push(frame));
          setStats((s) => ({ roundTripMs: roundTrip, serverMs: frame.inference_ms, frames: s.frames + 1 }));
          setError(null);
        } catch (failure) {
          if (stopped || controller.signal.aborted) return;
          setError(failure);
          // back off: model missing (503) or rate limit (429) will not fix itself in half a second
          const status = failure instanceof ApiError ? failure.status : 0;
          await wait(status === 429 ? 5000 : status === 503 ? 8000 : 1500);
          continue;
        }
        await wait(Math.max(0, MIN_INTERVAL_MS - (performance.now() - started)));
      }
    }
    void loop();
    return () => {
      stopped = true;
      controller.abort();
    };
  }, [running, cropHint, video, view]);

  const reset = useCallback(() => {
    smoother.current.reset();
    setLiveView(EMPTY_VIEW);
  }, []);

  /** Show the answer for one still photo (used when the live camera is not available). */
  const showStill = useCallback((frame: Parameters<LiveSmoother["push"]>[0]) => {
    smoother.current.reset();
    setLiveView({
      phase: frame.status === "confident" ? "locked" : frame.status === "low_confidence" ? "unsure" : "unsupported",
      result: frame,
      confidence: frame.confidence,
      agreement: 1,
      window: 1,
      justLocked: frame.status === "confident",
    });
    setError(null);
  }, []);

  return { liveView, lighting, error, stats, reset, showStill, setError };
}
