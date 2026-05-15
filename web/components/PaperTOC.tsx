"use client";

import { useEffect, useState } from "react";
import {
  Target,
  BookOpenText,
  MessagesSquare,
  FileText,
} from "lucide-react";
import { useT } from "./I18nProvider";
import type { I18nKey } from "@/lib/i18n";

export type CoreAspect = "problem" | "solution" | "methodology" | "experiments" | "conclusion";

export type PaperTOCProps = {
  available: {
    relevance: boolean;
    brief: boolean;
    core: boolean;
    qa: boolean;
  };
  /** Which of the 5 core aspects have content, in display order. */
  coreAspects: CoreAspect[];
};

type FlatItem = { id: string; labelKey: I18nKey; icon?: React.ReactNode; sub?: boolean };

const ASPECT_LABEL: Record<CoreAspect, I18nKey> = {
  problem: "core.problem",
  solution: "core.solution",
  methodology: "core.methodology",
  experiments: "core.experiments",
  conclusion: "core.conclusion",
};

export default function PaperTOC({ available, coreAspects }: PaperTOCProps) {
  const t = useT();

  // Build a flat list of {id, label, sub} — the nesting is purely visual
  // (sub items get a class), but scroll-spy works over the flat list.
  const items: FlatItem[] = [];
  if (available.relevance)
    items.push({ id: "relevance", labelKey: "section.relevance", icon: <Target /> });
  if (available.brief)
    items.push({ id: "brief", labelKey: "section.brief", icon: <FileText /> });
  if (available.core) {
    items.push({ id: "core", labelKey: "section.core", icon: <BookOpenText /> });
    for (const aspect of coreAspects) {
      items.push({ id: `core-${aspect}`, labelKey: ASPECT_LABEL[aspect], sub: true });
    }
  }
  if (available.qa)
    items.push({ id: "qa", labelKey: "section.qa", icon: <MessagesSquare /> });

  const [active, setActive] = useState<string>(items[0]?.id ?? "");

  useEffect(() => {
    if (items.length === 0) return;
    const anchorY = window.innerHeight * 0.3;

    function update() {
      let bestId = items[0].id;
      let bestDist = Infinity;
      for (const it of items) {
        const el = document.getElementById(it.id);
        if (!el) continue;
        const top = el.getBoundingClientRect().top;
        const dist = Math.abs(top - anchorY);
        if (top - anchorY <= 16 && dist < bestDist) {
          bestDist = dist;
          bestId = it.id;
        }
      }
      setActive(bestId);
    }

    update();
    window.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
    return () => {
      window.removeEventListener("scroll", update);
      window.removeEventListener("resize", update);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items.map((i) => i.id).join(",")]);

  return (
    <nav aria-label="Table of contents">
      <ul className="toc-list">
        {items.map((it) => (
          <li key={it.id}>
            <a
              href={`#${it.id}`}
              className={`${active === it.id ? "active" : ""} ${it.sub ? "toc-sub" : ""}`}
              onClick={(e) => {
                const el = document.getElementById(it.id);
                if (!el) return;
                e.preventDefault();
                el.scrollIntoView({ behavior: "smooth", block: "start" });
                history.replaceState(null, "", `#${it.id}`);
              }}
            >
              {it.icon}
              <span>{t(it.labelKey)}</span>
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}
