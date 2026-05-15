import "./globals.css";
import type { ReactNode } from "react";
import Link from "next/link";
import { ScrollText, Home, Plus } from "lucide-react";
import { getLocale } from "@/lib/locale-server";
import { t } from "@/lib/i18n";
import { I18nProvider } from "@/components/I18nProvider";
import LangToggle from "@/components/LangToggle";

export const metadata = {
  title: "LLM4ArxivPaper",
  description: "Arxiv weekly digests + on-demand LLM analyses",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  const locale = getLocale();
  return (
    <html lang={locale === "en" ? "en" : "zh-CN"}>
      <body>
        <I18nProvider locale={locale}>
          <header className="site-header">
            <div className="site-header-inner">
              <Link href="/" className="brand">
                <span className="brand-mark" aria-hidden="true">
                  <ScrollText size={16} />
                </span>
                <span>LLM4ArxivPaper</span>
              </Link>
              <nav className="site-nav" aria-label="primary">
                <Link href="/">
                  <Home size={15} />
                  {t(locale, "nav.home")}
                </Link>
                <Link href="/submit">
                  <Plus size={15} />
                  {t(locale, "nav.submit")}
                </Link>
                <LangToggle />
              </nav>
            </div>
          </header>
          <main>{children}</main>
        </I18nProvider>
      </body>
    </html>
  );
}
