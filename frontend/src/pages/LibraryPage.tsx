import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";

import { PageShell } from "../components/PageShell";
import { CategoryBadge, EmptyState, ErrorBanner, Skeleton } from "../components/ui";
import { useI18n } from "../i18n";
import { api } from "../lib/api";

export function LibraryPage() {
  const { t, crop: cropName } = useI18n();
  const [q, setQ] = useState("");
  const [crop, setCrop] = useState("");
  const list = useQuery({ queryKey: ["diseases", crop, q], queryFn: () => api.diseases({ crop, q }) });
  const all = useQuery({ queryKey: ["diseases", "", ""], queryFn: () => api.diseases({}), staleTime: Infinity });
  const crops = all.data?.crops ?? [];

  return (
    <PageShell title={t("library.title")} lead={t("library.lead")}>
      <div className="rounded-2xl bg-white p-4 shadow-sm">
        <label className="relative block">
          <span className="sr-only">{t("library.search")}</span>
          <Search className="pointer-events-none absolute start-3 top-1/2 h-5 w-5 -translate-y-1/2 text-gray-400" aria-hidden="true" />
          <input
            type="search"
            value={q}
            onChange={(event) => setQ(event.target.value)}
            placeholder={t("library.search")}
            className="w-full rounded-xl border border-gray-300 py-2.5 ps-10 pe-3"
            data-testid="library-search"
          />
        </label>
        <div className="mt-3 flex flex-wrap gap-2" role="group" aria-label={t("library.allCrops")}>
          {["", ...crops].map((name) => (
            <button
              key={name || "all"}
              type="button"
              onClick={() => setCrop(name)}
              aria-pressed={crop === name}
              className={`rounded-full px-3.5 py-1.5 text-sm font-semibold ${crop === name ? "bg-brand-700 text-white" : "bg-gray-100 text-gray-800 hover:bg-brand-50"}`}
            >
              {name ? cropName(name) : t("library.allCrops")}
            </button>
          ))}
        </div>
      </div>
      {list.isPending && <Skeleton className="h-64 w-full" />}
      {list.isError && <ErrorBanner error={list.error} onRetry={() => list.refetch()} />}
      {list.data && list.data.items.length === 0 && <EmptyState title={t("library.noResults")} />}
      {list.data && list.data.items.length > 0 && (
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4" data-testid="library-grid">
          {list.data.items.map((item) => (
            <li key={item.id}>
              <Link to={`/library/${encodeURIComponent(item.id)}`} className="block h-full overflow-hidden rounded-2xl bg-white shadow-sm transition hover:shadow-md">
                {item.image ? (
                  <img src={item.image} alt="" className="aspect-[4/3] w-full object-cover" loading="lazy" />
                ) : (
                  <div className="aspect-[4/3] w-full bg-brand-50" />
                )}
                <div className="p-4">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-semibold text-gray-600">{cropName(item.crop)}</span>
                    <CategoryBadge category={item.category} />
                  </div>
                  <p className="mt-1 text-lg font-bold text-gray-900">{item.disease}</p>
                  <p className="mt-1 line-clamp-2 text-sm text-gray-700">{item.description}</p>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </PageShell>
  );
}
