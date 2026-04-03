"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

// ── PlantUML encoding (raw DEFLATE + custom base64 via Web Compression API) ──
const PUML_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_";

function pumlBase64(data: Uint8Array): string {
  let out = "";
  for (let i = 0; i < data.length; i += 3) {
    const b1 = data[i];
    const b2 = i + 1 < data.length ? data[i + 1] : 0;
    const b3 = i + 2 < data.length ? data[i + 2] : 0;
    out +=
      PUML_CHARS[b1 >> 2] +
      PUML_CHARS[((b1 & 0x3) << 4) | (b2 >> 4)] +
      PUML_CHARS[((b2 & 0xf) << 2) | (b3 >> 6)] +
      PUML_CHARS[b3 & 0x3f];
  }
  return out;
}

async function encodePlantUML(source: string): Promise<string> {
  const utf8 = new TextEncoder().encode(source);
  const cs = new CompressionStream("deflate-raw");
  const writer = cs.writable.getWriter();
  const reader = cs.readable.getReader();
  writer.write(utf8);
  writer.close();
  const chunks: Uint8Array[] = [];
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value);
  }
  const total = chunks.reduce((s, c) => s + c.length, 0);
  const compressed = new Uint8Array(total);
  let offset = 0;
  for (const c of chunks) { compressed.set(c, offset); offset += c.length; }
  return pumlBase64(compressed);
}

type TopicKey =
  | "Purpose and Scope"
  | "Repository Layout"
  | "Source Layer"
  | "Tech Stack"
  | "Architecture Text"
  | "Architecture Diagram"
  | "RPC Protocol";

type TopicMap = Record<TopicKey, string>;

type AnalysisApiResponse = {
  repo_url: string;
  purpose_scope?: string;
  repo_layout?: string;
  source_layer?: string;
  tech_stack?: string;
  architecture_text?: string;
  architecture_diagram?: string;
  rpc_protocol?: string;
  source?: "database" | "generated";
};

type DiagramFormat = "svg" | "png";

const TOPICS: Array<{ key: TopicKey; label: string }> = [
  { key: "Purpose and Scope", label: "Purpose and Scope" },
  { key: "Repository Layout", label: "Repository Layout" },
  { key: "Source Layer", label: "Source Layer" },
  { key: "Tech Stack", label: "Tech Stack" },
  { key: "Architecture Text", label: "Architecture Text" },
  { key: "Architecture Diagram", label: "Architecture Diagram" },
  { key: "RPC Protocol", label: "RPC Protocol" },
];

const EMPTY_CONTENT = "No content available for this topic.";

const EMPTY_ANALYSIS_DATA: TopicMap = {
  "Purpose and Scope": EMPTY_CONTENT,
  "Repository Layout": EMPTY_CONTENT,
  "Source Layer": EMPTY_CONTENT,
  "Tech Stack": EMPTY_CONTENT,
  "Architecture Text": EMPTY_CONTENT,
  "Architecture Diagram": EMPTY_CONTENT,
  "RPC Protocol": EMPTY_CONTENT,
};

function toTopicMap(payload: AnalysisApiResponse): TopicMap {
  return {
    "Purpose and Scope": payload.purpose_scope || EMPTY_CONTENT,
    "Repository Layout": payload.repo_layout || EMPTY_CONTENT,
    "Source Layer": payload.source_layer || EMPTY_CONTENT,
    "Tech Stack": payload.tech_stack || EMPTY_CONTENT,
    "Architecture Text": payload.architecture_text || EMPTY_CONTENT,
    "Architecture Diagram": payload.architecture_diagram || EMPTY_CONTENT,
    "RPC Protocol": payload.rpc_protocol || EMPTY_CONTENT,
  };
}

function extractPlantUMLSource(content: string): string | null {
  // Fenced code block: ```plantuml or ```uml
  const fenced = content.match(/```(?:plantuml|uml)\s*([\s\S]*?)```/i);
  if (fenced?.[1]?.trim()) {
    const src = fenced[1].trim();
    return src.startsWith("@startuml") ? src : `@startuml\n${src}\n@enduml`;
  }

  // Raw @startuml...@enduml block anywhere in content
  const raw = content.match(/@startuml[\s\S]*?@enduml/i);
  if (raw?.[0]?.trim()) {
    return raw[0].trim();
  }

  return null;
}

function stripPlantUMLBlocks(content: string): string {
  return content
    .replace(/```(?:plantuml|uml)\s*[\s\S]*?```/gi, "")
    .replace(/@startuml[\s\S]*?@enduml/gi, "")
    .trim();
}



function normalizeMarkdown(content: string): string {
  // Some DB values may contain escaped newlines; normalize them for renderer.
  return content.replace(/\\n/g, "\n").trim();
}

const markdownComponents: Components = {
  h1: ({ children }) => <h1 className="report-h1">{children}</h1>,
  h2: ({ children }) => <h2 className="report-h2">{children}</h2>,
  h3: ({ children }) => <h3 className="report-h3">{children}</h3>,
  p: ({ children }) => <p className="report-p">{children}</p>,
  ul: ({ children }) => <ul className="report-ul">{children}</ul>,
  ol: ({ children }) => <ol className="report-ol">{children}</ol>,
  li: ({ children }) => <li className="report-li">{children}</li>,
  blockquote: ({ children }) => <blockquote className="report-quote">{children}</blockquote>,
  table: ({ children }) => <table className="report-table">{children}</table>,
  th: ({ children }) => <th className="report-th">{children}</th>,
  td: ({ children }) => <td className="report-td">{children}</td>,
};

function PlantUMLDiagram({ chart, format, title }: { chart: string; format: DiagramFormat; title: string }) {
  const [svgUrl, setSvgUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    encodePlantUML(chart)
      .then((encoded) => {
        if (active) {
          setError(null);
          setSvgUrl(`https://www.plantuml.com/plantuml/${format}/${encoded}`);
        }
      })
      .catch(() => {
        if (active) setError("Failed to encode PlantUML diagram.");
      });

    return () => { active = false; };
  }, [chart, format]);

  return (
    <div className="analysis-diagram-wrap">
      {error ? <p className="analysis-state error">{error}</p> : null}
      {svgUrl ? (
        <img
          src={svgUrl}
            alt={title}
          className="analysis-diagram-img"
          onError={() => setError("Failed to render diagram from PlantUML server. Check your network or diagram syntax.")}
        />
      ) : null}
    </div>
  );
}

export default function AnalysisPage() {
  const searchParams = useSearchParams();
  const repoUrl = useMemo(() => searchParams.get("repo_url") ?? "", [searchParams]);

  const [selectedTopic, setSelectedTopic] = useState<TopicKey>("Purpose and Scope");
  const [analysisData, setAnalysisData] = useState<TopicMap>(EMPTY_ANALYSIS_DATA);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [diagramFormat, setDiagramFormat] = useState<DiagramFormat>("svg");

  const activeContent = normalizeMarkdown(analysisData[selectedTopic] || EMPTY_CONTENT);
  const plantUMLSource = useMemo(() => extractPlantUMLSource(activeContent), [activeContent]);
  const cleanedContent = useMemo(() => stripPlantUMLBlocks(activeContent), [activeContent]);
  const isDiagramTopic = selectedTopic === "Architecture Diagram" || selectedTopic === "Repository Layout";

  useEffect(() => {
    if (!repoUrl) {
      setAnalysisData(EMPTY_ANALYSIS_DATA);
      setError("Please provide a repository URL from the home page.");
      return;
    }

    const fetchAnalysis = async () => {
      setLoading(true);
      setError(null);

      const apiUrl = process.env.NEXT_PUBLIC_ANALYSIS_API_URL || "http://localhost:8000/analysis";

      try {
        const response = await fetch(apiUrl, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ repo_url: repoUrl }),
        });

        if (!response.ok) {
          const message = "Failed to fetch analysis from backend.";
          throw new Error(message);
        }

        const payload = (await response.json()) as AnalysisApiResponse;
        setAnalysisData(toTopicMap(payload));
      } catch (fetchError) {
        setAnalysisData(EMPTY_ANALYSIS_DATA);
        setError(fetchError instanceof Error ? fetchError.message : "Unexpected error while fetching analysis.");
      } finally {
        setLoading(false);
      }
    };

    fetchAnalysis();
  }, [repoUrl]);

  return (
    <section className="analysis-page">
      <div className="analysis-shell">
        <aside className="analysis-sidebar" aria-label="Analysis topics">
          <h2 className="analysis-sidebar-title">Analysis Topics</h2>
          <nav className="analysis-topic-list">
            {TOPICS.map((topic) => {
              const isActive = selectedTopic === topic.key;
              return (
                <button
                  key={topic.key}
                  type="button"
                  className={`analysis-topic-btn ${isActive ? "active" : ""}`}
                  onClick={() => setSelectedTopic(topic.key)}
                >
                  {topic.label}
                </button>
              );
            })}
          </nav>
        </aside>

        <article className="analysis-content" aria-live="polite">
         
          {loading ? <p className="analysis-state">Checking database and generating analysis if needed...</p> : null}
          {error ? <p className="analysis-state error">{error}</p> : null}

          <div className={`analysis-text ${isDiagramTopic ? "diagram-mode" : ""}`}>
            {isDiagramTopic && plantUMLSource ? (
              <>
                <div className="analysis-diagram-toolbar" role="group" aria-label="Diagram format">
                  <button
                    type="button"
                    className={`analysis-format-btn ${diagramFormat === "svg" ? "active" : ""}`}
                    onClick={() => setDiagramFormat("svg")}
                  >
                    SVG
                  </button>
                  <button
                    type="button"
                    className={`analysis-format-btn ${diagramFormat === "png" ? "active" : ""}`}
                    onClick={() => setDiagramFormat("png")}
                  >
                    PNG
                  </button>
                </div>
                <PlantUMLDiagram
                  chart={plantUMLSource}
                  format={diagramFormat}
                  title={selectedTopic}
                />
              </>
            ) : null}

            {isDiagramTopic && plantUMLSource ? (
              cleanedContent ? (
                <div className="analysis-markdown diagram-notes">
                  <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                    {cleanedContent}
                  </ReactMarkdown>
                </div>
              ) : null
            ) : (
              <div className="analysis-markdown">
                <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                  {activeContent}
                </ReactMarkdown>
              </div>
            )}
          </div>
        </article>
      </div>
    </section>
  );
}
