"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export default function HomePage() {
  const router = useRouter();
  const [url, setUrl] = useState("");

  const handleAnalyze = () => {
    const repoUrl = url.trim();
    if (!repoUrl) {
      return;
    }

    router.push(`/analysis?repo_url=${encodeURIComponent(repoUrl)}`);
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
          />
        </div>
        <button
          className="hero-btn"
          onClick={handleAnalyze}
          disabled={!url.trim()}
        >
          Analyze
        </button>
      </div>

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