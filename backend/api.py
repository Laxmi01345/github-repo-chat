import re
import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from db_utils import get_repo_analysis
from main import generate_repo_analysis
from repo_utils import prepare_repo, read_all_files
from chunk_utils import chunk_files
from embedding_utils import embed_chunks, retrieve_chunks
from vector_store import create_vector_store
from llm_utils import ask_llm


class AnalysisRequest(BaseModel):
    repo_url: str = Field(..., min_length=1)


class ChatRequest(BaseModel):
    repo_url: str = Field(..., min_length=1)
    question: str = Field(..., min_length=1)
    analysis_snapshot: str | None = None


def _sanitize_chat_answer(answer: str) -> str:
    if not isinstance(answer, str):
        return ""

    cleaned = answer

    # Remove top-level boilerplate wrapper lines in both markdown and plain-text forms.
    lines = cleaned.splitlines()
    drop_index = 0
    for idx, line in enumerate(lines):
        stripped = line.strip()
        normalized = re.sub(r"^[#>*\-\s]+", "", stripped).strip().lower()

        if not stripped:
            drop_index = idx + 1
            continue

        if normalized == "repository assistant":
            drop_index = idx + 1
            continue

        if normalized == "answering your question":
            drop_index = idx + 1
            continue

        if normalized.startswith("you asked:"):
            drop_index = idx + 1
            continue

        break

    cleaned = "\n".join(lines[drop_index:])

    # Safety cleanup for edge cases where wrapper text still appears at the very top.
    cleaned = re.sub(r"^\s*(?:#{1,6}\s*)?repository assistant\s*\n?", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^\s*(?:#{1,6}\s*)?answering your question\s*\n?", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^\s*(?:[-*]\s*)?you asked:\s*.*\n?", "", cleaned, flags=re.IGNORECASE)

    # Remove doubled blank lines introduced after cleanup.
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


app = FastAPI(title="Repo Analysis API")


REPO_STRUCTURE_HINTS = (
    "readme",
    "package.json",
    "node_modules",
    "src/",
    "src\\",
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".md",
)


def architecture_diagram_needs_refresh(diagram: str | None) -> bool:
    if not diagram:
        return True

    lowered = diagram.lower()

    # Diagram must be PlantUML; legacy Mermaid diagrams need regeneration
    if "@startuml" not in lowered:
        return True

    if any(hint in lowered for hint in REPO_STRUCTURE_HINTS):
        return True

    path_like_node_count = len(re.findall(r"[A-Za-z0-9_-]+/[A-Za-z0-9_./-]+", diagram))
    if path_like_node_count >= 2:
        return True

    edge_count = len(re.findall(r"\s[-.]*>+\s", diagram))
    if edge_count > 40:
        return True

    return False


def has_plantuml_block(text: str | None) -> bool:
    if not text:
        return False

    lowered = text.lower()
    return "@startuml" in lowered and "@enduml" in lowered


def has_meaningful_text(text: str | None) -> bool:
    if not text:
        return False

    stripped = text.strip()
    if not stripped:
        return False

    return stripped.lower() != "no content available for this topic."


def has_plantuml_diagram_in_text(text: str | None) -> bool:
    if not text:
        return False

    lowered = text.lower()
    return "```plantuml" in lowered or ("@startuml" in lowered and "@enduml" in lowered)


def has_architecture_sections(text: str | None) -> bool:
    if not text:
        return False

    lowered = text.lower()
    required_sections = (
        "## system components",
        "## communication flow",
        "## realtime and messaging layer",
        "## data and persistence",
        "## request lifecycle",
    )
    return all(section in lowered for section in required_sections)


def has_multiple_architecture_diagrams(text: str | None) -> bool:
    if not text:
        return False

    fenced_count = len(re.findall(r"```(?:plantuml|uml)\s*[\s\S]*?```", text, flags=re.IGNORECASE))
    # System Components, Communication Flow, Realtime/Messaging, Request Lifecycle = 4 diagrams needed
    # Data and Persistence has no diagram
    if fenced_count >= 4:
        return True

    raw_count = len(re.findall(r"@startuml[\s\S]*?@enduml", text, flags=re.IGNORECASE))
    return raw_count >= 4


def has_explanation_before_diagram_per_section(text: str | None) -> bool:
    if not text:
        return False

    sections = re.findall(r"(^##\s+.*$[\s\S]*?)(?=^##\s+.*$|\Z)", text, flags=re.MULTILINE)
    if not sections:
        return False

    for section in sections:
        heading_match = re.search(r"^##\s+.*$", section, flags=re.MULTILINE)
        if not heading_match:
            return False

        after_heading = section[heading_match.end():]
        diagram_match = re.search(r"```(?:plantuml|uml)\s*[\s\S]*?```|@startuml[\s\S]*?@enduml", after_heading, flags=re.IGNORECASE)

        if not diagram_match:
            continue

        explanation_before_diagram = after_heading[:diagram_match.start()]
        if len(explanation_before_diagram.strip()) < 120:
            return False

    return True


def has_repo_structure_tree(text: str | None) -> bool:
    if not text:
        return False

    lowered = text.lower()
    if "```text" in lowered and ("├──" in text or "└──" in text):
        return True

    # Fallback for ASCII-only trees
    if "```text" in lowered and ("+--" in text or "|--" in text):
        return True

    return False


def has_repo_layout_tables(text: str | None) -> bool:
    if not text:
        return False

    lowered = text.lower()
    has_directory_table = "| directory | purpose |" in lowered
    has_manifest_table = "| manifest | package name | target |" in lowered
    return has_directory_table and has_manifest_table


def has_repo_layout_sections(text: str | None) -> bool:
    if not text:
        return False

    lowered = text.lower()
    required_sections = (
        "### repository layout",
        "### repository structure tree",
    )
    return all(section in lowered for section in required_sections)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/prepare")
def prepare_repo_endpoint(payload: AnalysisRequest):
    repo_url = payload.repo_url.strip()
    print(f"Received prepare request for {repo_url}")
    if not repo_url:
        raise HTTPException(status_code=400, detail="repo_url is required")

    try:
        prepared = prepare_repo(repo_url)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to prepare repository: {exc}") from exc

    return {
        "repo_url": repo_url,
        "status": "ready",
        "source": "prepared",
        "reused": prepared["reused"],
    }


@app.post("/analysis")
def analyze_repo(payload: AnalysisRequest):
    repo_url = payload.repo_url.strip()
    print(f"Received analysis request for {repo_url}")
    if not repo_url:
        raise HTTPException(status_code=400, detail="repo_url is required")

    cached = get_repo_analysis(repo_url)
    if (
        cached
        and not architecture_diagram_needs_refresh(cached.get("architecture_diagram"))
        and has_repo_structure_tree(cached.get("repo_layout"))
        and has_repo_layout_tables(cached.get("repo_layout"))
        and has_repo_layout_sections(cached.get("repo_layout"))
        and has_plantuml_diagram_in_text(cached.get("architecture_text"))
        and has_architecture_sections(cached.get("architecture_text"))
        and has_multiple_architecture_diagrams(cached.get("architecture_text"))
        and has_explanation_before_diagram_per_section(cached.get("architecture_text"))
        and has_meaningful_text(cached.get("tech_stack"))
    ):
        return {
            **cached,
            "source": "database",
        }

    try:
        generated = generate_repo_analysis(repo_url)
        print(f"Generated analysis for {repo_url}: {generated}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to generate analysis: {exc}") from exc

    return {
        **generated,
        "source": "generated",
    }


@app.post("/chat")
def chat_about_repo(payload: ChatRequest):
    repo_url = payload.repo_url.strip()
    question = payload.question.strip()

    if not repo_url:
        raise HTTPException(status_code=400, detail="repo_url is required")

    if not question:
        raise HTTPException(status_code=400, detail="question is required")

    cached = get_repo_analysis(repo_url)
    snapshot_text = (payload.analysis_snapshot or "").strip()

    context_parts = []
    if snapshot_text:
        context_parts.append("ANALYSIS SNAPSHOT:\n" + snapshot_text)

    if cached:
        context_parts.append("CACHED ANALYSIS:\n" + json.dumps(cached, indent=2))

    try:
        prepared = prepare_repo(repo_url)
        repo = prepared["repo"]
        files_content = read_all_files(repo.working_dir)
        if files_content:
            chunks = chunk_files(files_content)
            if chunks:
                chunks = embed_chunks(chunks)
                index = create_vector_store(chunks)
                retrieved_chunks = retrieve_chunks(question, index, chunks, top_k=6)
                if retrieved_chunks:
                    context_parts.append("RETRIEVED SOURCE CHUNKS:\n" + "\n".join(retrieved_chunks))
    except Exception:
        pass

    if not context_parts:
        raise HTTPException(status_code=404, detail="No repository context available for chat.")

    prompt = (
        "Answer the user's question about this repository using the provided context. "
        "Return markdown only (headings, bullets, and code blocks when useful). "
        "Do NOT include wrapper text such as 'Repository Assistant', 'Answering Your Question', or 'You asked'. "
        "Start directly with the answer content. "
        "Prefer concrete details from the analysis snapshot and source chunks. "
        "If the context does not support an answer, say what is unknown instead of guessing."
    )

    answer = ask_llm(prompt, "\n\n".join(context_parts), section_key="chat", evidence={"question": question})
    answer = _sanitize_chat_answer(answer)

    return {
        "repo_url": repo_url,
        "question": question,
        "answer": answer,
    }
