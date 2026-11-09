/* Original CropDoc GB mark: two stylized leaves with mid-ribs (no third-party artwork). */
import { useId } from "react";

export function LeafMark({ className = "h-11 w-11" }: { className?: string }) {
  const gradient = useId();
  return (
    <svg viewBox="0 0 48 48" className={className} aria-hidden="true">
      <defs>
        <linearGradient id={gradient} x1="0" y1="1" x2="1" y2="0">
          <stop offset="0" stopColor="#16a34a" />
          <stop offset="1" stopColor="#4ade80" />
        </linearGradient>
      </defs>
      <path d="M24 44C12 40 5 30 6 14c11 1 19 8 19 20 0 4-0.5 7-1 10z" fill={`url(#${gradient})`} />
      <path d="M25 44c1-15 8-27 19-32 2 15-5 27-19 32z" fill={`url(#${gradient})`} opacity="0.92" />
      <path d="M23.5 42C20 32 15 24 9 17" stroke="#0b3d1f" strokeWidth="1.6" fill="none" strokeLinecap="round" />
      <path d="M26 42c4-10 9-18 15-25" stroke="#0b3d1f" strokeWidth="1.6" fill="none" strokeLinecap="round" />
    </svg>
  );
}

export function Logo({ compact = false, tagline }: { compact?: boolean; tagline: string }) {
  return (
    <span className="flex items-center gap-3">
      <LeafMark className={compact ? "h-9 w-9" : "h-11 w-11"} />
      <span className="flex flex-col leading-tight">
        <span className={`font-bold tracking-tight text-white latin ${compact ? "text-xl" : "text-2xl"}`} dir="ltr">
          CropDoc <span className="text-brand-400">GB</span>
        </span>
        {!compact && <span className="text-[13px] text-white/85">{tagline}</span>}
      </span>
    </span>
  );
}
