"use client";

import { createContext, useContext, type ReactNode } from "react";
import { t, type I18nKey, type Locale } from "@/lib/i18n";

const LocaleContext = createContext<Locale>("zh");

/**
 * Seeded by the root layout with the server-resolved locale (from the
 * `llm4arxiv_lang` cookie). Every Client Component below can then call
 * useT() / useLocale() without prop-drilling.
 */
export function I18nProvider({
  locale,
  children,
}: {
  locale: Locale;
  children: ReactNode;
}) {
  return <LocaleContext.Provider value={locale}>{children}</LocaleContext.Provider>;
}

export function useLocale(): Locale {
  return useContext(LocaleContext);
}

/** Returns a bound `t` for the current locale. */
export function useT(): (key: I18nKey, vars?: Record<string, string | number>) => string {
  const locale = useContext(LocaleContext);
  return (key, vars) => t(locale, key, vars);
}
