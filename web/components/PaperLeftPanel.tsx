"use client";

import { useState } from "react";
import { ListTree, MessageSquareText } from "lucide-react";
import PaperTOC, { type PaperTOCProps, type CoreAspect } from "./PaperTOC";
import ChatPanel from "./ChatPanel";
import { useT } from "./I18nProvider";

export type PaperLeftPanelProps = {
  arxivId: string;
  available: PaperTOCProps["available"];
  coreAspects: CoreAspect[];
};

/**
 * Left rail of the paper view. Two tabs share the column:
 *   - TOC: scroll-spy navigation (default)
 *   - Chat: per-paper LLM conversation
 *
 * Both children stay mounted so the chat's session state and TOC's scroll
 * listener survive tab switches. The inactive tab is just visually hidden.
 */
export default function PaperLeftPanel({ arxivId, available, coreAspects }: PaperLeftPanelProps) {
  const t = useT();
  const [tab, setTab] = useState<"toc" | "chat">("toc");

  return (
    <div className="left-panel">
      <div className="left-panel-tabs" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={tab === "toc"}
          className={tab === "toc" ? "active" : ""}
          onClick={() => setTab("toc")}
        >
          <ListTree size={14} />
          {t("panel.toc")}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "chat"}
          className={tab === "chat" ? "active" : ""}
          onClick={() => setTab("chat")}
        >
          <MessageSquareText size={14} />
          {t("panel.chat")}
        </button>
      </div>

      <div className="left-panel-body">
        <div hidden={tab !== "toc"} className="left-panel-pane">
          <PaperTOC available={available} coreAspects={coreAspects} />
        </div>
        <div hidden={tab !== "chat"} className="left-panel-pane chat-pane">
          <ChatPanel arxivId={arxivId} active={tab === "chat"} />
        </div>
      </div>
    </div>
  );
}
