import re
import json
from pathlib import Path

from repo_utils import get_repo, read_all_files
from chunk_utils import chunk_files
from embedding_utils import embed_chunks, retrieve_chunks
from vector_store import create_vector_store
from prompts import PROMPTS
from llm_utils import ask_llm
from db_utils import get_repo_analysis, store_repo_analysis


PLANTUML_BLOCK_PATTERN = re.compile(r"@startuml[\s\S]*?@enduml", re.IGNORECASE)
PLANTUML_NODE_PATTERN = re.compile(
    r'^(actor|component|database|queue)\s+(?:"([^"]+)"\s+as\s+([A-Za-z_][A-Za-z0-9_]*)|([A-Za-z_][A-Za-z0-9_]*)\s+as\s+"([^"]+)")\s*$',
    re.IGNORECASE,
)
PLANTUML_EDGE_PATTERN = re.compile(
    r'^([A-Za-z_][A-Za-z0-9_]*)\s*([-.]+>+|<[-.]+|<[-.]+>+|<\|--|--\|>|-->|->|\.\.>|<\.\.>?)\s*([A-Za-z_][A-Za-z0-9_]*)(?:\s*:\s*(.+))?\s*$',
    re.IGNORECASE,
)

REQUIRED_ARCHITECTURE_SECTIONS = [
    "## System Components",
    "## Communication Flow",
    "## Realtime and Messaging Layer",
    "## Data and Persistence",
    "## Request Lifecycle",
]

MIN_ARCH_SECTION_EXPLANATION_CHARS = 120

HTTP_METHOD_PATTERN = re.compile(
    r"(?:app|router)\.(get|post|put|patch|delete|options|head|all)\s*\(\s*['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)
FASTAPI_DECORATOR_PATTERN = re.compile(
    r"@(?:app|router)\.(get|post|put|patch|delete|options|head)\s*\(\s*['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)
FLASK_ROUTE_PATTERN = re.compile(
    r"@(?:app|bp|blueprint)\.route\s*\(\s*['\"]([^'\"]+)['\"](?:\s*,\s*methods\s*=\s*\[([^\]]+)\])?",
    re.IGNORECASE,
)
SOCKET_EVENT_PATTERN = re.compile(
    r"\.(?:on|emit)\s*\(\s*['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)


def _trim_snippet(text, limit=180):
    compact = " ".join(text.strip().split())
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit - 3]}..."


def _extract_protocol_signals(files_content):
    endpoints = []
    events = []
    protocols = {}

    for path, content in files_content.items():
        lower_path = path.lower()
        if not lower_path.endswith((".js", ".jsx", ".ts", ".tsx", ".py")):
            continue

        for method, route in HTTP_METHOD_PATTERN.findall(content):
            protocols["HTTP"] = True
            endpoints.append({
                "name": f"{method.upper()} {route}",
                "evidence_file": path,
                "evidence_snippet": _trim_snippet(f"{method.upper()} route {route}"),
            })

        for method, route in FASTAPI_DECORATOR_PATTERN.findall(content):
            protocols["HTTP"] = True
            endpoints.append({
                "name": f"{method.upper()} {route}",
                "evidence_file": path,
                "evidence_snippet": _trim_snippet(f"{method.upper()} decorator route {route}"),
            })

        for route, methods_blob in FLASK_ROUTE_PATTERN.findall(content):
            protocols["HTTP"] = True
            methods = ["GET"]
            if methods_blob:
                methods = [m.strip().strip("'\"").upper() for m in methods_blob.split(",") if m.strip()]
            for method in methods:
                endpoints.append({
                    "name": f"{method} {route}",
                    "evidence_file": path,
                    "evidence_snippet": _trim_snippet(f"{method} route {route}"),
                })

        for event_name in SOCKET_EVENT_PATTERN.findall(content):
            lowered_event = event_name.lower()
            if lowered_event in {"connection", "connect", "disconnect"} or ":" in event_name or " " in event_name or len(event_name) > 1:
                protocols["Socket.IO/WebSocket"] = True
                events.append({
                    "name": event_name,
                    "evidence_file": path,
                    "evidence_snippet": _trim_snippet(f"socket event {event_name}"),
                })

    dedup_endpoints = {item["name"]: item for item in endpoints}
    dedup_events = {item["name"]: item for item in events}

    return {
        "http_endpoints": list(dedup_endpoints.values())[:120],
        "events": list(dedup_events.values())[:160],
        "protocols": [
            {
                "name": name,
                "evidence_file": "static-scan",
                "evidence_snippet": f"Detected by static pattern scan: {name}",
            }
            for name in protocols.keys()
        ],
    }


def _merge_extracted_evidence(extracted_evidence, protocol_signals):
    if not isinstance(extracted_evidence, dict):
        extracted_evidence = {}

    communication = extracted_evidence.get("communication")
    if not isinstance(communication, dict):
        communication = {}

    existing_endpoints = communication.get("http_endpoints")
    if not isinstance(existing_endpoints, list):
        existing_endpoints = []

    existing_events = communication.get("events")
    if not isinstance(existing_events, list):
        existing_events = []

    existing_protocols = communication.get("protocols")
    if not isinstance(existing_protocols, list):
        existing_protocols = []

    endpoint_map = {item.get("name"): item for item in existing_endpoints if isinstance(item, dict) and item.get("name")}
    for item in protocol_signals.get("http_endpoints", []):
        endpoint_map[item.get("name")] = item

    event_map = {item.get("name"): item for item in existing_events if isinstance(item, dict) and item.get("name")}
    for item in protocol_signals.get("events", []):
        event_map[item.get("name")] = item

    protocol_map = {item.get("name"): item for item in existing_protocols if isinstance(item, dict) and item.get("name")}
    for item in protocol_signals.get("protocols", []):
        protocol_map[item.get("name")] = item

    communication["http_endpoints"] = list(endpoint_map.values())
    communication["events"] = list(event_map.values())
    communication["protocols"] = list(protocol_map.values())

    extracted_evidence["communication"] = communication
    return extracted_evidence


def _build_rpc_fallback_from_signals(protocol_signals):
    endpoints = protocol_signals.get("http_endpoints", []) if isinstance(protocol_signals, dict) else []
    events = protocol_signals.get("events", []) if isinstance(protocol_signals, dict) else []
    protocols = protocol_signals.get("protocols", []) if isinstance(protocol_signals, dict) else []

    lines = ["### Static Scan Interface Evidence", ""]

    if protocols:
        lines.extend([
            "#### Communication Technologies Detected",
            "| Technology | Evidence |",
            "| --- | --- |",
        ])
        for item in protocols[:20]:
            name = item.get("name", "Unknown")
            snippet = item.get("evidence_snippet", "Detected by static scan")
            lines.append(f"| {name} | {snippet} |")
        lines.append("")

    if endpoints:
        lines.extend([
            "#### HTTP Endpoints",
            "| Method | Path | Evidence File |",
            "| --- | --- | --- |",
        ])
        for item in endpoints[:120]:
            name = item.get("name", "")
            parts = name.split(" ", 1)
            method = parts[0] if parts else "UNKNOWN"
            path = parts[1] if len(parts) > 1 else "Unknown"
            evidence_file = item.get("evidence_file", "Unknown")
            lines.append(f"| {method} | {path} | {evidence_file} |")
        lines.append("")
    else:
        lines.extend([
            "#### HTTP Endpoints",
            "No endpoints discovered by static scan.",
            "",
        ])

    if events:
        lines.extend([
            "#### Events",
            "| Event | Technology | Evidence File |",
            "| --- | --- | --- |",
        ])
        for item in events[:160]:
            event_name = item.get("name", "Unknown")
            evidence_file = item.get("evidence_file", "Unknown")
            lines.append(f"| {event_name} | Socket.IO/WebSocket | {evidence_file} |")
        lines.append("")
    else:
        lines.extend([
            "#### Events",
            "No events discovered by static scan.",
            "",
        ])

    return "\n".join(lines).strip()


def _missing_architecture_sections(text):
    if not text:
        return REQUIRED_ARCHITECTURE_SECTIONS[:]

    lowered = text.lower()
    missing = []
    for section in REQUIRED_ARCHITECTURE_SECTIONS:
        if section.lower() not in lowered:
            missing.append(section)

    return missing


def _append_missing_architecture_sections(answer, missing_sections):
    if not missing_sections:
        return answer

    blocks = []
    for section in missing_sections:
        blocks.append(
            "\n".join(
                [
                    section,
                    "Unknown from current context.",
                    "- This section could not be grounded from the currently retrieved evidence.",
                ]
            )
        )

    if not answer:
        return "\n\n".join(blocks)

    return f"{answer.strip()}\n\n{'\n\n'.join(blocks)}"


def _extract_architecture_sections(text):
    if not isinstance(text, str) or not text.strip():
        return []

    pattern = re.compile(r"(^##\s+.+?$[\s\S]*?)(?=^##\s+.+?$|\Z)", re.MULTILINE)
    return [block.strip() for block in pattern.findall(text)]


def _extract_plantuml_blocks(text):
    if not isinstance(text, str) or not text.strip():
        return []
    fenced = re.findall(r"```plantuml\s*([\s\S]*?)```", text, flags=re.IGNORECASE)
    if fenced:
        return [f"@startuml\n{b.strip()}\n@enduml" if "@startuml" not in b.lower() else b.strip() for b in fenced]
    return re.findall(r"@startuml[\s\S]*?@enduml", text, flags=re.IGNORECASE)


def _normalize_uml_structure(uml_block):
    if not uml_block:
        return ""

    normalized = []
    for raw_line in uml_block.splitlines():
        line = raw_line.strip().lower()
        if not line:
            continue
        if line.startswith("@") or line.startswith("skinparam") or line.startswith("title"):
            continue
        # Compare structures rather than labels to detect duplicate diagrams.
        line = re.sub(r"\s*:\s*.*$", "", line)
        line = re.sub(r'"[^"]+"', '"x"', line)
        normalized.append(line)

    return "\n".join(normalized)


def _architecture_text_quality_issues(answer):
    issues = []
    if not isinstance(answer, str) or not answer.strip():
        return ["empty output"]

    missing = _missing_architecture_sections(answer)
    if missing:
        issues.append(f"missing sections: {', '.join(missing)}")

    sections = _extract_architecture_sections(answer)
    sections_requiring_diagrams = [
        "system components",
        "communication flow",
        "realtime and messaging layer",
        "request lifecycle",
    ]
    sections_no_diagram = ["data and persistence"]

    for section in sections:
        heading_match = re.search(r"^##\s+(.+)$", section, flags=re.MULTILINE)
        heading = heading_match.group(1).strip() if heading_match else "Unknown section"
        heading_lower = heading.lower()

        if "unknown from current context" in section.lower():
            continue

        # Check for required diagrams (all except Data and Persistence)
        if any(req in heading_lower for req in sections_requiring_diagrams):
            diagram_match = re.search(
                r"```(?:plantuml|uml)\s*[\s\S]*?```|@startuml[\s\S]*?@enduml",
                section,
                flags=re.IGNORECASE,
            )
            if not diagram_match:
                issues.append(f"{heading}: missing diagram")
                continue

            # Validate UML syntax
            if "```plantuml" in section.lower():
                uml_match = re.search(r"```plantuml\s*([\s\S]*?)```", section, flags=re.IGNORECASE)
            else:
                uml_match = re.search(r"@startuml([\s\S]*?)@enduml", section, flags=re.IGNORECASE)

            if uml_match:
                uml_content = uml_match.group(1) if uml_match.lastindex else uml_match.group(0)
                unclosed = uml_content.count("{") - uml_content.count("}")
                if unclosed != 0:
                    issues.append(f"{heading}: UML syntax error (unclosed braces)")

            explanation = section[:diagram_match.start()] if diagram_match else section
            explanation_len = len(re.sub(r"\s+", " ", explanation).strip())
            if explanation_len < MIN_ARCH_SECTION_EXPLANATION_CHARS:
                issues.append(f"{heading}: shallow explanation")

        # Sections with no diagrams (like Data and Persistence) should still have good explanation
        elif any(no_diag in heading_lower for no_diag in sections_no_diagram):
            explanation_len = len(re.sub(r"\s+", " ", section).strip())
            if explanation_len < MIN_ARCH_SECTION_EXPLANATION_CHARS:
                issues.append(f"{heading}: shallow explanation (no diagram, needs detailed text)")

    uml_blocks = _extract_plantuml_blocks(answer)
    if len(uml_blocks) < 4:
        issues.append("too few architecture diagrams (need at least 4)")
    elif len(uml_blocks) >= 3:
        normalized = [_normalize_uml_structure(b) for b in uml_blocks]
        non_empty = [n for n in normalized if n.strip()]
        unique_count = len(set(non_empty))
        if non_empty and unique_count < max(2, len(non_empty) - 1):
            issues.append("diagram structures are repetitive")

    return issues


def _infer_directory_purpose(name):
    purpose_map = {
        "frontend": "Frontend application and UI code",
        "client": "Frontend client application",
        "app": "Application source code",
        "src": "Primary source files",
        "server": "Backend server runtime and APIs",
        "backend": "Backend services and processing logic",
        "api": "API handlers and service endpoints",
        "components": "Reusable UI components",
        "models": "Data models and schema definitions",
        "routes": "HTTP route handlers",
        "public": "Static assets served to clients",
        "config": "Configuration files",
        "scripts": "Automation or build scripts",
        "tests": "Unit/integration tests",
        "test": "Unit/integration tests",
        "docs": "Documentation files",
    }
    lowered = name.lower()
    return purpose_map.get(lowered, "Project module or supporting code")


def _build_repo_layout_fallback(files_content, repo_root):
    rel_paths = []
    root_path = Path(repo_root)

    for absolute_path in files_content.keys():
        try:
            relative = Path(absolute_path).resolve().relative_to(root_path.resolve())
            rel_paths.append(relative)
        except Exception:
            continue

    top_dirs = {}
    for rel_path in rel_paths:
        if not rel_path.parts:
            continue
        head = rel_path.parts[0]
        if head.startswith("."):
            continue
        if len(rel_path.parts) > 1:
            top_dirs.setdefault(head, 0)
            top_dirs[head] += 1

    sorted_dirs = sorted(top_dirs.keys())

    manifests = []
    manifest_names = {
        "package.json": "Node.js package manifest",
        "requirements.txt": "Python dependencies",
        "pyproject.toml": "Python project metadata",
        "pom.xml": "Maven project manifest",
        "build.gradle": "Gradle build manifest",
        "go.mod": "Go module manifest",
    }

    for rel_path in rel_paths:
        file_name = rel_path.name.lower()
        if file_name in manifest_names:
            target = "Repository root" if len(rel_path.parts) == 1 else str(rel_path.parent).replace("\\", "/")
            manifests.append((str(rel_path).replace("\\", "/"), file_name, target))

    manifests = sorted(set(manifests))[:30]

    tree_lines = ["root"]
    max_top = min(8, len(sorted_dirs))
    for idx, directory in enumerate(sorted_dirs[:max_top]):
        branch = "└──" if idx == max_top - 1 else "├──"
        tree_lines.append(f"{branch} {directory}")

        children = set()
        for rel_path in rel_paths:
            if len(rel_path.parts) >= 2 and rel_path.parts[0] == directory:
                children.add(rel_path.parts[1])

        child_list = sorted(children)[:4]
        for child_idx, child in enumerate(child_list):
            child_branch = "└──" if child_idx == len(child_list) - 1 else "├──"
            tree_lines.append(f"    {child_branch} {child}")

    lines = [
        "### Repository Layout",
        "This section was generated from static repository scan because the LLM request failed for this topic.",
        "",
        "| Directory | Purpose |",
        "| --- | --- |",
    ]

    if sorted_dirs:
        for directory in sorted_dirs[:20]:
            lines.append(f"| {directory}/ | {_infer_directory_purpose(directory)} |")
    else:
        lines.append("| (no major directories detected) | Unknown |")

    lines.extend([
        "",
        "| Manifest | Package Name | Target |",
        "| --- | --- | --- |",
    ])

    if manifests:
        for manifest_path, package_name, target in manifests:
            lines.append(f"| {manifest_path} | {package_name} | {target} |")
    else:
        lines.append("| Unknown from current context | Unknown | Unknown |")

    lines.extend([
        "",
        "### Repository Structure Tree",
        "```text",
        *tree_lines,
        "```",
    ])

    return "\n".join(lines)


def fallback_architecture_diagram() -> str:
    return """@startuml
skinparam maxMessageSize 200
skinparam linetype ortho
skinparam backgroundColor transparent
skinparam defaultFontName Arial
skinparam defaultFontSize 13

actor "User" as User
component "Frontend" as Frontend
component "Backend API" as Backend
database "PostgreSQL" as Database
component "Cerebras LLM" as Cerebras

User --> Frontend : submits request
Frontend --> Backend : calls API
Backend --> Database : checks cache / stores analysis
Backend --> Cerebras : sends prompt
Cerebras --> Backend : returns response
Backend --> Frontend : returns analysis
@enduml"""


def _validate_and_fix_uml_syntax(uml_content: str) -> str:
    """Validate and fix common UML syntax errors."""
    if not uml_content:
        return uml_content

    lines = uml_content.splitlines()
    fixed_lines = []
    brace_depth = 0

    for line in lines:
        stripped = line.strip()

        # Skip empty lines and comments
        if not stripped or stripped.startswith("'"):
            fixed_lines.append(line)
            continue

        # Count braces for validation
        brace_depth += stripped.count("{") - stripped.count("}")

        # Fix missing closing braces at end of content
        if stripped and not stripped.endswith("{") and brace_depth < 0:
            brace_depth = 0

        fixed_lines.append(line)

    fixed_content = "\n".join(fixed_lines)

    # Close any unclosed braces before @enduml
    if brace_depth > 0 and "@enduml" in fixed_content.lower():
        fixed_content = fixed_content.replace("@enduml", "}" * brace_depth + "\n@enduml")

    return fixed_content


def sanitize_architecture_diagram(raw_diagram: str | None) -> str:
    if not raw_diagram:
        return fallback_architecture_diagram()

    block_match = PLANTUML_BLOCK_PATTERN.search(raw_diagram)
    diagram = block_match.group(0) if block_match else raw_diagram

    sanitized_lines = []
    aliases = set()

    for raw_line in diagram.splitlines():
        line = raw_line.strip()

        if not line or line.startswith("'"):
            continue

        lowered = line.lower()
        if lowered == "@startuml":
            sanitized_lines.append(line)
            sanitized_lines.append("skinparam maxMessageSize 200")
            sanitized_lines.append("skinparam linetype ortho")
            sanitized_lines.append("skinparam backgroundColor transparent")
            continue

        if lowered == "@enduml":
            sanitized_lines.append(line)
            continue

        node_match = PLANTUML_NODE_PATTERN.match(line)
        if node_match:
            kind = node_match.group(1).lower()
            label = node_match.group(2) or node_match.group(5)
            alias = node_match.group(3) or node_match.group(4)
            sanitized_lines.append(f'{kind} "{label}" as {alias}')
            aliases.add(alias)
            continue

        edge_match = PLANTUML_EDGE_PATTERN.match(line)
        if edge_match:
            source = edge_match.group(1)
            arrow = edge_match.group(2)
            target = edge_match.group(3)
            label = edge_match.group(4)

            if aliases and (source not in aliases or target not in aliases):
                continue

            edge_line = f"{source} {arrow} {target}"
            if label:
                edge_line += f" : {label}"
            sanitized_lines.append(edge_line)

    sanitized_diagram = "\n".join(sanitized_lines).strip()

    node_count = len(re.findall(r'^(actor|component|database|queue)\s+"[^"]+"\s+as\s+[A-Za-z_][A-Za-z0-9_]*$', sanitized_diagram, flags=re.IGNORECASE | re.MULTILINE))
    edge_count = len(re.findall(r'^[A-Za-z_][A-Za-z0-9_]*\s*([-.]+>+|<[-.]+|<[-.]+>+|<\|--|--\|>|-->|->|\.\.>|<\.\.>?)\s*[A-Za-z_][A-Za-z0-9_]*(?:\s*:\s*.+)?$', sanitized_diagram, flags=re.IGNORECASE | re.MULTILINE))

    if "@startuml" not in sanitized_diagram.lower() or "@enduml" not in sanitized_diagram.lower() or node_count == 0 or edge_count == 0:
        return fallback_architecture_diagram()

    return sanitized_diagram


def _fix_architecture_text_uml_syntax(text: str) -> str:
    """Fix UML syntax errors in embedded diagrams within architecture text."""
    if not isinstance(text, str):
        return text

    # Fix fenced PlantUML blocks
    def fix_fenced_planuml(match):
        content = match.group(1)
        fixed = _validate_and_fix_uml_syntax(content)
        return f"```plantuml\n{fixed}\n```"

    text = re.sub(r"```plantuml\s*([\s\S]*?)```", fix_fenced_planuml, text, flags=re.IGNORECASE)

    # Fix raw PlantUML blocks
    def fix_raw_planuml(match):
        content = match.group(0)
        fixed = _validate_and_fix_uml_syntax(content)
        return fixed

    text = re.sub(r"@startuml[\s\S]*?@enduml", fix_raw_planuml, text, flags=re.IGNORECASE)

    return text


def generate_repo_analysis(repo_url):
    repo = get_repo(repo_url)
    if repo is None:
        raise RuntimeError("Failed to initialize the repository.")

    print(f"Repository '{repo.working_dir}' initialized successfully.")

    files_content = read_all_files(repo.working_dir)
    print(f"Total files read: {len(files_content)}")

    if not files_content:
        raise RuntimeError("No readable source files found in repository after filtering.")

    chunks = chunk_files(files_content)
    print("Total chunks:", len(chunks))

    if not chunks:
        raise RuntimeError("No chunks generated from repository files.")

    chunks_emb = embed_chunks(chunks)
    print("Embeddings generated:", len(chunks_emb))

    index = create_vector_store(chunks)
    print("Vector store created")

    results = {}

    evidence_prompt = PROMPTS.get("evidence_extraction")
    evidence_context = ""
    extracted_evidence = {"note": "No evidence extracted."}

    if evidence_prompt:
        evidence_chunks = retrieve_chunks(evidence_prompt, index, chunks, top_k=20)
        evidence_context = "\n".join(evidence_chunks)
        raw_evidence = ask_llm(evidence_prompt, evidence_context, section_key="evidence_extraction")

        try:
            extracted_evidence = json.loads(raw_evidence)
        except Exception:
            block_match = re.search(r"\{[\s\S]*\}", raw_evidence)
            if block_match:
                try:
                    extracted_evidence = json.loads(block_match.group(0))
                except Exception:
                    extracted_evidence = {"raw_evidence": raw_evidence}
            else:
                extracted_evidence = {"raw_evidence": raw_evidence}

        print("Evidence extraction complete")

    protocol_signals = _extract_protocol_signals(files_content)
    extracted_evidence = _merge_extracted_evidence(extracted_evidence, protocol_signals)
    print(
        "Protocol scan signals:",
        len(extracted_evidence.get("communication", {}).get("http_endpoints", [])),
        "endpoints,",
        len(extracted_evidence.get("communication", {}).get("events", [])),
        "events",
    )

    for key, prompt in PROMPTS.items():
        if key == "evidence_extraction":
            continue

        retrieved_chunks = retrieve_chunks(prompt, index, chunks)
        context = "\n".join(retrieved_chunks)

        if key == "architecture_text":
            richer_chunks = retrieve_chunks(prompt, index, chunks, top_k=20)
            context = "\n".join(richer_chunks)
        elif key == "rpc_protocol":
            # Get more endpoint definitions and payload examples for better inference
            richer_chunks = retrieve_chunks(prompt, index, chunks, top_k=18)
            context = "\n".join(richer_chunks)
        elif key == "repo_layout":
            richer_chunks = retrieve_chunks(prompt, index, chunks, top_k=14)
            context = "\n".join(richer_chunks)

        answer = ask_llm(prompt, context, section_key=key, evidence=extracted_evidence)

        if key == "architecture_text":
            missing_sections = _missing_architecture_sections(answer)
            if missing_sections:
                repair_prompt = (
                    f"{prompt} "
                    f"Your previous draft missed these required sections: {', '.join(missing_sections)}. "
                    "Regenerate the full architecture output with all required sections in order."
                )
                repaired = ask_llm(repair_prompt, context, section_key=key, evidence=extracted_evidence)
                repaired_missing = _missing_architecture_sections(repaired)
                answer = repaired if not repaired_missing else _append_missing_architecture_sections(repaired, repaired_missing)

            quality_issues = _architecture_text_quality_issues(answer)
            if quality_issues:
                repair_prompt = (
                    f"{prompt} "
                    "Regenerate the full architecture document from scratch and improve depth and technical specificity. "
                    "Use concrete evidence from context, avoid generic statements, and ensure section diagrams are structurally different. "
                    f"Fix these issues from the previous draft: {', '.join(quality_issues[:8])}."
                )
                repaired = ask_llm(repair_prompt, context, section_key=key, evidence=extracted_evidence)
                repaired_issues = _architecture_text_quality_issues(repaired)
                if len(repaired_issues) < len(quality_issues):
                    answer = repaired

        if isinstance(answer, str) and answer.strip() == "LLM request failed.":
            if key == "repo_layout":
                answer = _build_repo_layout_fallback(files_content, repo.working_dir)
            else:
                answer = "LLM request failed for this section after retries."

        if key == "rpc_protocol":
            fallback_section = _build_rpc_fallback_from_signals(protocol_signals)
            if "No confirmed API endpoint discovered in retrieved context." in answer:
                answer = f"{answer}\n\n{fallback_section}".strip()
            elif fallback_section:
                answer = f"{answer}\n\n{fallback_section}".strip()

        if key == "architecture_diagram":
            answer = sanitize_architecture_diagram(answer)

        if key == "architecture_text":
            answer = _fix_architecture_text_uml_syntax(answer)

        results[key] = answer
        print(f"{key}: {answer}")

    store_repo_analysis(repo_url, results)
    print("Saved to database")

    persisted = get_repo_analysis(repo_url)
    if persisted is not None:
        return persisted

    return {
        "repo_url": repo_url,
        **results,
    }


if __name__ == "__main__":
    user_input = input("Enter the path to the Git repository: ")
    try:
        generate_repo_analysis(user_input)
    except Exception as exc:
        print(f"Error: {exc}")
        raise