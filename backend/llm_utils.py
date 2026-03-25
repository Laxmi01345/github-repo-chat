import os
import time
from dotenv import load_dotenv
from cerebras.cloud.sdk import Cerebras

# load .env file
load_dotenv()

# read environment variable
api_key = os.getenv("CEREBRAS_API_KEY")

client = Cerebras(api_key=api_key)


SECTION_STYLE = {
    "purpose_scope": (
        "Output 3-5 short paragraphs with bold headings. "
        "Start exactly with: The purpose of the project is to ..."
    ),
    "repo_layout": (
        "Output exactly three parts in order: "
        "(1) concise bullet list by folder/responsibility; "
        "(2) one fenced ```text repository tree block using tree-style lines; "
        "(3) one PlantUML diagram block. "
        "The diagram must be wrapped in @startuml/@enduml, contain at most 15 nodes, and avoid duplicate edges."
    ),
    "source_layer": (
        "Output bullet points grouped by backend/frontend/shared modules and key functions."
    ),
    "tech_stack": (
        "Output a markdown table with columns: Layer, Technology, Purpose, Evidence. "
        "Keep it concise and include only technologies supported by context evidence."
    ),
    "architecture_text": (
        "Output a structured narrative with headings: Components, Data Flow, Integration Points."
    ),
    "architecture_diagram": (
        "Output only a valid PlantUML component diagram wrapped in @startuml and @enduml tags. "
        "Use actor, component, database, and arrow notation. Add human-readable labels. "
        "Keep output compact with at most 20 nodes and 30 edges, and no duplicated edge pair. No extra prose."
    ),
    "rpc_protocol": (
        "Output headings: Endpoints, Payloads, Integrations, Notes. "
        "If no endpoint is found in context, explicitly write: No confirmed API endpoint discovered in retrieved context."
    ),
}


def ask_llm(prompt, context, section_key=None):

    style_instruction = SECTION_STYLE.get(
        section_key,
        "Write in a professional technical documentation style.",
    )

    final_prompt = f"""
You are generating repository documentation in a DeepWiki-like professional tone.

Hard requirements:
- Use only evidence present in the provided context.
- Do not mention package manager internals, lockfile dependency trees, or node_modules details.
- Do not hallucinate endpoints, frameworks, files, or components.
- Prefer concise, high-signal language over generic commentary.
- If evidence is insufficient, explicitly say what is unknown.

Task:
{prompt}

Section formatting requirement:
{style_instruction}

Repository context:
{context}
"""

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