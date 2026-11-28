/* The scanner's last photo and result, kept in memory while the app is open, so that opening
   "Treatment guide" or "Full details" and pressing Back returns to the same report.
   Nothing is written to the device: a page reload starts fresh (saved scans live in My Scoutings). */
import type { PredictResponse } from "../lib/api";

export const lastScan: { file: File | null; result: PredictResponse | null; cropHint: string } = {
  file: null,
  result: null,
  cropHint: "",
};
