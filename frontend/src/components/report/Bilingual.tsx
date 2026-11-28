/* Bilingual building blocks: English and Urdu shown together (Urdu right-to-left, Nastaliq font). */
import { AlertOctagon, AlertTriangle, Camera, CheckCircle2, HelpCircle, ShieldAlert } from "lucide-react";
import type { ReactNode } from "react";

import type { Bilingual, BilingualList, RiskLevel, Status } from "../../lib/api";

/** Urdu text block: right-to-left with the Urdu font, whatever the page language is. */
export function Ur({ children, className = "", as: Tag = "p" }: { children: ReactNode; className?: string; as?: "p" | "span" | "div" | "li" }) {
  return (
    <Tag lang="ur" dir="rtl" className={`urdu text-right ${className}`}>
      {children}
    </Tag>
  );
}

/** English text block (left-to-right even inside an Urdu page). */
export function En({ children, className = "", as: Tag = "p" }: { children: ReactNode; className?: string; as?: "p" | "span" | "div" | "li" }) {
  return (
    <Tag lang="en" dir="ltr" className={`text-left ${className}`}>
      {children}
    </Tag>
  );
}

/** "Symptoms / علامات" style heading. */
export function BiHeading({ en, ur, icon, id, level = 3 }: { en: string; ur: string; icon?: ReactNode; id?: string; level?: 2 | 3 }) {
  const Tag = level === 2 ? "h2" : "h3";
  return (
    <Tag id={id} className={`flex flex-wrap items-center gap-x-2 font-bold text-gray-900 ${level === 2 ? "text-xl" : "text-base"}`}>
      {icon}
      <span lang="en" dir="ltr">{en}</span>
      <span aria-hidden="true" className="text-gray-400">/</span>
      <span lang="ur" dir="rtl" className="urdu">{ur}</span>
    </Tag>
  );
}

/** Two columns: English list | Urdu list (stacked on phones). */
export function BiList({ list, testId, bullet = "•" }: { list: BilingualList; testId?: string; bullet?: string }) {
  if (!list.en.length && !list.ur.length) return null;
  return (
    <div className="grid gap-3 md:grid-cols-2" data-testid={testId}>
      <ul lang="en" dir="ltr" className="space-y-1.5 text-left text-[15px] text-gray-800">
        {list.en.map((item) => (
          <li key={item} className="flex gap-2">
            <span aria-hidden="true" className="text-brand-700">{bullet}</span>
            <span>{item}</span>
          </li>
        ))}
      </ul>
      {list.ur.length > 0 && (
        <ul lang="ur" dir="rtl" className="urdu space-y-1 text-right text-[15px] text-gray-800">
          {list.ur.map((item) => (
            <li key={item} className="flex gap-2">
              <span aria-hidden="true" className="text-brand-700">{bullet}</span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** English paragraph + Urdu paragraph side by side. */
export function BiText({ text, className = "" }: { text: Bilingual; className?: string }) {
  if (!text.en && !text.ur) return null;
  return (
    <div className={`grid gap-3 md:grid-cols-2 ${className}`}>
      <En className="text-[15px] text-gray-800">{text.en}</En>
      {text.ur && <Ur className="text-[15px] text-gray-800">{text.ur}</Ur>}
    </div>
  );
}

const RISK = {
  high: { en: "High risk", ur: "زیادہ خطرہ", tone: "bg-red-100 text-red-900 border-red-200",
    explainEn: "Can cause heavy losses quickly. Act now and contact an expert.",
    explainUr: "تیزی سے بھاری نقصان کر سکتی ہے۔ فوراً قدم اٹھائیں اور ماہر سے رابطہ کریں۔" },
  medium: { en: "Medium risk", ur: "درمیانہ خطرہ", tone: "bg-amber-100 text-amber-950 border-amber-200",
    explainEn: "Can reduce yield or quality if ignored. Act within a few days.",
    explainUr: "نظر انداز کرنے پر پیداوار یا معیار کم ہو سکتا ہے۔ چند دنوں میں قدم اٹھائیں۔" },
  low: { en: "Low risk", ur: "کم خطرہ", tone: "bg-sky-100 text-sky-950 border-sky-200",
    explainEn: "Usually limited damage if basic care is followed.",
    explainUr: "بنیادی دیکھ بھال سے عموماً محدود نقصان ہوتا ہے۔" },
  none: { en: "No disease", ur: "کوئی بیماری نہیں", tone: "bg-brand-100 text-brand-900 border-brand-200",
    explainEn: "Keep checking your plants every week.",
    explainUr: "ہر ہفتے پودوں کا معائنہ جاری رکھیں۔" },
} as const;

export function RiskBadge({ level, reason, compact = false }: { level: RiskLevel; reason?: Bilingual; compact?: boolean }) {
  if (!level || !(level in RISK)) return null;
  const r = RISK[level as keyof typeof RISK];
  return (
    <div className={`rounded-xl border p-3 ${r.tone}`} data-testid="risk-badge" data-risk={level}>
      <p className="flex flex-wrap items-center gap-x-2 font-bold">
        <ShieldAlert className="h-4 w-4" aria-hidden="true" />
        <span lang="en">{r.en}</span>
        <span aria-hidden="true">/</span>
        <span lang="ur" dir="rtl" className="urdu">{r.ur}</span>
      </p>
      {!compact && (
        <div className="mt-1 grid gap-1 text-sm md:grid-cols-2">
          <En>{reason?.en || r.explainEn}</En>
          <Ur>{reason?.ur || r.explainUr}</Ur>
        </div>
      )}
    </div>
  );
}

type View = "healthy" | "disease" | "unsure" | "unsupported" | "retake";

export function viewOf(status: Status, healthy: boolean): View {
  if (status === "retake_photo") return "retake";
  if (status === "not_a_leaf_or_unsupported_crop") return "unsupported";
  if (status === "low_confidence") return "unsure";
  return healthy ? "healthy" : "disease";
}

const STATUS = {
  healthy: { en: "Healthy", ur: "صحت مند", icon: CheckCircle2, tone: "bg-brand-700 text-white" },
  disease: { en: "Disease detected", ur: "بیماری کی تشخیص ہوئی", icon: AlertTriangle, tone: "bg-red-700 text-white" },
  unsure: { en: "Not sure", ur: "یقین نہیں", icon: HelpCircle, tone: "bg-amber-400 text-gray-950" },
  unsupported: { en: "Not recognised", ur: "پہچانا نہیں گیا", icon: AlertOctagon, tone: "bg-gray-700 text-white" },
  retake: { en: "Please take another photo", ur: "براہ کرم دوبارہ تصویر لیں", icon: Camera, tone: "bg-sky-700 text-white" },
} as const;

export function StatusPill({ view }: { view: View }) {
  const s = STATUS[view];
  const Icon = s.icon;
  return (
    <span className={`inline-flex flex-wrap items-center gap-x-2 rounded-full px-3 py-1 text-sm font-bold ${s.tone}`} data-testid="status-pill" data-view={view}>
      <Icon className="h-4 w-4" aria-hidden="true" />
      <span lang="en">{s.en}</span>
      <span aria-hidden="true">/</span>
      <span lang="ur" dir="rtl" className="urdu">{s.ur}</span>
    </span>
  );
}

const QUALITY_ISSUES = {
  too_dark: { en: "The photo is too dark. Take it in daylight or move out of the shade.", ur: "تصویر بہت اندھیری ہے۔ دن کی روشنی میں یا سائے سے باہر تصویر لیں۔" },
  too_bright: { en: "The photo is too bright (glare). Avoid direct sun on the leaf or the lens.", ur: "تصویر بہت زیادہ روشن ہے۔ پتے یا کیمرے پر براہ راست دھوپ سے بچیں۔" },
  blurry: { en: "The photo is blurry. Hold the phone still and tap the leaf to focus.", ur: "تصویر دھندلی ہے۔ فون کو ساکن رکھیں اور فوکس کے لیے پتے پر ٹیپ کریں۔" },
} as const;

export function RetakeAdvice({ issues }: { issues: (keyof typeof QUALITY_ISSUES)[] }) {
  const items = issues.length ? issues : (["blurry"] as const);
  return (
    <div className="rounded-xl border border-sky-200 bg-sky-50 p-4 text-sky-950" role="alert" data-testid="retake-advice">
      <BiHeading en="Why we need a new photo" ur="نئی تصویر کیوں چاہیے" icon={<Camera className="h-5 w-5" aria-hidden="true" />} />
      <BiList list={{ en: items.map((i) => QUALITY_ISSUES[i].en), ur: items.map((i) => QUALITY_ISSUES[i].ur) }} />
      <BiText className="mt-2 text-sm" text={{ en: "No disease is shown, because this photo cannot be analysed reliably.", ur: "کوئی بیماری نہیں دکھائی گئی، کیونکہ اس تصویر کا قابلِ اعتماد تجزیہ ممکن نہیں۔" }} />
    </div>
  );
}

export function ReviewNote({ urdu }: { urdu?: boolean }) {
  return (
    <BiText
      className="text-xs text-gray-500"
      text={{
        en: `Guidance drafted from cited agricultural sources; awaiting expert review.${urdu ? " Urdu text awaiting native review." : ""}`,
        ur: "رہنمائی حوالہ شدہ زرعی ذرائع سے تیار کی گئی ہے؛ ماہر کے جائزے کی منتظر ہے۔",
      }}
    />
  );
}
