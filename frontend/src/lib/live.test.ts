import { describe, expect, it } from "vitest";

import type { LivePredictResponse, Status } from "./api";
import { lightingOf, LiveSmoother, meanBrightness, reticleSourceRect } from "./live";

function frame(class_id: string, status: Status = "confident", confidence = 0.9): LivePredictResponse {
  return {
    status,
    class_id,
    crop: "Tomato",
    disease: class_id,
    healthy: false,
    confidence,
    top3: [{ class_id, crop: "Tomato", disease: class_id, probability: confidence }],
    disease_info: { id: class_id, description: "", category: "fungal", recommendations: [], needs_review: true },
    heatmap_png: "",
    crop_hint: null,
    model_version: "test",
    inference_ms: 5,
    disclaimer: "",
  };
}

describe("reticleSourceRect", () => {
  it("maps the on-screen square to camera pixels when the view crops the sides (portrait phone)", () => {
    // 1280x720 camera shown in a 360x640 portrait box: scale = 640/720, only the middle 405 px are visible
    const rect = reticleSourceRect({ width: 360, height: 640 }, { width: 1280, height: 720 }, 0.72);
    const side = (360 * 0.72) / (640 / 720);
    expect(rect.width).toBeCloseTo(side, 6);
    expect(rect.height).toBeCloseTo(side, 6);
    expect(rect.x + rect.width / 2).toBeCloseTo(640, 6); // centred in the camera frame
    expect(rect.y + rect.height / 2).toBeCloseTo(360, 6);
  });

  it("stays inside the camera frame for a wide laptop view", () => {
    const rect = reticleSourceRect({ width: 900, height: 600 }, { width: 640, height: 480 }, 0.72);
    expect(rect.x).toBeGreaterThanOrEqual(0);
    expect(rect.y).toBeGreaterThanOrEqual(0);
    expect(rect.x + rect.width).toBeLessThanOrEqual(640);
    expect(rect.y + rect.height).toBeLessThanOrEqual(480);
  });
});

describe("lighting", () => {
  it("measures brightness and flags dark or glaring frames", () => {
    const dark = new Uint8ClampedArray(4 * 16).fill(10);
    const mid = new Uint8ClampedArray(4 * 16).fill(128);
    expect(lightingOf(meanBrightness(dark, 1))).toBe("dark");
    expect(lightingOf(meanBrightness(mid, 1))).toBe("ok");
    expect(lightingOf(250)).toBe("bright");
  });
});

describe("LiveSmoother", () => {
  it("does not lock on a single confident frame", () => {
    const smoother = new LiveSmoother(3, 2);
    const view = smoother.push(frame("A"));
    expect(view.phase).toBe("steadying");
  });

  it("locks when two of the last three frames agree, and reports it once", () => {
    const smoother = new LiveSmoother(3, 2);
    smoother.push(frame("A", "confident", 0.8));
    const locked = smoother.push(frame("A", "confident", 1.0));
    expect(locked.phase).toBe("locked");
    expect(locked.justLocked).toBe(true);
    expect(locked.confidence).toBeCloseTo(0.9, 6); // mean of the agreeing frames
    const again = smoother.push(frame("A"));
    expect(again.phase).toBe("locked");
    expect(again.justLocked).toBe(false);
    expect(again.agreement).toBe(3);
  });

  it("keeps the locked answer through one bad frame, then lets go", () => {
    const smoother = new LiveSmoother(3, 2);
    smoother.push(frame("A"));
    smoother.push(frame("A"));
    expect(smoother.push(frame("A", "low_confidence", 0.4)).phase).toBe("locked");
    expect(smoother.push(frame("X", "not_a_leaf_or_unsupported_crop", 0.3)).phase).toBe("locked"); // A still in window
    const gone = smoother.push(frame("X", "not_a_leaf_or_unsupported_crop", 0.3));
    expect(gone.phase).toBe("unsupported");
    expect(gone.result?.class_id).toBe("X");
  });

  it("switches to a new disease only when the new one has a majority", () => {
    const smoother = new LiveSmoother(3, 2);
    smoother.push(frame("A"));
    smoother.push(frame("A"));
    expect(smoother.push(frame("B")).result?.class_id).toBe("A");
    const switched = smoother.push(frame("B"));
    expect(switched.result?.class_id).toBe("B");
    expect(switched.justLocked).toBe(true);
  });

  it("never locks on uncertain frames", () => {
    const smoother = new LiveSmoother(3, 2);
    smoother.push(frame("A", "low_confidence", 0.5));
    const view = smoother.push(frame("A", "low_confidence", 0.5));
    expect(view.phase).toBe("unsure");
  });
});
