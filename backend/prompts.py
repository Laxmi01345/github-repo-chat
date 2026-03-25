PROMPTS = {

    "purpose_scope": (
        "Write a concise repository overview in third-person documentation style. "
        "Explain the purpose, scope, and primary capabilities of the project based only on the provided context. "
        "Mention the main problem the project solves, the intended users or environment, and the overall maturity "
        "or stage of the project if it can be inferred. Do not speculate or invent details not present in the context."
    ),

    "repo_layout": (
        "Describe the repository layout in a structured documentation style. "
        "Explain the major top-level directories, their responsibilities, and important entry files. "
        "Ignore dependency folders such as node_modules, build outputs, and vendor directories. "
        "Also include a repository structure tree in a fenced ```text block using tree-style lines (for example: root, ├──, └──). "
        "Show at least top-level folders and one important nested level for each major area. "
        "After the explanation, include a compact PlantUML diagram showing repository structure as a logical hierarchy. "
        "Keep the diagram concise with at most 15 nodes and avoid duplicate edges. "
        "Wrap the diagram in @startuml ... @enduml tags."
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
        "If a layer is not evidenced, explicitly state it is unknown rather than guessing."
    ),

    "architecture_text": (
        "Provide a clear architectural description of the system in third-person documentation style. "
        "Explain the main components of the system, their responsibilities, and how they interact. "
        "Describe data flow and control flow between major parts such as backend services, APIs, "
        "frontend layers, databases, or processing modules if they appear in the code context. "
        "Only reference components that appear in the retrieved source context."
    ),

    "architecture_diagram": (
        "Generate a PlantUML component diagram that represents the project or system architecture, not the repository layout. "
        "Focus on runtime components: user-facing flows, backend services, APIs, processing stages, data stores, and external integrations visible in the provided source context. "
        "Do not draw directory trees, file hierarchies, folder relationships, or repository structure. "
        "Do not use filenames, file paths, README nodes, package manifests, or source folders as architecture nodes unless they directly represent a runtime component exposed by the system. "
        "Use PlantUML component syntax: actor, component, database, queue, and arrow notation. "
        "Use clear, human-readable labels on each component. "
        "Show relationships between application layers and services using action-oriented labels such as 'submits', 'calls', 'retrieves', 'stores', 'renders', or 'returns'. "
        "Keep the diagram compact: maximum 20 nodes and 30 edges. Do not repeat the same edge pair more than once. "
        "Always wrap the output in @startuml and @enduml tags. "
        "Output only valid PlantUML code without explanations or markdown outside the diagram block."
    ),

    "rpc_protocol": (
        "Document the external interfaces of the system in professional documentation style. "
        "Describe APIs, RPC endpoints, service interfaces, or communication mechanisms if they exist in the code. "
        "Explain the purpose of each interface and the interaction pattern between services. "
        "If no clear API or RPC layer exists in the provided context, explicitly state that "
        "the repository does not expose a defined external protocol."
    )
}