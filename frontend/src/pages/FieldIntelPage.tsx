/* Field Intelligence: the research story, rendered only from results/*.json via /api/field-intelligence. */
import { useMutation, useQuery } from "@tanstack/react-query";
import { CheckCircle2, FlaskConical, Send } from "lucide-react";
import { useState, type FormEvent } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ErrorBar,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { PageShell } from "../components/PageShell";
import { Button, Card, CardTitle, ErrorBanner, IconBubble, PendingNotice, Skeleton } from "../components/ui";
import { useI18n } from "../i18n";
import { api, type FieldSection } from "../lib/api";
import { asNumber, decimal, percent } from "../lib/format";
import { useDistrict } from "../state/district";

type Json = Record<string, unknown>;
const obj = (value: unknown): Json => (value && typeof value === "object" ? (value as Json) : {});

function Tile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-brand-50 p-3">
      <dt className="text-xs text-gray-600">{label}</dt>
      <dd className="mt-0.5 text-xl font-bold text-brand-900 latin">{value}</dd>
    </div>
  );
}

/** Lab vs field accuracy / macro-F1 (also used for the leakage comparison). */
function CompareBars({ rows }: { rows: { name: string; accuracy: number | null; macro_f1: number | null }[] }) {
  const { t } = useI18n();
  const data = rows.map((r) => ({ name: r.name, [t("field.accuracy")]: r.accuracy, [t("field.macroF1")]: r.macro_f1 }));
  return (
    <div className="h-64" dir="ltr">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="name" tick={{ fontSize: 12 }} />
          <YAxis domain={[0, 1]} tickFormatter={(v: number) => `${Math.round(v * 100)}%`} />
          <Tooltip formatter={(v) => percent(Number(v))} />
          <Legend />
          <Bar isAnimationActive={false} dataKey={t("field.accuracy")} fill="#15803d" radius={[6, 6, 0, 0]} />
          <Bar isAnimationActive={false} dataKey={t("field.macroF1")} fill="#86efac" radius={[6, 6, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function GapSection({ data }: { data: Json }) {
  const { t } = useI18n();
  const lab = obj(data.lab);
  const field = obj(data.field);
  const hint = obj(data.field_crop_hint);
  const rows = [
    { name: t("field.lab"), accuracy: asNumber(lab.accuracy), macro_f1: asNumber(lab.macro_f1) },
    { name: t("field.field"), accuracy: asNumber(field.accuracy), macro_f1: asNumber(field.macro_f1) },
  ];
  if (asNumber(hint.accuracy) !== null) rows.push({ name: t("field.cropHint"), accuracy: asNumber(hint.accuracy), macro_f1: asNumber(hint.macro_f1) });
  const perClass = Array.isArray(data.per_class) ? (data.per_class as Json[]) : [];
  return (
    <div className="space-y-3">
      <CompareBars rows={rows} />
      <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Tile label={`${t("field.lab")} n`} value={String(lab.n ?? "—")} />
        <Tile label={`${t("field.field")} n`} value={String(field.n ?? "—")} />
        {data.calibration !== undefined && <Tile label={`${t("field.ece")} · ${t("field.lab")}`} value={decimal(asNumber(obj(data.calibration).lab_ece))} />}
        {data.calibration !== undefined && <Tile label={`${t("field.ece")} · ${t("field.field")}`} value={decimal(asNumber(obj(data.calibration).field_ece))} />}
        {data.safety_net !== undefined && (
          <>
            <Tile label={`${t("status.confident")} · ${t("field.field")}`} value={percent(asNumber(obj(obj(obj(data.safety_net).field).confident).share))} />
            <Tile label={`${t("field.accuracy")} · ${t("status.confident")}`} value={percent(asNumber(obj(obj(obj(data.safety_net).field).confident).accuracy))} />
          </>
        )}
      </dl>
      {perClass.length > 0 && (
        <details className="rounded-xl border border-gray-200 p-3">
          <summary className="cursor-pointer text-sm font-semibold">Per-class ({perClass.length})</summary>
          <table className="mt-2 w-full text-sm latin">
            <thead>
              <tr className="text-start text-gray-600">
                <th className="text-start">class</th>
                <th>{t("field.lab")}</th>
                <th>{t("field.field")}</th>
                <th>n</th>
              </tr>
            </thead>
            <tbody>
              {perClass.map((row) => (
                <tr key={String(row.class_id)} className="border-t border-gray-100">
                  <td className="py-1">{String(row.class_id)}</td>
                  <td className="text-center">{percent(asNumber(row.lab_recall ?? row.lab_acc))}</td>
                  <td className="text-center">{percent(asNumber(row.field_recall ?? row.field_acc))}</td>
                  <td className="text-center">{String(row.n_field ?? "")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      )}
    </div>
  );
}

function FewShotSection({ data }: { data: Json }) {
  const { t } = useI18n();
  const ks = Array.isArray(data.k) ? (data.k as number[]) : [];
  const mean = (data.accuracy_mean as number[]) ?? [];
  const std = (data.accuracy_std as number[]) ?? [];
  const f1 = (data.macro_f1_mean as number[]) ?? [];
  const points = ks.map((k, i) => ({ k, accuracy: mean[i], error: std[i] ?? 0, macro_f1: f1[i] }));
  return (
    <div className="h-64" dir="ltr">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={points} margin={{ top: 4, right: 12, bottom: 22, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="k" label={{ value: t("field.k"), position: "insideBottom", offset: -16 }} />
          <YAxis domain={[0, 1]} tickFormatter={(v: number) => `${Math.round(v * 100)}%`} />
          <Tooltip formatter={(v) => percent(Number(v))} />
          <Legend verticalAlign="top" />
          <Line isAnimationActive={false} type="monotone" dataKey="accuracy" name={t("field.accuracy")} stroke="#15803d" strokeWidth={3}>
            <ErrorBar dataKey="error" width={6} stroke="#15803d" />
          </Line>
          <Line isAnimationActive={false} type="monotone" dataKey="macro_f1" name={t("field.macroF1")} stroke="#f59e0b" strokeWidth={2} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function ReliabilityChart({ series }: { series: { label: string; bins: Json[]; colour: string }[] }) {
  const toPoints = (bins: Json[]) =>
    bins
      .filter((b) => asNumber(b.count) && asNumber(b.confidence) !== null)
      .map((b) => ({ confidence: asNumber(b.confidence), accuracy: asNumber(b.accuracy) }));
  return (
    <div className="h-56" dir="ltr">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="confidence" type="number" domain={[0, 1]} tickFormatter={(v: number) => v.toFixed(1)} />
          <YAxis domain={[0, 1]} />
          <Tooltip formatter={(v) => decimal(Number(v), 3)} />
          <Legend verticalAlign="top" />
          <Line
            isAnimationActive={false}
            data={[{ confidence: 0, accuracy: 0 }, { confidence: 1, accuracy: 1 }]}
            dataKey="accuracy"
            name="perfect calibration"
            stroke="#9ca3af"
            strokeDasharray="4 4"
            dot={false}
          />
          {series.map((s) => (
            <Line isAnimationActive={false} key={s.label} data={toPoints(s.bins)} dataKey="accuracy" name={s.label} stroke={s.colour} strokeWidth={3} dot />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function CalibrationSection({ data }: { data: Json }) {
  const { t } = useI18n();
  const sets = Object.entries(data).filter(([, v]) => v && typeof v === "object" && "ece_before" in (v as Json));
  return (
    <div className="space-y-3">
      <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Tile label="T" value={decimal(asNumber(data.temperature), 3)} />
        {sets.map(([name, v]) => (
          <Tile key={name} label={`${t("field.ece")} · ${name}`} value={`${decimal(asNumber(obj(v).ece_before))} → ${decimal(asNumber(obj(v).ece_after))}`} />
        ))}
      </dl>
      {Array.isArray(data.reliability_test) && (
        <ReliabilityChart
          series={[
            { label: t("field.lab"), bins: data.reliability_test as Json[], colour: "#15803d" },
            ...(Array.isArray(data.reliability_plantdoc)
              ? [{ label: t("field.field"), bins: data.reliability_plantdoc as Json[], colour: "#f59e0b" }]
              : []),
          ]}
        />
      )}
    </div>
  );
}

function GenericSection({ data }: { data: Json }) {
  const flat: [string, string][] = [];
  const walk = (prefix: string, value: unknown, depth: number) => {
    if (typeof value === "number") flat.push([prefix, Math.abs(value) <= 1 && !Number.isInteger(value) ? decimal(value) : String(value)]);
    else if (value && typeof value === "object" && !Array.isArray(value) && depth < 2)
      for (const [k, v] of Object.entries(value as Json)) walk(prefix ? `${prefix} · ${k}` : k, v, depth + 1);
  };
  walk("", data, 0);
  return (
    <dl className="grid grid-cols-2 gap-2 sm:grid-cols-3">
      {flat.slice(0, 12).map(([k, v]) => (
        <Tile key={k} label={k.replaceAll("_", " ")} value={v} />
      ))}
    </dl>
  );
}

function LeakageSection({ data }: { data: Json }) {
  const { t } = useI18n();
  const rows = [
    { name: t("field.naive"), accuracy: asNumber(obj(data.naive).accuracy), macro_f1: asNumber(obj(data.naive).macro_f1) },
    { name: t("field.groupAware"), accuracy: asNumber(obj(data.group_aware).accuracy), macro_f1: asNumber(obj(data.group_aware).macro_f1) },
  ];
  return (
    <div className="space-y-3">
      <CompareBars rows={rows} />
      <GenericSection data={{ exposed_fraction: data.naive_exposed_fraction, inflation_accuracy_points: data.inflation_accuracy_points }} />
    </div>
  );
}

function OodSection({ data }: { data: Json }) {
  const sets = Array.isArray(data.sets) ? (data.sets as Json[]) : [];
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-gray-600">
          <th className="py-1 text-start font-semibold">Input</th>
          <th className="font-semibold">AUROC (energy)</th>
          <th className="font-semibold">AUROC (max-softmax)</th>
          <th className="font-semibold">n</th>
        </tr>
      </thead>
      <tbody className="latin">
        {sets.map((s) => (
          <tr key={String(s.name)} className="border-t border-gray-100">
            <td className="py-1.5">{String(s.name)}</td>
            <td className="text-center font-semibold">{decimal(asNumber(s.auroc_energy))}</td>
            <td className="text-center">{decimal(asNumber(s.auroc_msp))}</td>
            <td className="text-center">{String(s.n_ood ?? "")}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function BackgroundSection({ data }: { data: Json }) {
  const { t } = useI18n();
  return (
    <dl className="grid grid-cols-2 gap-2">
      <Tile label={`${t("field.accuracy")} · background only`} value={percent(asNumber(obj(data.background_only_probe).accuracy))} />
      <Tile label={`${t("field.accuracy")} · 8-px border only`} value={percent(asNumber(obj(data.border_only_probe).accuracy))} />
      <Tile label="chance" value={percent(asNumber(data.chance_accuracy))} />
      <Tile label="majority class" value={percent(asNumber(data.majority_class_accuracy))} />
    </dl>
  );
}

function CamSection({ data }: { data: Json }) {
  const { t } = useI18n();
  return (
    <dl className="grid grid-cols-2 gap-2 sm:grid-cols-3">
      <Tile label="Grad-CAM heat outside leaf" value={percent(asNumber(data.cam_mass_outside_leaf_mean))} />
      <Tile label="background share of image" value={percent(asNumber(data.background_area_fraction_mean))} />
      <Tile label={`${t("field.accuracy")} · original`} value={percent(asNumber(data.accuracy_original))} />
      <Tile label={`${t("field.accuracy")} · leaf removed`} value={percent(asNumber(data.accuracy_leaf_removed))} />
      <Tile label={`${t("field.accuracy")} · background removed`} value={percent(asNumber(data.accuracy_background_removed))} />
      <Tile label="chance" value={percent(asNumber(data.chance_accuracy))} />
    </dl>
  );
}

function SectionBody({ id, section }: { id: string; section: FieldSection }) {
  if (section.status !== "ready" || !section.data) return <PendingNotice reason={section.pending_reason} source={section.source} />;
  const data = section.data;
  if (id === "plantdoc_gap" || id === "field_gap") return <GapSection data={data} />;
  if (id.startsWith("fewshot")) return <FewShotSection data={data} />;
  if (id === "calibration") return <CalibrationSection data={data} />;
  if (id === "leakage") return <LeakageSection data={data} />;
  if (id === "ood") return <OodSection data={data} />;
  if (id === "background") return <BackgroundSection data={data} />;
  if (id === "cam_focus") return <CamSection data={data} />;
  return <GenericSection data={data} />;
}

function ContributeForm() {
  const { t, crop } = useI18n();
  const { district } = useDistrict();
  const [file, setFile] = useState<File | null>(null);
  const [label, setLabel] = useState("");
  const [consent, setConsent] = useState(false);
  const model = useQuery({ queryKey: ["model"], queryFn: api.model, staleTime: Infinity });
  const mutation = useMutation({ mutationFn: () => api.contribute(file as File, label || "unknown", consent, district || undefined) });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (file && consent) mutation.mutate();
  };
  if (mutation.isSuccess)
    return (
      <p className="flex items-center gap-2 font-semibold text-brand-800" role="status">
        <CheckCircle2 className="h-5 w-5" aria-hidden="true" />
        {t("field.thanks")}
      </p>
    );
  return (
    <form onSubmit={submit} className="space-y-3" data-testid="contribute-form">
      <input type="file" accept="image/jpeg,image/png" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="block w-full text-sm" required />
      <label className="block text-sm font-semibold text-gray-800">
        {t("field.label")}
        <select value={label} onChange={(e) => setLabel(e.target.value)} className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 font-normal">
          <option value="">{t("field.labelUnknown")}</option>
          {(model.data?.classes ?? []).map((c) => (
            <option key={c.id} value={c.id}>
              {crop(c.crop)}: {c.disease}
            </option>
          ))}
        </select>
      </label>
      <label className="flex items-start gap-2 text-sm text-gray-800">
        <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} className="mt-0.5 h-5 w-5 accent-brand-700" required />
        {t("field.consent")}
      </label>
      {mutation.isError && <ErrorBanner error={mutation.error} />}
      <Button type="submit" disabled={!file || !consent || mutation.isPending}>
        <Send className="h-4 w-4" aria-hidden="true" />
        {t("field.send")}
      </Button>
    </form>
  );
}

const ORDER = ["plantdoc_gap", "field_gap", "leakage", "background", "calibration", "ood", "fewshot_plantdoc", "fewshot_field", "cam_focus", "sweep"];

export function FieldIntelPage() {
  const { t } = useI18n();
  const intel = useQuery({ queryKey: ["field-intel"], queryFn: api.fieldIntel });
  return (
    <PageShell title={t("field.title")} lead={t("field.lead")}>
      <Card>
        <CardTitle
          icon={
            <IconBubble tone="soft">
              <FlaskConical className="h-6 w-6" />
            </IconBubble>
          }
          title={t("field.title")}
        />
        <p className="text-gray-800">{t("field.story1")}</p>
        <p className="mt-2 text-gray-800">{t("field.story2")}</p>
      </Card>
      {intel.isPending && <Skeleton className="h-64 w-full" />}
      {intel.isError && <ErrorBanner error={intel.error} onRetry={() => intel.refetch()} />}
      {intel.data && (
        <div className="grid gap-5 lg:grid-cols-2">
          {ORDER.filter((id) => intel.data.sections[id]).map((id) => {
            const section = intel.data.sections[id];
            return (
              <Card key={id} data-testid={`section-${id}`}>
                <div className="mb-3 flex items-start justify-between gap-2">
                  <h2 className="text-lg font-bold text-gray-900">{section.title}</h2>
                  <span className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-bold ${section.status === "ready" ? "bg-brand-100 text-brand-800" : "bg-amber-100 text-amber-900"}`}>
                    {section.status === "ready" ? t("field.ready") : t("field.pending")}
                  </span>
                </div>
                <SectionBody id={id} section={section} />
                {section.status === "ready" && (
                  <p className="mt-3 text-xs text-gray-500 latin">
                    {t("field.source")}: {section.source}
                  </p>
                )}
              </Card>
            );
          })}
        </div>
      )}
      <Card>
        <CardTitle title={t("field.contributeTitle")} subtitle={t("field.contributeLead")} />
        <ContributeForm />
      </Card>
    </PageShell>
  );
}
