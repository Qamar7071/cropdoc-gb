import { BarChart3, BookOpen, ChevronDown, FlaskConical, Home, Info, Languages, Mountain, ScanLine } from "lucide-react";
import { NavLink } from "react-router";

import { useI18n } from "../i18n";
import { DISTRICTS, useDistrict } from "../state/district";
import { Logo } from "./Logo";

export const NAV_ITEMS = [
  { to: "/", key: "nav.home", icon: Home, end: true },
  { to: "/scanner", key: "nav.scanner", icon: ScanLine },
  { to: "/dashboard", key: "nav.dashboard", icon: BarChart3 },
  { to: "/library", key: "nav.library", icon: BookOpen },
  { to: "/field-intelligence", key: "nav.field", icon: FlaskConical },
  { to: "/about", key: "nav.about", icon: Info },
] as const;

export function DistrictSelect({ compact = false }: { compact?: boolean }) {
  const { t, district: districtName } = useI18n();
  const { district, setDistrict } = useDistrict();
  return (
    <label className="relative flex items-center">
      <span className="sr-only">{t("district.label")}</span>
      <Mountain className="pointer-events-none absolute start-3 h-4 w-4 text-white" aria-hidden="true" />
      <select
        value={district}
        onChange={(event) => setDistrict(event.target.value)}
        className={`appearance-none rounded-xl border border-brand-500/40 bg-brand-800/70 py-2 ps-9 pe-8 font-semibold text-white shadow-sm hover:bg-brand-800 focus:outline-none ${compact ? "text-sm" : "text-[15px]"}`}
        data-testid="district-select"
      >
        <option value="">{t("district.all")}</option>
        {DISTRICTS.map((name) => (
          <option key={name} value={name}>
            {districtName(name)}
          </option>
        ))}
      </select>
      <ChevronDown className="pointer-events-none absolute end-2.5 h-4 w-4 text-white" aria-hidden="true" />
    </label>
  );
}

export function LanguageToggle({ compact = false }: { compact?: boolean }) {
  const { t, lang, setLang } = useI18n();
  return (
    <button
      type="button"
      onClick={() => setLang(lang === "en" ? "ur" : "en")}
      className="flex items-center gap-1.5 rounded-xl border border-white/20 px-3 py-2 text-sm font-semibold text-white hover:bg-white/10"
      aria-label={t("lang.switchLabel")}
      data-testid="lang-toggle"
    >
      <Languages className="h-4 w-4" aria-hidden="true" />
      {!compact && <span>{t("lang.switch")}</span>}
    </button>
  );
}

export function TopBar() {
  const { t } = useI18n();
  return (
    <header className="no-print sticky top-0 z-40 border-b border-brand-500/20 bg-gradient-to-r from-brand-950 via-brand-900 to-brand-850 shadow-lg">
      <div className="mx-auto flex h-[72px] max-w-[1480px] items-center gap-4 px-4 lg:h-[88px] lg:px-8">
        <NavLink to="/" className="shrink-0 rounded-lg" aria-label={t("app.name")}>
          <span className="hidden lg:block">
            <Logo tagline={t("app.tagline")} />
          </span>
          <span className="lg:hidden">
            <Logo compact tagline={t("app.tagline")} />
          </span>
        </NavLink>
        <nav aria-label={t("nav.main")} className="mx-auto hidden min-w-0 overflow-x-auto [scrollbar-width:none] lg:block">
          <ul className="flex items-center gap-1">
            {NAV_ITEMS.map(({ to, key, icon: Icon, ...rest }) => (
              <li key={to}>
                <NavLink
                  to={to}
                  end={"end" in rest}
                  title={t(key)}
                  className={({ isActive }) =>
                    `flex shrink-0 items-center gap-2 whitespace-nowrap rounded-xl px-2.5 py-2.5 text-[14.5px] font-semibold transition-colors ${
                      isActive ? "bg-brand-700 text-white shadow-md" : "text-white/90 hover:bg-white/10"
                    }`
                  }
                >
                  <Icon className="h-[18px] w-[18px]" aria-hidden="true" />
                  {/* labels from 1400 px (never wrapped); icon-only with title + accessible name below that */}
                  <span className="sr-only min-[1400px]:not-sr-only min-[1400px]:whitespace-nowrap">{t(key)}</span>
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
        <div className="ms-auto flex items-center gap-2 lg:ms-0">
          <div className="hidden sm:block">
            <DistrictSelect />
          </div>
          <LanguageToggle compact />
        </div>
      </div>
    </header>
  );
}
