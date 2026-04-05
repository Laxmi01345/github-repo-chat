"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export default function HomePage() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [isPreparing, setIsPreparing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleAnalyze = async () => {
    const repoUrl = url.trim();
    if (!repoUrl) {
      return;
    }

    setIsPreparing(true);
    setError(null);

    const apiUrl = process.env.NEXT_PUBLIC_ANALYSIS_API_URL || "http://localhost:8000/analysis";
    const prepareUrl = apiUrl.replace(/\/analysis\/?$/, "/prepare");

    try {
      const response = await fetch(prepareUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ repo_url: repoUrl }),
      });

      if (!response.ok) {
        let message = "Failed to prepare repository.";

        try {
          const payload = (await response.json()) as { detail?: string };
          if (payload.detail) {
            message = payload.detail;
          }
        } catch {
          const body = await response.text();
          if (body.trim()) {
            message = body.trim();
          }
        }

        throw new Error(message);
      }

      router.push(`/analysis?repo_url=${encodeURIComponent(repoUrl)}`);
    } catch (prepareError) {
      setError(prepareError instanceof Error ? prepareError.message : "Unexpected error while preparing repository.");
    } finally {
      setIsPreparing(false);
    }
  };

  return (
    <section className="hero">
      <h1 className="hero-heading">
        Understand any&nbsp;
        <span className="hero-heading-accent">Repository</span>
        <br />
        in seconds
      </h1>

      <p className="hero-sub">
        Paste a GitHub URL and instantly chat with the codebase —
        ask questions, trace logic, and navigate code like never before.
      </p>

      <div className="hero-input-row">
        <div className="hero-input-wrap">
          <svg className="hero-input-icon" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M10 2a8 8 0 0 1 5.29 13.88l4.42 4.42-1.42 1.42-4.42-4.42A8 8 0 1 1 10 2Zm0 2a6 6 0 1 0 0 12A6 6 0 0 0 10 4Z" />
          </svg>
          <input
            className="hero-input"
            type="url"
            placeholder="https://github.com/owner/repo"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            aria-label="GitHub repository URL"
            disabled={isPreparing}
          />
        </div>
        <button
          className="hero-btn"
          onClick={handleAnalyze}
          disabled={!url.trim() || isPreparing}
          aria-busy={isPreparing}
        >
          {isPreparing ? (
            <span className="hero-btn-loading">
              <span className="hero-btn-spinner" aria-hidden="true" />
              Preparing repo
            </span>
          ) : (
            "Analyze"
          )}
        </button>
      </div>

      {isPreparing ? (
        <div className="hero-loader" role="status" aria-live="polite" aria-busy="true">
          <div className="analysis-spinner" aria-hidden="true" />
          <p className="hero-loader-title">Cloning repository...</p>
          <p className="hero-loader-text">This can take a moment for larger repos. The analysis screen will open when it is ready.</p>
        </div>
      ) : null}

      {error ? <p className="hero-error">{error}</p> : null}

      <ul className="hero-features">
        <li className="hero-feature-chip">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 0 0 1.946-.806 3.42 3.42 0 0 1 4.438 0 3.42 3.42 0 0 0 1.946.806 3.42 3.42 0 0 1 3.138 3.138 3.42 3.42 0 0 0 .806 1.946 3.42 3.42 0 0 1 0 4.438 3.42 3.42 0 0 0-.806 1.946 3.42 3.42 0 0 1-3.138 3.138 3.42 3.42 0 0 0-1.946.806 3.42 3.42 0 0 1-4.438 0 3.42 3.42 0 0 0-1.946-.806 3.42 3.42 0 0 1-3.138-3.138 3.42 3.42 0 0 0-.806-1.946 3.42 3.42 0 0 1 0-4.438 3.42 3.42 0 0 0 .806-1.946 3.42 3.42 0 0 1 3.138-3.138z"/></svg>
          Ask about any file
        </li>
        <li className="hero-feature-chip">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
          Instant answers
        </li>
        <li className="hero-feature-chip">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"/></svg>
          Full codebase context
        </li>
      </ul>
    </section>
  );
}