/* Typed client for the CropDoc GB API (see docs/api.md). */

export type Status = "confident" | "low_confidence" | "not_a_leaf_or_unsupported_crop" | "retake_photo";

export interface Bilingual {
  en: string;
  ur: string;
}

export interface BilingualList {
  en: string[];
  ur: string[];
}

export type RiskLevel = "low" | "medium" | "high" | "none" | "";

/** Bilingual knowledge for one class (from the knowledge base, never measured from the photo). */
export interface DiseaseReport {
  id: string;
  crop: Bilingual;
  name: Bilingual;
  category: string;
  healthy: boolean;
  pathogen: string;
  description: Bilingual;
  risk_level: RiskLevel;
  risk_reason: Bilingual;
  symptoms_early: BilingualList;
  symptoms_advanced: BilingualList;
  spread: Bilingual;
  causes: BilingualList;
  immediate_actions: BilingualList;
  prevention: BilingualList;
  treatment_categories: BilingualList;
  call_expert_when: BilingualList;
  extension_fallback: Bilingual;
  sources: string[];
  needs_review: boolean;
  urdu_needs_review: boolean;
}

export interface QualityReport {
  checked: boolean;
  ok: boolean;
  issues: ("too_dark" | "too_bright" | "blurry")[];
  brightness?: number | null;
  sharpness?: number | null;
}

export interface Health {
  status: "ok";
  app_version: string;
  model_loaded: boolean;
  model_version: string | null;
  reason: string | null;
  num_classes: number;
  metrics: Record<string, number | string>;
  thresholds_provisional: boolean | null;
  /** True on serverless hosts (Vercel) where saved scans can disappear and are shared by all visitors. */
  temporary_storage?: boolean;
}

export interface ClassInfo {
  id: string;
  crop: string;
  disease: string;
  healthy: boolean;
}

export interface ModelInfo {
  model_loaded: boolean;
  model_version: string | null;
  classes: ClassInfo[];
  crops: string[];
  districts: string[];
  model_card: Record<string, unknown> & {
    metrics?: Record<string, number | string>;
    data?: { sizes?: Record<string, number> };
    architecture?: string;
    limitations?: string[];
  };
  calibration: Record<string, unknown>;
}

export interface TopPrediction {
  class_id: string;
  crop: string;
  disease: string;
  probability: number;
}

export interface PredictResponse {
  scan_id: string | null;
  saved: boolean;
  status: Status;
  class_id: string;
  crop: string;
  disease: string;
  healthy: boolean;
  confidence: number;
  top3: TopPrediction[];
  disease_info: {
    id: string;
    description: string;
    category: string;
    recommendations: string[];
    needs_review: boolean;
    report?: DiseaseReport | null;
  };
  gradcam_png: string;
  heatmap_png: string;
  model_view_jpeg: string;
  scores: Record<string, number>;
  thresholds: { min_confidence: number; max_energy: number | null; provisional: boolean; source: string };
  quality?: QualityReport;
  crop_hint: string | null;
  district: string | null;
  model_version: string;
  disclaimer: string;
}

export interface LivePredictResponse {
  status: Status;
  class_id: string;
  crop: string;
  disease: string;
  healthy: boolean;
  confidence: number;
  top3: TopPrediction[];
  disease_info: PredictResponse["disease_info"];
  heatmap_png: string;
  quality?: QualityReport;
  crop_hint: string | null;
  model_version: string;
  inference_ms: number;
  disclaimer: string;
}

export interface NetworkInfo {
  phone_mode: boolean;
  urls: string[];
}

export interface Feedback {
  correct: boolean;
  correct_class_id: string | null;
  created_at: string;
}

export interface ScanSummary {
  id: string;
  created_at: string;
  class_id: string;
  crop: string;
  disease: string;
  confidence: number;
  status: Status;
  district: string | null;
  thumbnail_url: string;
  feedback: Feedback | null;
}

export interface ScanDetail extends ScanSummary {
  top3: TopPrediction[];
  crop_hint: string | null;
  model_version: string;
  image_url: string;
  gradcam_url: string | null;
}

export interface ScanPage {
  items: ScanSummary[];
  total: number;
  page: number;
  page_size: number;
}

export interface CountItem {
  key: string;
  label: string;
  count: number;
}

export interface Stats {
  total_scans: number;
  healthy_scans: number;
  diseased_scans: number;
  by_disease: CountItem[];
  by_week: CountItem[];
  by_district: CountItem[];
  feedback: { total: number; correct: number; incorrect: number };
  source: string;
}

export interface DiseaseSummary {
  id: string;
  crop: string;
  disease: string;
  category: string;
  description: string;
  needs_review: boolean;
  image: string | null;
}

export interface DiseaseDetail {
  id: string;
  crop: string;
  disease: string;
  category: string;
  pathogen: string;
  description: string;
  symptoms: string[];
  spread: string;
  most_affected_part: string;
  general_management: string[];
  sources: string[];
  needs_review: boolean;
  images: string[];
  report?: DiseaseReport;
}

export interface CropSummary {
  id: string;
  name: Bilingual;
  season: Bilingual;
  summary: Bilingual;
  scanner_supported: boolean;
  diseases: Bilingual[];
}

export interface CropDisease {
  name: Bilingual;
  symptoms: Bilingual;
  prevention: BilingualList;
}

export interface CropDetail extends Omit<CropSummary, "diseases" | "scanner_supported"> {
  diseases: CropDisease[];
  seasonal_care: BilingualList;
  scanner_classes: string[];
  scanner_diseases: { id: string; name: Bilingual }[];
  sources: string[];
  needs_review: boolean;
  meta: { scanner_note?: Bilingual; status?: string };
}

export interface Tip {
  id: string;
  icon: string;
  title: Bilingual;
  body: Bilingual;
}

export interface WeatherDay {
  date: string;
  summary: Bilingual;
  temp_max: number | null;
  temp_min: number | null;
  precipitation_mm: number | null;
  precipitation_probability: number | null;
}

export interface Weather {
  available: boolean;
  reason?: string;
  place?: string | null;
  current?: { temperature: number | null; humidity: number | null; precipitation_mm: number | null; wind_kmh: number | null; summary: Bilingual };
  daily?: WeatherDay[];
  advisories?: Bilingual[];
  advisory_note?: Bilingual;
  attribution?: string;
}

export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
}

export interface AssistantReply {
  reply: string;
  language: "en" | "ur";
  mode: "ai" | "knowledge_base";
  model: string | null;
  notice: "ai_not_configured" | "ai_unavailable" | null;
  related: { kind: "disease" | "crop" | "tip"; id: string; title: Bilingual }[];
  sources: string[];
  disclaimer: string;
}

export interface AssistantStatus {
  ai_available: boolean;
  model: string | null;
  privacy: Bilingual;
}

export interface FieldSection {
  title: string;
  source: string;
  status: "ready" | "pending";
  data?: Record<string, unknown>;
  pending_reason?: string;
}

export interface FieldIntel {
  sections: Record<string, FieldSection>;
  ready: number;
  total: number;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, init);
  } catch (error) {
    if (init?.signal?.aborted) throw error; // cancelled on purpose (e.g. live scanner stopped)
    throw new ApiError(0, "network");
  }
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* not JSON */
    }
    throw new ApiError(response.status, detail);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

function query(params: Record<string, string | number | undefined | null>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

export const api = {
  health: () => request<Health>("/api/health"),
  model: () => request<ModelInfo>("/api/model"),
  predict: (file: File, options: { cropHint?: string; district?: string; save: boolean }) => {
    const form = new FormData();
    form.append("image", file);
    if (options.cropHint) form.append("crop_hint", options.cropHint);
    if (options.district) form.append("district", options.district);
    form.append("save", String(options.save));
    return request<PredictResponse>("/api/predict", { method: "POST", body: form });
  },
  predictLive: (frame: Blob, options: { cropHint?: string; signal?: AbortSignal }) => {
    const form = new FormData();
    form.append("image", frame, "frame.jpg");
    if (options.cropHint) form.append("crop_hint", options.cropHint);
    return request<LivePredictResponse>("/api/predict/live", { method: "POST", body: form, signal: options.signal });
  },
  network: () => request<NetworkInfo>("/api/network"),
  scans: (params: {
    q?: string;
    disease?: string;
    district?: string;
    date_from?: string;
    date_to?: string;
    page?: number;
    page_size?: number;
  }) => request<ScanPage>(`/api/scans${query(params)}`),
  scan: (id: string) => request<ScanDetail>(`/api/scans/${encodeURIComponent(id)}`),
  deleteScan: (id: string) => request<void>(`/api/scans/${encodeURIComponent(id)}`, { method: "DELETE" }),
  feedback: (id: string, body: { correct: boolean; correct_class_id?: string }) =>
    request<Feedback>(`/api/scans/${encodeURIComponent(id)}/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  stats: () => request<Stats>("/api/stats"),
  diseases: (params: { crop?: string; q?: string }) =>
    request<{ items: DiseaseSummary[]; crops: string[] }>(`/api/diseases${query(params)}`),
  disease: (id: string) => request<DiseaseDetail>(`/api/diseases/${encodeURIComponent(id)}`),
  fieldIntel: () => request<FieldIntel>("/api/field-intelligence"),
  crops: () => request<{ items: CropSummary[]; meta: { scanner_note?: Bilingual } }>("/api/crops"),
  crop: (id: string) => request<CropDetail>(`/api/crops/${encodeURIComponent(id)}`),
  tips: () => request<{ items: Tip[]; meta: { sources: string[] } }>("/api/tips"),
  weather: (params: { district?: string; lat?: number; lon?: number }) => request<Weather>(`/api/weather${query(params)}`),
  assistantStatus: () => request<AssistantStatus>("/api/assistant/status"),
  assistantChat: (messages: ChatTurn[], classId?: string) =>
    request<AssistantReply>("/api/assistant/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages, class_id: classId || undefined }),
    }),
  contribute: (file: File, label: string, consent: boolean, district?: string) => {
    const form = new FormData();
    form.append("image", file);
    form.append("label", label);
    form.append("consent", String(consent));
    if (district) form.append("district", district);
    return request<{ saved: boolean; id: string }>("/api/contribute", { method: "POST", body: form });
  },
};
