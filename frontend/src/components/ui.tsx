/* Small shared UI building blocks. */
import { AlertCircle, AlertTriangle, Clock, Inbox, RotateCcw } from "lucide-react";
import type { ReactNode } from "react";

import { ApiError } from "../lib/api";
import { useI18n } from "../i18n";

export function Card({ children, className = "", ...rest }: { children: ReactNode; className?: string } & React.HTMLAttributes<HTMLElement>) {
  return (
    <section className={`rounded-2xl bg-white p-5 shadow-[0_10px_30px_-12px_rgba(6,39,22,0.35)] sm:p-7 ${className}`} {...rest}>
      {children}
    </section>
  );
}

export function CardTitle({ icon, title, subtitle, action }: { icon?: ReactNode; title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <div className="mb-5 flex items-start gap-3">
      {icon}
      <div className="min-w-0 flex-1">
        <h2 className="text-xl font-bold text-gray-900 sm:text-[22px]">{title}</h2>
        {subtitle && <p className="mt-1 text-sm text-gray-600">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

export function IconBubble({ children, tone = "solid" }: { children: ReactNode; tone?: "solid" | "soft" }) {
  return (
    <span
      className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-full ${tone === "solid" ? "bg-brand-700 text-white" : "bg-brand-100 text-brand-700"}`}
      aria-hidden="true"
    >
      {children}
    </span>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-xl bg-gray-200 ${className}`} aria-hidden="true" />;
}

export function EmptyState({ title, body, action, icon }: { title: string; body?: string; action?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="flex flex-col items-center rounded-2xl border-2 border-dashed border-brand-200 bg-brand-50/60 px-6 py-10 text-center" data-testid="empty-state">
      <span className="mb-3 text-brand-700">{icon ?? <Inbox className="h-10 w-10" aria-hidden="true" />}</span>
      <p className="text-lg font-bold text-gray-900">{title}</p>
      {body && <p className="mt-1 max-w-md text-sm text-gray-600">{body}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorBanner({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { t } = useI18n();
  let message = t("errors.generic");
  if (error instanceof ApiError) {
    if (error.status === 0) message = t("errors.network");
    else if (error.status === 503) message = `${t("errors.modelMissing")}: ${error.message}`;
    else message = error.message || message;
  }
  return (
    <div role="alert" className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-red-900">
      <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
      <p className="flex-1 text-sm font-medium">{message}</p>
      {onRetry && (
        <button type="button" onClick={onRetry} className="flex items-center gap-1 text-sm font-semibold underline">
          <RotateCcw className="h-4 w-4" aria-hidden="true" />
          {t("errors.retry")}
        </button>
      )}
    </div>
  );
}

export function PendingNotice({ reason, source }: { reason?: string; source?: string }) {
  const { t } = useI18n();
  return (
    <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-amber-950" data-testid="pending">
      <p className="flex items-center gap-2 font-bold">
        <Clock className="h-4 w-4" aria-hidden="true" />
        {t("field.pending")}
      </p>
      {reason && <p className="mt-1 text-sm">{reason}</p>}
      {source && <p className="mt-1 text-xs text-amber-800 latin">{source}</p>}
    </div>
  );
}

export function Disclaimer({ text }: { text?: string }) {
  const { t } = useI18n();
  return (
    <p className="flex items-start gap-2.5 rounded-xl border border-yellow-200 bg-yellow-50 px-4 py-3 text-sm text-gray-900" role="note" data-testid="disclaimer">
      <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-500" aria-hidden="true" />
      {text ?? t("result.disclaimer")}
    </p>
  );
}

export function Button({
  children,
  variant = "primary",
  className = "",
  ...rest
}: { children: ReactNode; variant?: "primary" | "secondary" | "ghost" | "accent" } & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  const styles = {
    primary: "bg-brand-700 text-white hover:bg-brand-800 disabled:bg-gray-400",
    secondary: "border border-brand-700 text-brand-800 bg-white hover:bg-brand-50 disabled:opacity-50",
    ghost: "text-gray-700 hover:bg-gray-100 disabled:opacity-50",
    accent: "bg-amber-300 text-gray-900 hover:bg-amber-400 disabled:bg-gray-300",
  }[variant];
  return (
    <button
      type="button"
      className={`inline-flex items-center justify-center gap-2 rounded-xl px-5 py-2.5 text-[15px] font-semibold shadow-sm transition-colors disabled:cursor-not-allowed ${styles} ${className}`}
      {...rest}
    >
      {children}
    </button>
  );
}

export function CategoryBadge({ category }: { category: string }) {
  const { t } = useI18n();
  const tone: Record<string, string> = {
    healthy: "bg-brand-100 text-brand-800",
    fungal: "bg-orange-100 text-orange-900",
    bacterial: "bg-sky-100 text-sky-900",
    viral: "bg-purple-100 text-purple-900",
    oomycete: "bg-teal-100 text-teal-900",
    pest: "bg-rose-100 text-rose-900",
  };
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold ${tone[category] ?? "bg-gray-100 text-gray-800"}`}>
      {t(`category.${category}`)}
    </span>
  );
}
