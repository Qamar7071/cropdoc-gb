/* Tiny i18n: a React context with two flat JSON dictionaries (English + Urdu) and RTL switching. */
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import en from "./en.json";
import ur from "./ur.json";

export type Lang = "en" | "ur";
type Dict = Record<string, string>;
const DICTS: Record<Lang, Dict> = { en, ur };
const STORAGE_KEY = "cropdoc.lang";

export type TFunction = (key: string, vars?: Record<string, string | number>) => string;

interface I18nValue {
  lang: Lang;
  dir: "ltr" | "rtl";
  setLang: (lang: Lang) => void;
  t: TFunction;
  /** Crop name in the current language (falls back to the English name). */
  crop: (name: string) => string;
  district: (name: string) => string;
}

const I18nContext = createContext<I18nValue | null>(null);

function readStoredLang(): Lang {
  try {
    return localStorage.getItem(STORAGE_KEY) === "ur" ? "ur" : "en";
  } catch {
    return "en";
  }
}

export function translate(lang: Lang, key: string, vars?: Record<string, string | number>): string {
  const template = DICTS[lang][key] ?? DICTS.en[key] ?? key;
  return vars ? template.replace(/\{(\w+)\}/g, (_, name: string) => String(vars[name] ?? `{${name}}`)) : template;
}

export function I18nProvider({ children, initialLang }: { children: ReactNode; initialLang?: Lang }) {
  const [lang, setLangState] = useState<Lang>(initialLang ?? readStoredLang());
  const dir = lang === "ur" ? "rtl" : "ltr";

  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = dir;
  }, [lang, dir]);

  const setLang = useCallback((next: Lang) => {
    setLangState(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* private mode: language just won't persist */
    }
  }, []);

  const value = useMemo<I18nValue>(() => {
    const t: TFunction = (key, vars) => translate(lang, key, vars);
    return {
      lang,
      dir,
      setLang,
      t,
      crop: (name) => (lang === "ur" ? (DICTS.ur[`crop.${name}`] ?? name) : name),
      district: (name) => (lang === "ur" ? (DICTS.ur[`districtName.${name}`] ?? name) : name),
    };
  }, [lang, dir, setLang]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  const value = useContext(I18nContext);
  if (!value) throw new Error("useI18n must be used inside <I18nProvider>");
  return value;
}
