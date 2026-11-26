/* "My Scoutings": mobile-first scan history with search, filters, actions menu. */
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Filter, MoreHorizontal, Search, Trash2, Eye } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router";

import { PageShell } from "../components/PageShell";
import { Button, EmptyState, ErrorBanner, Skeleton, TemporaryStorageNotice } from "../components/ui";
import { useI18n } from "../i18n";
import { api, type ScanSummary } from "../lib/api";
import { formatDate, probability } from "../lib/format";
import { DISTRICTS } from "../state/district";

const PAGE_SIZE = 12;

function StatusChip({ status }: { status: ScanSummary["status"] }) {
  const { t } = useI18n();
  const tone = status === "confident" ? "bg-brand-100 text-brand-800" : status === "low_confidence" ? "bg-amber-100 text-amber-900" : "bg-red-100 text-red-900";
  return <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${tone}`}>{t(`status.${status}`)}</span>;
}

function ScanRow({ scan }: { scan: ScanSummary }) {
  const { t, lang, crop, district } = useI18n();
  const [menu, setMenu] = useState(false);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const remove = useMutation({
    mutationFn: () => api.deleteScan(scan.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["scans"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
    },
  });
  return (
    <li className="overflow-hidden rounded-2xl bg-white shadow-sm" data-testid="scan-row">
      <div className="flex items-center justify-between bg-gray-50 px-4 py-2 text-xs font-semibold text-gray-600">
        <span>{t("history.recognition")}</span>
        <span className="latin">{formatDate(scan.created_at, lang)}</span>
      </div>
      <div className="flex items-center gap-3 p-3">
        <Link to={`/history/${scan.id}`} className="shrink-0">
          <img src={scan.thumbnail_url} alt="" className="h-20 w-20 rounded-xl object-cover sm:h-24 sm:w-24" loading="lazy" />
        </Link>
        <Link to={`/history/${scan.id}`} className="min-w-0 flex-1">
          <p className="truncate font-bold text-gray-900">{scan.disease}</p>
          <p className="text-sm text-gray-600">
            {crop(scan.crop)} · <span dir="ltr" className="latin">{probability(scan.confidence)}</span>
            {scan.district && ` · ${district(scan.district)}`}
          </p>
          <div className="mt-1">
            <StatusChip status={scan.status} />
          </div>
        </Link>
        <div className="relative">
          <button type="button" onClick={() => setMenu((open) => !open)} className="rounded-full p-2 hover:bg-gray-100" aria-label={t("history.menu")} aria-expanded={menu}>
            <MoreHorizontal className="h-5 w-5 text-brand-800" aria-hidden="true" />
          </button>
          {menu && (
            <div className="absolute end-0 z-10 mt-1 w-40 overflow-hidden rounded-xl border border-gray-200 bg-white shadow-lg" role="menu">
              <button type="button" role="menuitem" className="flex w-full items-center gap-2 px-4 py-2.5 text-start text-sm hover:bg-gray-50" onClick={() => navigate(`/history/${scan.id}`)}>
                <Eye className="h-4 w-4" aria-hidden="true" />
                {t("history.view")}
              </button>
              <button
                type="button"
                role="menuitem"
                className="flex w-full items-center gap-2 px-4 py-2.5 text-start text-sm text-red-700 hover:bg-red-50"
                onClick={() => {
                  setMenu(false);
                  if (window.confirm(t("history.confirmDelete"))) remove.mutate();
                }}
              >
                <Trash2 className="h-4 w-4" aria-hidden="true" />
                {t("history.delete")}
              </button>
            </div>
          )}
        </div>
      </div>
    </li>
  );
}

export function HistoryPage() {
  const { t, crop, district: districtName } = useI18n();
  const [q, setQ] = useState("");
  const [showFilters, setShowFilters] = useState(false);
  const [filters, setFilters] = useState({ disease: "", district: "", date_from: "", date_to: "" });
  const model = useQuery({ queryKey: ["model"], queryFn: api.model, staleTime: Infinity });
  const scans = useInfiniteQuery({
    queryKey: ["scans", q, filters],
    queryFn: ({ pageParam }) => api.scans({ q, ...filters, page: pageParam, page_size: PAGE_SIZE }),
    initialPageParam: 1,
    getNextPageParam: (last) => (last.page * last.page_size < last.total ? last.page + 1 : undefined),
  });
  const items = scans.data?.pages.flatMap((page) => page.items) ?? [];
  const active = Object.values(filters).some(Boolean) || q;

  return (
    <PageShell title={t("history.title")}>
      <div className="mx-auto max-w-2xl space-y-4">
        <TemporaryStorageNotice />
        <div className="flex gap-2">
          <label className="relative flex-1">
            <span className="sr-only">{t("history.search")}</span>
            <Search className="pointer-events-none absolute start-3 top-1/2 h-5 w-5 -translate-y-1/2 text-gray-400" aria-hidden="true" />
            <input
              type="search"
              value={q}
              onChange={(event) => setQ(event.target.value)}
              placeholder={t("history.search")}
              className="w-full rounded-xl border border-gray-300 bg-white py-2.5 ps-10 pe-3"
              data-testid="history-search"
            />
          </label>
          <Button variant="secondary" onClick={() => setShowFilters((open) => !open)} aria-expanded={showFilters}>
            <Filter className="h-4 w-4" aria-hidden="true" />
            {t("history.filter")}
          </Button>
        </div>
        {showFilters && (
          <div className="grid gap-3 rounded-2xl bg-white p-4 shadow-sm sm:grid-cols-2">
            <select value={filters.disease} onChange={(e) => setFilters({ ...filters, disease: e.target.value })} className="rounded-lg border border-gray-300 px-3 py-2" aria-label={t("history.allDiseases")}>
              <option value="">{t("history.allDiseases")}</option>
              {(model.data?.classes ?? []).map((c) => (
                <option key={c.id} value={c.id}>
                  {crop(c.crop)}: {c.disease}
                </option>
              ))}
            </select>
            <select value={filters.district} onChange={(e) => setFilters({ ...filters, district: e.target.value })} className="rounded-lg border border-gray-300 px-3 py-2" aria-label={t("history.allDistricts")}>
              <option value="">{t("history.allDistricts")}</option>
              {DISTRICTS.map((name) => (
                <option key={name} value={name}>
                  {districtName(name)}
                </option>
              ))}
            </select>
            <label className="text-sm font-semibold text-gray-700">
              {t("history.from")}
              <input type="date" value={filters.date_from} onChange={(e) => setFilters({ ...filters, date_from: e.target.value })} className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 font-normal" />
            </label>
            <label className="text-sm font-semibold text-gray-700">
              {t("history.to")}
              <input type="date" value={filters.date_to} onChange={(e) => setFilters({ ...filters, date_to: e.target.value })} className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 font-normal" />
            </label>
            {active && (
              <Button variant="ghost" onClick={() => { setFilters({ disease: "", district: "", date_from: "", date_to: "" }); setQ(""); }}>
                {t("history.clear")}
              </Button>
            )}
          </div>
        )}
        {scans.isPending && <Skeleton className="h-40 w-full" />}
        {scans.isError && <ErrorBanner error={scans.error} onRetry={() => scans.refetch()} />}
        {scans.data && items.length === 0 && (
          <EmptyState
            title={t("history.empty")}
            action={
              <Link to="/scanner" className="rounded-xl bg-brand-700 px-5 py-2.5 font-semibold text-white hover:bg-brand-800">
                {t("history.emptyCta")}
              </Link>
            }
          />
        )}
        <ul className="space-y-3">
          {items.map((scan) => (
            <ScanRow key={scan.id} scan={scan} />
          ))}
        </ul>
        {scans.hasNextPage && (
          <div className="text-center">
            <Button variant="secondary" onClick={() => scans.fetchNextPage()} disabled={scans.isFetchingNextPage}>
              {t("history.loadMore")}
            </Button>
          </div>
        )}
      </div>
    </PageShell>
  );
}
