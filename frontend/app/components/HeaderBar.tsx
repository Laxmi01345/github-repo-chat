"use client";

import { useEffect, useState } from "react";

type Theme = "light" | "dark";

const THEME_STORAGE_KEY = "repolens-theme";

function applyTheme(theme: Theme) {
  document.documentElement.setAttribute("data-theme", theme);
}

export default function HeaderBar() {
  const [theme, setTheme] = useState<Theme>(() => {
    if (typeof window === "undefined") {
      return "light";
    }

    const storedTheme = localStorage.getItem(THEME_STORAGE_KEY);
    if (storedTheme === "light" || storedTheme === "dark") {
      return storedTheme;
    }

    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  });
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  const toggleTheme = () => {
    const nextTheme: Theme = theme === "light" ? "dark" : "light";
    setTheme(nextTheme);
    localStorage.setItem(THEME_STORAGE_KEY, nextTheme);
    applyTheme(nextTheme);
  };

  const handleShare = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

  return (
    <header className="header-bar" aria-label="Primary">
      <div className="header-brand">RepoLens</div>
      <div className="header-actions">
        <button type="button" className="icon-button" onClick={handleShare} aria-label="Share">
          <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
            <path d="M18 8a3 3 0 1 0-2.82-4H15a3 3 0 0 0 .12.82L8.91 8.1a3 3 0 0 0-1.82-.6A3.09 3.09 0 0 0 4 10.5 3.09 3.09 0 0 0 7.09 13a3 3 0 0 0 1.82-.61l6.21 3.28a3 3 0 0 0-.12.83 3 3 0 1 0 .88-2.12L9.67 11.1a3.52 3.52 0 0 0 0-1.2l6.21-3.28A3 3 0 0 0 18 8Z" />
          </svg>
          <span>{copied ? "Copied" : "Share"}</span>
        </button>

        <button
          type="button"
          className="icon-button icon-only"
          onClick={toggleTheme}
          aria-label="Switch theme"
          title="Switch theme"
        >
          {theme === "light" ? (
            <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
              <path d="M21.64 13a1 1 0 0 0-1.06-.36 8 8 0 0 1-9.22-9.22A1 1 0 0 0 10 2.36 10 10 0 1 0 21.64 14a1 1 0 0 0 0-1Z" />
            </svg>
          ) : (
            <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
              <path d="M12 18a6 6 0 1 0 0-12 6 6 0 0 0 0 12Zm0-16a1 1 0 0 1 1 1v1a1 1 0 0 1-2 0V3a1 1 0 0 1 1-1Zm0 18a1 1 0 0 1 1 1v1a1 1 0 0 1-2 0v-1a1 1 0 0 1 1-1Zm10-9a1 1 0 0 1 1 1 1 1 0 0 1-1 1h-1a1 1 0 0 1 0-2h1ZM3 11a1 1 0 0 1 1 1 1 1 0 0 1-1 1H2a1 1 0 0 1 0-2h1Zm16.95-6.54a1 1 0 0 1 1.41 1.41l-.71.71a1 1 0 1 1-1.41-1.41l.71-.71ZM4.35 19.65a1 1 0 0 1 1.41 0 1 1 0 0 1 0 1.41l-.71.71a1 1 0 1 1-1.41-1.41l.71-.71Zm16.3 2.12a1 1 0 0 1-1.41 0l-.71-.71a1 1 0 0 1 1.41-1.41l.71.71a1 1 0 0 1 0 1.41ZM5.76 5.76a1 1 0 0 1-1.41 1.41l-.71-.71a1 1 0 0 1 1.41-1.41l.71.71Z" />
            </svg>
          )}
        </button>
      </div>
    </header>
  );
}
