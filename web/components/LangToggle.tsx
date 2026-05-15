"use client";

import { useRouter } from "next/navigation";
import { Languages } from "lucide-react";
import { useLocale } from "./I18nProvider";
import { LOCALE_COOKIE } from "@/lib/i18n";

/**
 * Header language switch. Writes the locale cookie and calls router.refresh()
 * so Server Components re-render in the new language — no full reload, no
 * flash of the wrong language.
 */
export default function LangToggle() {
  const locale = useLocale();
  const router = useRouter();

  function toggle() {
    const next = locale === "zh" ? "en" : "zh";
    // 1 year, lax — same shape as the admin cookie.
    document.cookie = `${LOCALE_COOKIE}=${next}; path=/; max-age=${60 * 60 * 24 * 365}; samesite=lax`;
    router.refresh();
  }

  return (
    <button
      type="button"
      onClick={toggle}
      className="lang-toggle"
      aria-label={locale === "zh" ? "Switch to English" : "切换到中文"}
      title={locale === "zh" ? "Switch to English" : "切换到中文"}
    >
      <Languages size={14} />
      {locale === "zh" ? "EN" : "中"}
    </button>
  );
}
