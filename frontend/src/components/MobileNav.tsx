/* Bottom navigation for phones and tablets (< 1024 px), with a centre live-scan button. */
import { BarChart3, BookOpen, Bot, FlaskConical, History, Home, Info, Lightbulb, Menu, ScanLine, Video, Wheat, X } from "lucide-react";
import { useState } from "react";
import { NavLink } from "react-router";

import { useI18n } from "../i18n";
import { DistrictSelect, LanguageToggle } from "./TopBar";

const itemClass = ({ isActive }: { isActive: boolean }) =>
  `flex flex-1 flex-col items-center gap-0.5 py-2 text-[11px] font-semibold ${isActive ? "text-brand-700" : "text-gray-600"}`;

export function MobileNav() {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  return (
    <>
      <nav
        aria-label={t("nav.main")}
        className="no-print fixed inset-x-0 bottom-0 z-40 border-t border-gray-200 bg-white/95 pb-[env(safe-area-inset-bottom)] backdrop-blur lg:hidden"
      >
        <div className="mx-auto flex max-w-xl items-end px-2">
          <NavLink to="/" end className={itemClass}>
            <Home className="h-5 w-5" aria-hidden="true" />
            {t("nav.home")}
          </NavLink>
          <NavLink to="/history" className={itemClass}>
            <History className="h-5 w-5" aria-hidden="true" />
            {t("nav.history")}
          </NavLink>
          <NavLink to="/live" className="flex flex-1 flex-col items-center" aria-label={t("nav.live")} data-testid="mobile-live">
            {({ isActive }) => (
              <span
                className={`-mt-6 flex h-14 w-14 items-center justify-center rounded-full border-4 border-white shadow-lg ${isActive ? "bg-brand-800" : "bg-brand-700"}`}
              >
                <Video className="h-6 w-6 text-white" aria-hidden="true" />
              </span>
            )}
          </NavLink>
          <NavLink to="/assistant" className={itemClass} data-testid="mobile-assistant">
            <Bot className="h-5 w-5" aria-hidden="true" />
            {t("nav.assistantShort")}
          </NavLink>
          <button type="button" className={itemClass({ isActive: open })} onClick={() => setOpen(true)} aria-expanded={open}>
            <Menu className="h-5 w-5" aria-hidden="true" />
            {t("nav.more")}
          </button>
        </div>
      </nav>
      {open && (
        <div className="no-print fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true" aria-label={t("nav.more")}>
          <button type="button" className="absolute inset-0 bg-black/40" aria-label={t("result.close")} onClick={() => setOpen(false)} />
          <div className="absolute inset-x-0 bottom-0 rounded-t-3xl bg-white p-5 pb-[calc(env(safe-area-inset-bottom)+20px)] shadow-2xl">
            <div className="mb-3 flex items-center justify-between">
              <span className="text-lg font-bold">{t("nav.more")}</span>
              <button type="button" onClick={() => setOpen(false)} className="rounded-full p-2 hover:bg-gray-100" aria-label={t("result.close")}>
                <X className="h-5 w-5" aria-hidden="true" />
              </button>
            </div>
            <ul className="grid gap-1" onClick={() => setOpen(false)}>
              {[
                { to: "/scanner", key: "nav.scanner", icon: ScanLine },
                { to: "/crops", key: "nav.crops", icon: Wheat },
                { to: "/tips", key: "nav.tips", icon: Lightbulb },
                { to: "/dashboard", key: "nav.dashboard", icon: BarChart3 },
                { to: "/library", key: "nav.library", icon: BookOpen },
                { to: "/field-intelligence", key: "nav.field", icon: FlaskConical },
                { to: "/about", key: "nav.about", icon: Info },
              ].map(({ to, key, icon: Icon }) => (
                <li key={to}>
                  <NavLink to={to} className="flex items-center gap-3 rounded-xl px-3 py-3 font-semibold text-gray-800 hover:bg-brand-50">
                    <Icon className="h-5 w-5 text-brand-700" aria-hidden="true" />
                    {t(key)}
                  </NavLink>
                </li>
              ))}
            </ul>
            <div className="mt-4 flex flex-wrap items-center gap-2 rounded-2xl bg-brand-900 p-3">
              <DistrictSelect compact />
              <LanguageToggle />
            </div>
          </div>
        </div>
      )}
    </>
  );
}
