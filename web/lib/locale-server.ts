/**
 * Server-only locale resolution. Reads the `llm4arxiv_lang` cookie that
 * <LangToggle> sets on the client. Server Components call getLocale() and
 * pass the result into t(); the root layout also seeds <I18nProvider> with
 * it so Client Components stay in sync.
 */
import "server-only";
import { cookies } from "next/headers";
import { normaliseLocale, LOCALE_COOKIE, type Locale } from "./i18n";

export function getLocale(): Locale {
  return normaliseLocale(cookies().get(LOCALE_COOKIE)?.value);
}
