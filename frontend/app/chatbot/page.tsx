"use client";

import { useSearchParams } from "next/navigation";
import RepoChatbot from "../components/RepoChatbot";

export default function ChatbotPage() {
    const searchParams = useSearchParams();
    const repoUrl = searchParams.get("repoUrl") || "";
    const initialQuestion = searchParams.get("q") || "";

    return (
        <section className="chatbot-page">
            <header className="chatbot-page-header">
                <h1 className="chatbot-page-title">Repository Chat</h1>
                <p className="chatbot-page-subtitle">Ask detailed questions about architecture, endpoints, and implementation.</p>
            </header>

            <RepoChatbot
                repoUrl={repoUrl}
                analysisData={{}}
                disabled={!repoUrl}
                initialQuestion={initialQuestion}
                autoSendInitialQuestion={Boolean(initialQuestion)}
            />

            {!repoUrl ? <p className="repo-chatbot-error">Missing repository URL. Open chat from the analysis page.</p> : null}
        </section>
    );
}