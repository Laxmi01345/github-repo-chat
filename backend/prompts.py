PROMPTS = {

    "purpose_scope": (
    "Write a detailed repository overview in third-person technical documentation style based ONLY on the provided context.\n\n"

    "STRICT RULES:\n"
    "- Do NOT be concise; provide in-depth explanation.\n"
    "- Do NOT speculate or invent missing details.\n"
    "- Every claim must be grounded in the provided context.\n"
    "- Avoid vague phrases like 'various features' or 'etc.'. Be explicit.\n\n"

    "STRUCTURE (MANDATORY):\n\n"

    "## Purpose\n"
    "- Clearly explain the primary objective of the project.\n"
    "- Describe the core problem it is designed to solve.\n"
    "- Include why this problem matters in its domain.\n\n"

    "## Scope\n"
    "- Define what the project covers and what it does NOT cover (if inferable).\n"
    "- Describe boundaries, supported use cases, and limitations if visible.\n\n"

    "## Key Capabilities\n"
    "- List and explain the main features or functionalities.\n"
    "- For each capability, describe what it does and how it contributes to the system.\n\n"

    "## Target Users / Environment\n"
    "- Identify intended users (developers, end-users, internal tools, etc.).\n"
    "- Describe the environment where the system operates (web app, CLI, backend service, etc.).\n\n"

    "## Project Maturity\n"
    "- Assess the stage of the project (early-stage, prototype, production-ready) ONLY if evidence exists.\n"
    "- Use signals like documentation completeness, configuration files, tests, or deployment setup.\n"
    "- If unclear, explicitly state: 'Unknown from current context'.\n\n"

    "Write in clean, well-structured paragraphs or bullet groups. Ensure depth, clarity, and completeness without unnecessary repetition."
),

    "repo_layout": (
        "Write a repository layout section in a DeepWiki-like style with crisp structure and concrete evidence from context. "
        "Ignore dependency folders such as node_modules, build outputs, vendor folders, and transient runtime output directories. "
        "Use exactly this output structure and headings: "
        "1) '### Repository Layout' with a short intro paragraph. "
        "2) A markdown table with columns: Directory | Purpose. Include only meaningful project directories. "
        "3) A markdown table with columns: Manifest | Package Name | Target for important package manifests when present. "
        "4) '### Repository Structure Tree' followed by a fenced ```text tree using root/├──/└── and 2-3 levels of important paths. "
        "5) '### Repository Structure Diagram (PlantUML)' followed by a PlantUML block using package syntax to mirror the same hierarchy. "
        "Keep the layout diagram structural only (no runtime communication arrows). "
        "Keep it concise and accurate: max 18 package nodes. "
        "Always include @startuml and @enduml. "
        "Do not include claims that are not visible in the provided context."
    ),

    "source_layer": (
        "Summarize the source layer of the repository in a technical documentation style. "
        "Describe the core modules, important files, and key classes or functions if present. "
        "Explain the responsibility of each major source component and how the modules relate to each other. "
        "Ignore lockfiles, dependency folders, and generated files."
    ),

    "tech_stack": (
        "Document the technology stack used by the project in a concise, reader-friendly format. "
        "Infer technologies only from concrete evidence in the provided source context (framework imports, dependency files, config files, runtime code). "
        "Group technologies by layer such as frontend, backend, database, AI/ML, infrastructure, and tooling. "
        "For each technology, add a short purpose note. "
    ),

    "architecture_text": (
        "Provide a detailed architecture overview in third-person technical documentation style, similar to an architecture-overview page. "
        "Focus on runtime behavior, not folder structure. "
        "Use EXACTLY these sections in this order: "
        "1) '## System Components' "
        "2) '## Communication Flow' "
        "3) '## Realtime and Messaging Layer' "
        "4) '## Data and Persistence' "
        "5) '## Request Lifecycle'. "
        "\n"
        "For System Components: output explanation first listing each major component and subcomponent with file/module names. Then output a PlantUML tree diagram showing the component hierarchy. Use this format: draw components with parent-child relationships using edges (->). For example, show Frontend component containing Login, MainPanel, Chat subcomponents. Use 'component' or 'folder' types. Max 10 nodes. Proper nesting and clear hierarchy."
        "\n"
        "For Data and Persistence: output DEEP EXPLANATION ONLY. No diagram. Infer and describe: (1) Data models - look for database schemas, ORM models (e.g., SQLAlchemy classes, Mongoose schemas), table/collection structures. (2) Storage layer - identify the database type (SQL, NoSQL, message queue, cache). (3) Persistence patterns - describe how data flows: what gets written, when, where (create/update/delete operations). For example, if you see 'cursor.execute(\"INSERT INTO users\")', explain that users are persisted to database. If you see Redis calls, explain caching strategy. Be specific about what data persists where. Infer from code: database imports, connection code, table creation, ORM models, queries."
        "\n"
        "For Request Lifecycle: output explanation first describing the step-by-step flow from user request to response. Then output an activity or sequence diagram showing the complete request flow. For example: (1) User submits input in frontend, (2) Frontend calls API endpoint, (3) Backend processes request, (4) Queries database, (5) Returns response, (6) Frontend displays result. Identify each step from evidence."
        "\n"
        "CRITICAL: All five sections MUST be output. Do not omit sections. If details are truly unknown, write 'Unknown from current context' within the section but still include the section heading and explanation attempt. Use only evidenced component/module names from context."
    ),

    "architecture_diagram": (
        "Generate a PlantUML runtime architecture diagram (not repository layout) using only: actor, component, database, queue, and arrows. "
        "Show communication edges for every technology evidenced in context (HTTP, WebSocket/Socket.IO, gRPC, queue/pub-sub, database operations, external APIs). "
        "Use clear action labels that match observed behavior, such as: 'HTTP request', 'HTTP response', 'connect', 'emit event', 'broadcast', 'publish', 'consume', 'execute code', 'persist', 'retrieve'. "
        "Preferred node style is application components (e.g., User, Browser Client, Socket.IO Client, API Server, Socket.IO Server, Execution Service, Database). "
        "Do not include file paths or directory names as nodes. "
        "Assign unique aliases and keep labels human-readable. "
        "Keep under 22 nodes and 34 edges. "
        "Always wrap in @startuml and @enduml and output only the PlantUML block."
    ),

    "rpc_protocol": (
        "Document the external interface layer in a protocol-focused style using evidence from code context. "
        "Include a section named 'Communication Technologies Detected' listing each evidenced technology and its role. "
        "For event-based systems, include a table named 'Events' with columns: Event | Technology | Emitter | Listener | Payload (if known) | Purpose. "
        "Include an 'HTTP Endpoints' table with Method | Path | Purpose | Request Body | Response Body. For each endpoint: "
        "- Infer PURPOSE from function names, context, docstrings. For example, '/api/chat' is for chat messages, '/run' executes code. "
        "- Infer REQUEST BODY by examining function parameters, POST data parsing, or JSON schemas in code. "
        "- Infer RESPONSE BODY by examining return statements, response fields, or success/error structures. "
        "For queue/pub-sub systems, include a 'Topics or Queues' table with Topic/Queue | Producer | Consumer | Payload | Purpose when evidence exists. "
        "Describe request/response and pub/sub interaction patterns clearly and separately. "
        "Be specific and concrete: avoid generic descriptions. If truly no evidence exists for a field, then write 'Unknown from current context'."
    )
}