/* Pure helpers for the live scanner (no React, no DOM): unit-tested in live.test.ts. */
import type { LivePredictResponse, Status } from "./api";

export interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

/**
 * The reticle (scan box) is a square centred in the on-screen video, `fraction` of its shorter side.
 * The video is shown with CSS `object-fit: cover`, so the screen shows only part of the camera image.
 * This maps the on-screen square back to pixels of the camera frame, so we send exactly what the
 * farmer sees inside the box.
 */
export function reticleSourceRect(
  view: { width: number; height: number },
  video: { width: number; height: number },
  fraction = 0.72,
): Rect {
  const scale = Math.max(view.width / video.width, view.height / video.height); // cover
  const shownWidth = view.width / scale;
  const shownHeight = view.height / scale;
  const offsetX = (video.width - shownWidth) / 2;
  const offsetY = (video.height - shownHeight) / 2;
  const side = (Math.min(view.width, view.height) * fraction) / scale;
  return {
    x: offsetX + (shownWidth - side) / 2,
    y: offsetY + (shownHeight - side) / 2,
    width: side,
    height: side,
  };
}

/** Average brightness 0-255 of RGBA pixels (sampled), to warn about dark or washed-out frames. */
export function meanBrightness(rgba: Uint8ClampedArray, step = 4): number {
  let total = 0;
  let count = 0;
  for (let i = 0; i < rgba.length; i += 4 * step) {
    total += 0.299 * rgba[i] + 0.587 * rgba[i + 1] + 0.114 * rgba[i + 2];
    count += 1;
  }
  return count ? total / count : 0;
}

export type Lighting = "ok" | "dark" | "bright";

export function lightingOf(brightness: number): Lighting {
  if (brightness < 45) return "dark";
  if (brightness > 235) return "bright";
  return "ok";
}

/**
 * What the screen should say, decided from the last few frames instead of only the newest one.
 *
 * Intuition: a single frame can be blurry or caught mid-movement, so answers would flicker.
 * We only "lock" a disease when the model was confident about the SAME class in at least
 * `needed` of the last `window` frames, and we keep showing it until another class locks or the
 * camera has seen no confident leaf for `window` frames in a row.
 */
export type LivePhase = "searching" | "unsupported" | "unsure" | "steadying" | "locked";

export interface LiveView {
  phase: LivePhase;
  /** The answer to show: the locked frame (best of the agreeing frames) or the newest frame. */
  result: LivePredictResponse | null;
  /** Mean confidence over the agreeing frames when locked; else the newest frame's confidence. */
  confidence: number;
  /** How many of the recent frames agree with the shown class (for the stability meter). */
  agreement: number;
  window: number;
  /** True only on the frame where a new class locks (to vibrate / announce once). */
  justLocked: boolean;
}

export const EMPTY_VIEW: LiveView = {
  phase: "searching",
  result: null,
  confidence: 0,
  agreement: 0,
  window: 3,
  justLocked: false,
};

export class LiveSmoother {
  private frames: LivePredictResponse[] = [];
  private locked: LivePredictResponse | null = null;
  private lockedConfidence = 0;

  constructor(
    private readonly window = 3,
    private readonly needed = 2,
  ) {}

  reset(): void {
    this.frames = [];
    this.locked = null;
    this.lockedConfidence = 0;
  }

  push(frame: LivePredictResponse): LiveView {
    this.frames = [...this.frames, frame].slice(-this.window);
    const confident = this.frames.filter((f) => f.status === "confident");
    const counts = new Map<string, LivePredictResponse[]>();
    for (const f of confident) counts.set(f.class_id, [...(counts.get(f.class_id) ?? []), f]);

    let best: LivePredictResponse[] = [];
    for (const group of counts.values()) if (group.length > best.length) best = group;

    let justLocked = false;
    if (best.length >= this.needed) {
      const classId = best[0].class_id;
      justLocked = this.locked?.class_id !== classId;
      // newest agreeing frame carries the freshest heatmap; confidence is the mean over agreeing frames
      this.locked = best[best.length - 1];
      this.lockedConfidence = best.reduce((sum, f) => sum + f.confidence, 0) / best.length;
    } else if (this.locked && !confident.some((f) => f.class_id === this.locked?.class_id)) {
      if (this.frames.length >= this.window) {
        this.locked = null; // nothing confident about the locked class in the whole window
      }
    }

    if (this.locked) {
      const agreement = this.frames.filter((f) => f.status === "confident" && f.class_id === this.locked?.class_id).length;
      return {
        phase: "locked",
        result: this.locked,
        confidence: this.lockedConfidence,
        agreement,
        window: this.window,
        justLocked,
      };
    }
    // a single confident frame is not enough yet: ask the farmer to hold steady for one more
    const phase: LivePhase =
      frame.status === "not_a_leaf_or_unsupported_crop" ? "unsupported" : frame.status === "low_confidence" ? "unsure" : "steadying";
    return {
      phase,
      result: frame,
      confidence: frame.confidence,
      agreement: best.length,
      window: this.window,
      justLocked: false,
    };
  }
}

export function statusTone(status: Status | LivePhase): "good" | "warn" | "bad" | "idle" {
  if (status === "confident" || status === "locked") return "good";
  if (status === "low_confidence" || status === "unsure" || status === "steadying") return "warn";
  if (status === "not_a_leaf_or_unsupported_crop" || status === "unsupported") return "bad";
  return "idle";
}
