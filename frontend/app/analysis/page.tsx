"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import RepoChatbot from "../components/RepoChatbot";

// ── PlantUML encoding (raw DEFLATE + custom base64 via Web Compression API) ──
const PUML_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_";

const PLANTUML_EDGE_PATTERN = /(-+>|<-+|\.+>|<\.+|<\|--|--\|>)/;
const PLANTUML_NODE_KINDS = [
  "actor",
  "component",
  "database",
  "queue",
  "class",
  "interface",
  "entity",
  "participant",
  "boundary",
  "control",
  "collections",
];

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

function toSafeAlias(raw: string): string {
  let alias = raw.replace(/[^A-Za-z0-9_]/g, "_");
  if (!alias) {
    alias = "Node";
  }
  if (/^[0-9]/.test(alias)) {
    alias = `N_${alias}`;
  }
  return alias;
}

function defaultNodeForKind(kind: string): { label: string; alias: string } {
  const defaults: Record<string, { label: string; alias: string }> = {
    actor: { label: "User", alias: "UserNode" },
    component: { label: "Component", alias: "ComponentNode" },
    database: { label: "Database", alias: "DatabaseNode" },
    queue: { label: "Queue", alias: "QueueNode" },
    class: { label: "Class", alias: "ClassNode" },
    interface: { label: "Interface", alias: "InterfaceNode" },
    entity: { label: "Entity", alias: "EntityNode" },
    participant: { label: "Participant", alias: "ParticipantNode" },
    boundary: { label: "Boundary", alias: "BoundaryNode" },
    control: { label: "Control", alias: "ControlNode" },
    collections: { label: "Collection", alias: "CollectionNode" },
  };

  return defaults[kind] ?? { label: "Node", alias: "NodeAlias" };
}

function sanitizePlantUMLSource(source: string): string {
  const withoutFences = source
    .replace(/```(?:plantuml|uml)?/gi, "")
    .replace(/```/g, "")
    .trim();

  const rawLines = withoutFences.split(/\r?\n/);
  const aliasMap = new Map<string, string>();
  const output: string[] = [];

  for (const rawLine of rawLines) {
    const line = rawLine.trim();
    if (!line) {
      output.push(rawLine);
      continue;
    }

    const lowered = line.toLowerCase();
    if (lowered === "@startuml" || lowered === "@enduml" || lowered.startsWith("skinparam ")) {
      output.push(rawLine);
      continue;
    }

    const kind = PLANTUML_NODE_KINDS.find((k) => lowered === k || lowered.startsWith(`${k} `));
    if (!kind) {
      output.push(rawLine);
      continue;
    }

    const rest = line.slice(kind.length).trim();
    if (!rest) {
      const fallback = defaultNodeForKind(kind);
      output.push(`${kind} "${fallback.label}" as ${fallback.alias}`);
      continue;
    }

    if (rest.includes("{") || rest.includes("}")) {
      output.push(rawLine);
      continue;
    }

    if (rest.includes(" as ") || rest.startsWith('"') || rest.startsWith("'")) {
      output.push(rawLine);
      continue;
    }

    if (PLANTUML_EDGE_PATTERN.test(rest) || rest.includes(":")) {
      output.push(rawLine);
      continue;
    }

    if (/^[A-Za-z_][A-Za-z0-9_]*$/.test(rest)) {
      output.push(rawLine);
      continue;
    }

    const alias = toSafeAlias(rest);
    aliasMap.set(rest, alias);
    output.push(`${kind} "${rest}" as ${alias}`);
  }

  const rewritten = output.map((line) => {
    if (!PLANTUML_EDGE_PATTERN.test(line)) {
      return line;
    }

    let next = line;
    for (const [raw, alias] of aliasMap.entries()) {
      if (!raw) continue;
      const escaped = raw.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      const regex = new RegExp(escaped, "g");
      next = next.replace(regex, alias);
    }
    return next;
  });

  let normalized = rewritten.join("\n").trim();
  if (!/@startuml/i.test(normalized)) {
    normalized = `@startuml\n${normalized}\n@enduml`;
  }
  if (!/@enduml/i.test(normalized)) {
    normalized = `${normalized}\n@enduml`;
  }

  return normalized;
}

function enforceVerticalTreeLayout(source: string, heading: string): string {
  const isSystemComponents = heading.toLowerCase().includes("system components");
  if (!isSystemComponents) {
    return source;
  }

  if (!/@startuml/i.test(source)) {
    return source;
  }

  const needsDirection = !/top to bottom direction/i.test(source) && !/left to right direction/i.test(source);
  const needsLineType = !/skinparam\s+linetype\s+ortho/i.test(source);
  const needsNodeSep = !/skinparam\s+nodesep/i.test(source);
  const needsRankSep = !/skinparam\s+ranksep/i.test(source);

  if (!needsDirection && !needsLineType && !needsNodeSep && !needsRankSep) {
    return source;
  }

  const hints: string[] = [];
  if (needsDirection) hints.push("top to bottom direction");
  if (needsLineType) hints.push("skinparam linetype ortho");
  if (needsNodeSep) hints.push("skinparam nodesep 40");
  if (needsRankSep) hints.push("skinparam ranksep 70");

  return source.replace(/@startuml\s*/i, `@startuml\n${hints.join("\n")}\n`);
}

type TopicKey =
  | "Purpose and Scope"
  | "Repository Layout"
  | "Source Layer"
  | "Tech Stack"
  | "Architecture"
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
  { key: "Architecture", label: "Architecture" },
  { key: "RPC Protocol", label: "RPC Protocol" },
];

const EMPTY_CONTENT = "No content available for this topic.";

const EMPTY_ANALYSIS_DATA: TopicMap = {
  "Purpose and Scope": EMPTY_CONTENT,
  "Repository Layout": EMPTY_CONTENT,
  "Source Layer": EMPTY_CONTENT,
  "Tech Stack": EMPTY_CONTENT,
  "Architecture": EMPTY_CONTENT,
  "RPC Protocol": EMPTY_CONTENT,
};

function toTopicMap(payload: AnalysisApiResponse): TopicMap {
  return {
    "Purpose and Scope": payload.purpose_scope || EMPTY_CONTENT,
    "Repository Layout": payload.repo_layout || EMPTY_CONTENT,
    "Source Layer": payload.source_layer || EMPTY_CONTENT,
    "Tech Stack": payload.tech_stack || EMPTY_CONTENT,
    "Architecture": payload.architecture_text || EMPTY_CONTENT,
    "RPC Protocol": payload.rpc_protocol || EMPTY_CONTENT,
  };
}

function extractPlantUMLSources(content: string): string[] {
  const results: string[] = [];

  const fencedPattern = /```(?:plantuml|uml)\s*([\s\S]*?)```/gi;
  for (const match of content.matchAll(fencedPattern)) {
    const src = match[1]?.trim();
    if (!src) continue;
    const wrapped = src.startsWith("@startuml") ? src : `@startuml\n${src}\n@enduml`;
    results.push(sanitizePlantUMLSource(wrapped));
  }

  if (results.length > 0) {
    return results;
  }

  const rawPattern = /@startuml[\s\S]*?@enduml/gi;
  for (const match of content.matchAll(rawPattern)) {
    if (match[0]?.trim()) {
      results.push(sanitizePlantUMLSource(match[0].trim()));
    }
  }

  return results;
}

function stripPlantUMLBlocks(content: string): string {
  return content
    .replace(/```(?:plantuml|uml)\s*[\s\S]*?```/gi, "")
    .replace(/@startuml[\s\S]*?@enduml/gi, "")
    .trim();
}

type ArchitectureSection = {
  id: string;
  heading: string;
  content: string;
  diagrams: string[];
  textOnly: string;
};

function splitArchitectureSections(content: string): ArchitectureSection[] {
  const sections: ArchitectureSection[] = [];
  const sectionPattern = /(^##\s+.*$[\s\S]*?)(?=^##\s+.*$|\Z)/gm;

  const matches = Array.from(content.matchAll(sectionPattern));
  if (matches.length === 0) {
    const diagrams = extractPlantUMLSources(content);
    return [{
      id: "architecture-fallback",
      heading: "Architecture",
      content,
      diagrams,
      textOnly: stripPlantUMLBlocks(content),
    }];
  }

  for (let index = 0; index < matches.length; index += 1) {
    const sectionContent = matches[index][1].trim();
    const firstLine = sectionContent.split("\n", 1)[0].trim();
    const heading = firstLine.replace(/^##\s+/, "") || `Section ${index + 1}`;
    const diagrams = extractPlantUMLSources(sectionContent).map((diagram) =>
      enforceVerticalTreeLayout(diagram, heading),
    );
    sections.push({
      id: `architecture-section-${index + 1}`,
      heading,
      content: sectionContent,
      diagrams,
      textOnly: stripPlantUMLBlocks(sectionContent),
    });
  }

  return sections;
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
  const [zoomLevel, setZoomLevel] = useState(1);
  const minZoom = 0.5;
  const maxZoom = 2.5;
  const zoomStep = 0.1;

  const clampZoom = (value: number) => Math.min(maxZoom, Math.max(minZoom, value));

  useEffect(() => {
    let active = true;
    setZoomLevel(1);

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
      <div className="analysis-diagram-toolbar" role="group" aria-label="Diagram controls">
        <button
          type="button"
          className="analysis-format-btn"
          onClick={() => setZoomLevel((current) => clampZoom(current + zoomStep))}
          aria-label="Zoom in"
        >
          +
        </button>
        <button
          type="button"
          className="analysis-format-btn"
          onClick={() => setZoomLevel((current) => clampZoom(current - zoomStep))}
          aria-label="Zoom out"
        >
          -
        </button>
        <button
          type="button"
          className="analysis-format-btn"
          onClick={() => setZoomLevel(1)}
          aria-label="Reset zoom"
        >
          Reset
        </button>
      </div>
      {error ? <p className="analysis-state error">{error}</p> : null}
      {svgUrl ? (
        <div className="analysis-diagram-scroll">
          <img
            src={svgUrl}
            alt={title}
            className="analysis-diagram-img"
            style={{ transform: `scale(${zoomLevel})`, transformOrigin: "top center" }}
            onError={() => setError("Failed to render diagram from PlantUML server. Check your network or diagram syntax.")}
          />
        </div>
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
  const diagramFormat: DiagramFormat = "svg";
  const activeContent = normalizeMarkdown(analysisData[selectedTopic] || EMPTY_CONTENT);
  const architectureSections = useMemo(
    () => (selectedTopic === "Architecture" ? splitArchitectureSections(activeContent) : []),
    [activeContent, selectedTopic],
  );

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
          let message = "Failed to fetch analysis from backend.";
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
          {loading ? (
            <div className="analysis-loader" role="status" aria-live="polite" aria-busy="true">
              <div className="analysis-spinner" aria-hidden="true" />
              <p className="analysis-loader-text">Loading repository analysis...</p>
              <p className="analysis-loader-subtext">Checking cache, cloning the repo if needed, and generating results.</p>
            </div>
          ) : null}
          {error ? <p className="analysis-state error">{error}</p> : null}

          {!loading ? (
            <div className="analysis-text">
              {selectedTopic === "Architecture" ? (
                <div className="analysis-architecture-sections">
                  {architectureSections.map((section, sectionIndex) => (
                    <section key={section.id} className="analysis-architecture-section">
                      <div className="analysis-markdown">
                        <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                          {section.textOnly}
                        </ReactMarkdown>
                      </div>

                      {section.diagrams.length > 0 ? (
                        <div className="analysis-diagram-stack">
                          {section.diagrams.map((diagram, diagramIndex) => (
                            <PlantUMLDiagram
                              key={`${section.id}-diagram-${diagramIndex}`}
                              chart={diagram}
                              format={diagramFormat}
                              title={`${section.heading} - Diagram ${diagramIndex + 1}`}
                            />
                          ))}
                        </div>
                      ) : null}
                    </section>
                  ))}
                </div>
              ) : (
                <div className="analysis-markdown">
                  <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                    {activeContent}
                  </ReactMarkdown>
                </div>
              )}
            </div>
          ) : null}
        </article>
      </div>

      <div className="analysis-chatbot-bottom">
        <RepoChatbot
          repoUrl={repoUrl}
          analysisData={analysisData}
          disabled={loading}
          openInNewPageOnFirstSend
        />
      </div>
    </section>
  );
}
