"use client";

import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { useRouter } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type AnalysisData = Record<string, string>;

type ChatMessage = {
  role: "assistant" | "user";
  content: string;
};

type RepoChatbotProps = {
  repoUrl: string;
  analysisData?: AnalysisData;
  disabled?: boolean;
  openInNewPageOnFirstSend?: boolean;
  initialQuestion?: string;
  autoSendInitialQuestion?: boolean;
};

function buildAnalysisSnapshot(analysisData: AnalysisData): string {
  return Object.entries(analysisData)
    .map(([key, value]) => `${key}: ${value}`)
    .join("\n\n");
}

export default function RepoChatbot({
  repoUrl,
  analysisData = {},
  disabled = false,
  openInNewPageOnFirstSend = false,
  initialQuestion = "",
  autoSendInitialQuestion = false,
}: RepoChatbotProps) {
  const router = useRouter();
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content: "Ask me about this repository, the architecture, the code structure, or how things connect.",
    },
  ]);
  const initialQuestionSent = useRef(false);

  const analysisSnapshot = useMemo(() => buildAnalysisSnapshot(analysisData), [analysisData]);

  const sendPrompt = async (rawPrompt: string) => {
    const prompt = rawPrompt.trim();
    if (!prompt || loading || disabled || !repoUrl) {
      return;
    }

    const hasUserMessage = messages.some((message) => message.role === "user");
    if (openInNewPageOnFirstSend && !hasUserMessage) {
      const params = new URLSearchParams({
        repoUrl,
        q: prompt,
      });
      router.push(`/chatbot?${params.toString()}`);
      return;
    }

    setMessages((current) => [...current, { role: "user", content: prompt }]);
    setQuestion("");
    setLoading(true);
    setError(null);

    const apiUrl = process.env.NEXT_PUBLIC_ANALYSIS_API_URL || "http://localhost:8000/analysis";
    const chatUrl = apiUrl.replace(/\/analysis\/?$/, "/chat");

    try {
      const response = await fetch(chatUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          repo_url: repoUrl,
          question: prompt,
          analysis_snapshot: analysisSnapshot,
        }),
      });

      if (!response.ok) {
        let message = "Failed to get chatbot response.";
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

      const payload = (await response.json()) as { answer?: string };
      setMessages((current) => [...current, { role: "assistant", content: payload.answer || "No answer returned." }]);
    } catch (chatError) {
      setError(chatError instanceof Error ? chatError.message : "Unexpected chatbot error.");
    } finally {
      setLoading(false);
    }
  };

  const handleSend = async () => {
    await sendPrompt(question);
  };

  useEffect(() => {
    const prompt = initialQuestion.trim();
    if (!autoSendInitialQuestion || !prompt || initialQuestionSent.current || loading || disabled || !repoUrl) {
      return;
    }

    initialQuestionSent.current = true;
    void sendPrompt(prompt);
  }, [autoSendInitialQuestion, initialQuestion, loading, disabled, repoUrl]);

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      event.preventDefault();
      void handleSend();
    }
  };

  return (
    <section className="repo-chatbot" aria-label="Repository chatbot">
      <div className="repo-chatbot-header">
        <div>
          <h2 className="repo-chatbot-title">Chat with this repository</h2>
          <p className="repo-chatbot-subtitle">Ask follow-up questions about structure, endpoints, architecture, or implementation details.</p>
        </div>
      </div>

      <div className="repo-chatbot-thread" role="log" aria-live="polite">
        {messages.map((message, index) => (
          <div key={`${message.role}-${index}`} className={`repo-chatbot-bubble ${message.role}`}>
            {message.role === "assistant" ? (
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
            ) : (
              message.content
            )}
          </div>
        ))}
        {loading ? <div className="repo-chatbot-bubble assistant">Thinking...</div> : null}
      </div>

      {error ? <p className="repo-chatbot-error">{error}</p> : null}

      <div className="repo-chatbot-input-row">
        <input
          className="repo-chatbot-input"
          type="text"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask a question about this repo..."
          aria-label="Repository chatbot question"
          disabled={loading || disabled || !repoUrl}
        />
        <button
          type="button"
          className="repo-chatbot-send"
          onClick={() => void handleSend()}
          disabled={loading || disabled || !question.trim() || !repoUrl}
        >
          {loading ? "Sending..." : "Send"}
        </button>
      </div>

      {disabled ? <p className="repo-chatbot-loading-note">Chat is disabled while analysis is loading.</p> : null}
    </section>
  );
}