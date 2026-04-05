import json
import os
import time
from dotenv import load_dotenv
from cerebras.cloud.sdk import Cerebras

# load .env file
load_dotenv()

# read environment variable
api_key = os.getenv("CEREBRAS_API_KEY")

client = Cerebras(api_key=api_key)


# Keep one-message prompts well below provider limits.
MAX_PROMPT_CHARS = int(os.getenv("LLM_MAX_PROMPT_CHARS", "5200"))
MIN_CONTEXT_CHARS = 600
MIN_EVIDENCE_CHARS = 500


SECTION_STYLE = {
    "evidence_extraction": (
        "Return STRICT JSON only using the required schema. "
        "No markdown fences, no commentary, no extra keys."
    ),
    "purpose_scope": (
        "Output 3-5 short paragraphs with bold headings. "
        "Start exactly with: The purpose of the project is to ..."
    ),
    "repo_layout": (
        "Output exactly three parts in order: "
        "(1) concise bullet list by folder/responsibility; "
        "(2) one fenced ```text repository tree block using tree-style lines; "
        "(3) one PlantUML package diagram (NOT sequence, NOT actor, NOT component). "
        "Use only 'package \"FolderName\"' syntax to show folder hierarchy. "
        "The diagram must be wrapped in @startuml/@enduml, contain at most 15 packages, show only folder structure, and no communication flows."
    ),
    "source_layer": (
        "Output bullet points grouped by backend/frontend/shared modules and key functions."
    ),
    "tech_stack": (
        "Output a markdown table with columns: Layer, Technology, Purpose, Evidence. "
        "Keep it concise and include only technologies supported by context evidence."
    ),
    "architecture_text": (
        "Output EXACT sections in THIS ORDER (ALL FIVE REQUIRED): System Components, Communication Flow, Realtime and Messaging Layer, Data and Persistence, Request Lifecycle. "
        "Each section must include at least 3 concrete evidence points (files/modules/endpoints/events/technologies/data entities) in explanation. "
        "For System Components: list components and subcomponents with file/module names. Then output PlantUML tree diagram using hierarchical arrows (->). "
        "For Communication Flow: explain protocol interactions with actors and message flows. Output sequence diagram. "
        "For Realtime and Messaging Layer: explain event/pub-sub patterns if evidenced. Output diagram showing emitters and listeners. "
        "For Data and Persistence: CRITICAL - output deep explanation inferring from code: (1) Data models from ORM classes, database schemas, table definitions. (2) Storage layer type (DB, cache, queue). (3) Persistence patterns from queries, create/read/update/delete operations. Look for imports like 'db.', 'cursor', 'ORM', 'Schema' and infer what data is stored where. NO DIAGRAM for this section. "
        "For Request Lifecycle: output step-by-step flow from request to response with actual flow steps identified from code. Output activity or sequence diagram. "
        "All diagrams max 8 nodes and 12 edges per section. Valid PlantUML syntax (@startuml/@enduml, proper braces). "
        "Do NOT omit sections. If truly unknown, write 'Unknown from current context' in the section but keep the section header and heading present."
    ),
    "rpc_protocol": (
        "Output structured documentation of the external interface layer using evidence from code. "
        "Include 'Communication Technologies Detected' section listing each technology (HTTP, WebSocket, etc.) and its role. "
        "For HTTP endpoints, create a table with columns: Method | Path | Purpose | Request Body | Response Body. "
        "For each endpoint: infer PURPOSE from function logic/names, REQUEST BODY structure from parameters/parsing, RESPONSE BODY from return data/fields. "
        "Be specific and concrete: describe actual data fields and types. For example, if you see request.json.get('question'), write 'JSON object with question (string)' in Request Body. "
        "For events, create an Events table with columns: Event | Technology | Emitter | Listener | Payload | Purpose. "
        "Infer meaning from code context: socket emissions, function names, parameter names, documentation. "
        "Only write 'Unknown from current context' if truly no evidence exists to make an informed inference."
    ),
    "chat": (
        "Answer like a helpful repository assistant. "
        "Use the provided repository context and analysis snapshot to answer the user's question directly. "
        "Keep the response grounded, specific, and concise. "
        "If the answer is not supported by the context, say so clearly."
    ),
}


def _format_evidence(evidence):
    if evidence is None:
        return "No extracted evidence provided."

    if isinstance(evidence, str):
        return evidence

    try:
        return json.dumps(evidence, indent=2)
    except Exception:
        return str(evidence)


def _slice_list(items, limit):
    if not isinstance(items, list):
        return []
    return items[:limit]


def _truncate_text(text, max_chars, label):
    if text is None:
        return ""

    s = text if isinstance(text, str) else str(text)
    if max_chars <= 0:
        return f"[{label} omitted due to prompt budget]"
    if len(s) <= max_chars:
        return s

    suffix = f"\n\n[{label} truncated: showing first {max_chars} chars of {len(s)}]"
    keep = max(0, max_chars - len(suffix))
    return s[:keep] + suffix


def _build_bounded_prompt(task_prompt, style_instruction, depth_rule, evidence_block, context):
    base = f"""
You are generating repository documentation in a DeepWiki-like professional tone.

Hard requirements:
- Use only evidence present in the provided context.
- Do not mention package manager internals, lockfile dependency trees, or node_modules details.
- Do not hallucinate endpoints, frameworks, files, or components.
- Prefer concise, high-signal language over generic commentary.
- If evidence is insufficient, explicitly say what is unknown.
- Prefer detailed explanations over short summaries when evidence exists.

Task:
{task_prompt}

Section formatting requirement:
{style_instruction}

Depth requirement:
{depth_rule}

Extracted evidence (highest priority grounding source):
"""

    base_with_context_header = base + "\n\nRepository context:\n"
    remaining = MAX_PROMPT_CHARS - len(base_with_context_header)

    # If instructions themselves are too long, hard-trim the whole prompt.
    if remaining <= 0:
        return _truncate_text(base_with_context_header, MAX_PROMPT_CHARS, "prompt")

    evidence_budget = max(MIN_EVIDENCE_CHARS, int(remaining * 0.45))
    context_budget = max(MIN_CONTEXT_CHARS, remaining - evidence_budget)

    # Rebalance when one side is small.
    if len(evidence_block) < evidence_budget:
        context_budget += evidence_budget - len(evidence_block)
    if len(context) < context_budget:
        evidence_budget += context_budget - len(context)

    clipped_evidence = _truncate_text(evidence_block, evidence_budget, "evidence")
    clipped_context = _truncate_text(context, context_budget, "context")

    final_prompt = f"{base}{clipped_evidence}\n\nRepository context:\n{clipped_context}"
    return _truncate_text(final_prompt, MAX_PROMPT_CHARS, "prompt")


def ask_llm(prompt, context, section_key=None, evidence=None):

    style_instruction = SECTION_STYLE.get(
        section_key,
        "Write in a professional technical documentation style.",
    )

    condensed_evidence = _condense_evidence_for_section(section_key, evidence)
    evidence_block = _format_evidence(condensed_evidence)

    depth_rule = (
        "Every section must include at least 3 concrete references to files, modules, "
        "events, endpoints, or technologies from the extracted evidence whenever available."
    )

    final_prompt = _build_bounded_prompt(
        task_prompt=prompt,
        style_instruction=style_instruction,
        depth_rule=depth_rule,
        evidence_block=evidence_block,
        context=context,
    )

    for attempt in range(5):

        try:
            response = client.chat.completions.create(
                model="llama3.1-8b",
                messages=[{"role": "user", "content": final_prompt}],
                temperature=0.2
            )

            return response.choices[0].message.content

        except Exception as e:
            print(e)
            print("LLM busy, retrying...")
            time.sleep(5)

    return "LLM request failed."


def _condense_evidence_for_section(section_key, evidence):
    if not isinstance(evidence, dict):
        return evidence

    communication = evidence.get("communication") if isinstance(evidence.get("communication"), dict) else {}

    # Keep architecture prompts focused to avoid model truncation.
    if section_key == "architecture_text":
        return {
            "components": evidence.get("components", {}),
            "technologies": _slice_list(evidence.get("technologies"), 20),
            "communication": {
                "protocols": _slice_list(communication.get("protocols"), 20),
                "http_endpoints": _slice_list(communication.get("http_endpoints"), 24),
                "events": _slice_list(communication.get("events"), 30),
            },
            "data_layer": evidence.get("data_layer", {}),
            "entry_points": _slice_list(evidence.get("entry_points"), 20),
        }

    if section_key == "rpc_protocol":
        return {
            "communication": {
                "protocols": _slice_list(communication.get("protocols"), 30),
                "http_endpoints": _slice_list(communication.get("http_endpoints"), 80),
                "events": _slice_list(communication.get("events"), 100),
            }
        }

    return evidence
