"use client";

import { Suspense, useState, FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { KeyRound, AlertCircle } from "lucide-react";
import { useT } from "@/components/I18nProvider";

function LoginForm() {
  const t = useT();
  const router = useRouter();
  const search = useSearchParams();
  const redirect = search.get("redirect") || "/";
  const [token, setToken] = useState("");
  const [err, setErr] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setErr(null);
    document.cookie = `llm4arxiv_admin=${encodeURIComponent(token)}; path=/; max-age=${
      60 * 60 * 24 * 30
    }; samesite=lax`;
    const probe = await fetch("/api/papers/ingest", { method: "GET" });
    if (probe.status === 401) {
      setErr(t("login.error"));
      return;
    }
    router.push(redirect);
  }

  return (
    <div className="container" style={{ maxWidth: 560 }}>
      <h1 className="page-title">
        <KeyRound /> {t("login.title")}
      </h1>
      <p className="page-subtitle">{t("login.subtitle")}</p>

      <form className="form-card" onSubmit={onSubmit}>
        <label htmlFor="token">{t("login.label")}</label>
        <input
          id="token"
          type="password"
          required
          autoFocus
          value={token}
          onChange={(e) => setToken(e.target.value)}
        />
        <button type="submit">{t("login.button")}</button>
      </form>

      {err && (
        <div className="notice error">
          <AlertCircle />
          {err}
        </div>
      )}
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="container">
          <p>…</p>
        </div>
      }
    >
      <LoginForm />
    </Suspense>
  );
}
