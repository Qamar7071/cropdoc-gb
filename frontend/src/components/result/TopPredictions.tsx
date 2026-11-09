import { BarChart3 } from "lucide-react";

import { useI18n } from "../../i18n";
import type { TopPrediction } from "../../lib/api";
import { probability } from "../../lib/format";

export function TopPredictions({ items }: { items: TopPrediction[] }) {
  const { t, crop } = useI18n();
  return (
    <div data-testid="top3">
      <h3 className="mb-3 flex items-center gap-2 text-base font-bold text-gray-900">
        <BarChart3 className="h-5 w-5 text-brand-700" aria-hidden="true" />
        {t("result.top3")}
      </h3>
      <ul className="space-y-3 rounded-xl border border-gray-100 bg-white p-4 shadow-sm">
        {items.map((item, index) => (
          <li key={item.class_id} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 sm:grid-cols-[minmax(8rem,12rem)_1fr_4.2rem]">
            <span className={`text-[15px] leading-snug break-words ${index === 0 ? "font-bold text-gray-900" : "text-gray-700"}`}>
              {item.disease} <span className="text-xs text-gray-500">({crop(item.crop)})</span>
            </span>
            <span className="order-3 col-span-2 h-2.5 overflow-hidden rounded-full bg-gray-200 sm:order-none sm:col-span-1" aria-hidden="true">
              <span
                className={`block h-full rounded-full ${index === 0 ? "bg-brand-700" : "bg-gray-400"}`}
                style={{ width: `${Math.max(2, item.probability * 100)}%` }}
              />
            </span>
            <span className="text-end text-[15px] font-semibold tabular-nums text-gray-800 latin">{probability(item.probability)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
