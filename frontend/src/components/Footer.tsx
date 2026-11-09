import { Mountain, Sprout } from "lucide-react";

import { useI18n } from "../i18n";
import { LeafMark } from "./Logo";

export function Footer() {
  const { t } = useI18n();
  const items = [
    { icon: <LeafMark className="h-7 w-7" />, text: t("footer.made") },
    { icon: <Mountain className="h-7 w-7 text-white" aria-hidden="true" />, text: t("footer.bridge") },
    { icon: <Sprout className="h-7 w-7 text-white" aria-hidden="true" />, text: t("footer.brand") },
  ];
  return (
    <footer className="no-print relative mt-10 overflow-hidden bg-brand-900 pb-24 text-white lg:pb-0">
      <div className="mx-auto flex max-w-[1480px] flex-col gap-4 px-6 py-6 sm:flex-row sm:items-center sm:gap-0 lg:px-12">
        {items.map((item, index) => (
          <div key={item.text} className="flex items-center gap-3 sm:flex-1">
            {index > 0 && <span className="me-6 hidden h-8 w-px bg-white/40 sm:block" aria-hidden="true" />}
            {item.icon}
            <span className="text-[15px] font-semibold">{item.text}</span>
          </div>
        ))}
      </div>
      <svg viewBox="0 0 200 120" className="pointer-events-none absolute -bottom-6 end-0 hidden h-36 w-60 opacity-90 lg:block" aria-hidden="true">
        <path d="M120 120c-10-40 10-80 60-100-5 50-25 85-60 100z" fill="#22c55e" />
        <path d="M150 120c-30-20-45-50-40-90 35 20 50 55 40 90z" fill="#16a34a" />
        <path d="M120 118c15-30 30-60 58-95" stroke="#0b3d1f" strokeWidth="2" fill="none" />
      </svg>
    </footer>
  );
}
