import { ShieldCheck } from "lucide-react";

import { useI18n } from "../i18n";

/* Original hero illustration: layered leaves with veins, dew drops and an AI scanning frame. */
function HeroArt() {
  return (
    <svg viewBox="0 0 640 300" className="h-full w-full" aria-hidden="true" preserveAspectRatio="xMidYMid slice">
      <defs>
        <radialGradient id="glow" cx="0.55" cy="0.35" r="0.6">
          <stop offset="0" stopColor="#4ade80" stopOpacity="0.35" />
          <stop offset="1" stopColor="#4ade80" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="leafA" x1="0" y1="1" x2="1" y2="0">
          <stop offset="0" stopColor="#15803d" />
          <stop offset="0.6" stopColor="#4ade80" />
          <stop offset="1" stopColor="#bef264" />
        </linearGradient>
        <linearGradient id="leafB" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#14532d" />
          <stop offset="1" stopColor="#22c55e" />
        </linearGradient>
      </defs>
      <rect width="640" height="300" fill="url(#glow)" />
      <path d="M40 300C60 220 120 170 210 160c-20 70-80 120-170 140z" fill="url(#leafB)" opacity="0.55" />
      <path d="M560 40c50 20 80 70 80 140-60-20-95-70-80-140z" fill="url(#leafB)" opacity="0.6" />
      <g transform="translate(250 30) rotate(-18 160 120)">
        <path d="M20 230C40 100 140 20 300 10c-10 150-110 230-280 220z" fill="url(#leafA)" />
        <path d="M30 222C120 150 200 80 290 20" stroke="#14532d" strokeWidth="4" fill="none" strokeLinecap="round" />
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <g key={i} stroke="#166534" strokeWidth="2" fill="none" strokeLinecap="round" opacity="0.7">
            <path d={`M${70 + i * 36} ${190 - i * 30}c-10-30-6-52 10-70`} />
            <path d={`M${70 + i * 36} ${190 - i * 30}c26 8 50 6 70-6`} />
          </g>
        ))}
        {[
          [120, 120, 7],
          [180, 90, 5],
          [215, 130, 6],
          [150, 165, 4],
          [245, 70, 4],
        ].map(([cx, cy, r]) => (
          <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r={r} fill="#ecfccb" opacity="0.75" />
        ))}
      </g>
      <g stroke="#86efac" strokeWidth="3" fill="none" strokeLinecap="round" opacity="0.9">
        <path d="M330 40h-28v28" />
        <path d="M520 40h28v28" />
        <path d="M330 250h-28v-28" />
        <path d="M520 250h28v-28" />
      </g>
      <rect x="310" y="60" width="230" height="2" fill="#bbf7d0" className="animate-scan" />
    </svg>
  );
}

export function Hero({ compact = false }: { compact?: boolean }) {
  const { t } = useI18n();
  return (
    <section className={`relative overflow-hidden ${compact ? "min-h-[200px]" : "min-h-[220px] lg:min-h-[260px]"}`}>
      <div className="pointer-events-none absolute inset-y-0 end-0 w-full opacity-50 sm:w-[70%] sm:opacity-100 lg:w-[55%] rtl:-scale-x-100">
        <HeroArt />
      </div>
      <div className="relative mx-auto max-w-[1480px] px-5 pt-8 pb-10 lg:px-12 lg:pt-12">
        <h1 className="text-4xl font-extrabold tracking-tight text-white sm:text-5xl lg:text-6xl">
          {t("hero.title1")} <span className="text-brand-400">{t("hero.title2")}</span>
        </h1>
        <p className="mt-3 max-w-2xl text-lg font-semibold text-white lg:text-xl">{t("hero.subtitle")}</p>
        <p className="mt-5 flex items-center gap-2 text-lg font-medium text-white">
          <ShieldCheck className="h-6 w-6 text-brand-400" aria-hidden="true" />
          {t("hero.tagline1")} <span className="text-brand-400">{t("hero.tagline2")}</span>
        </p>
      </div>
    </section>
  );
}
