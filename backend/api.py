import re

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from db_utils import get_repo_analysis
from main import generate_repo_analysis


class AnalysisRequest(BaseModel):
    repo_url: str = Field(..., min_length=1)


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


@app.post("/analysis")
def analyze_repo(payload: AnalysisRequest):
    repo_url = payload.repo_url.strip()
    if not repo_url:
        raise HTTPException(status_code=400, detail="repo_url is required")

    cached = get_repo_analysis(repo_url)
    if (
        cached
        and not architecture_diagram_needs_refresh(cached.get("architecture_diagram"))
        and has_plantuml_block(cached.get("repo_layout"))
        and has_repo_structure_tree(cached.get("repo_layout"))
        and has_meaningful_text(cached.get("tech_stack"))
    ):
        return {
            **cached,
            "source": "database",
        }

    try:
        generated = generate_repo_analysis(repo_url)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to generate analysis: {exc}") from exc

    return {
        **generated,
        "source": "generated",
    }
