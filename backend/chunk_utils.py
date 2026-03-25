import ast
import os


def _slice_by_lines(text, start_line, end_line):
    lines = text.splitlines(keepends=True)
    start_idx = max(start_line - 1, 0)
    end_idx = min(end_line, len(lines))
    return "".join(lines[start_idx:end_idx]).strip()


def _node_source(text, node):
    if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
        return _slice_by_lines(text, node.lineno, node.end_lineno)

    segment = ast.get_source_segment(text, node)
    return (segment or "").strip()


def _build_chunk(path, chunk_type, name, source, methods=None, parent=None):
    methods = methods or []
    header = [f"File: {path}", f"Type: {chunk_type}", f"Name: {name}"]

    if parent:
        header.append(f"Parent: {parent}")

    if methods:
        header.append(f"Methods: {', '.join(methods)}")

    header_text = "\n".join(header)
    body = source.strip() if source else ""

    text = f"{header_text}\n\n{body}" if body else header_text

    return {
        "text": text,
        "path": path,
        "type": chunk_type,
        "name": name,
        "methods": methods,
        "parent": parent,
    }


def _fallback_char_chunks(path, text, chunk_size=1200, overlap=200):
    chunks = []
    start = 0

    while start < len(text):
        chunk_text = text[start:start + chunk_size]
        chunk_name = f"module_segment_{start // max(chunk_size - overlap, 1) + 1}"
        chunks.append(_build_chunk(path, "Module", chunk_name, chunk_text))

        step = max(chunk_size - overlap, 1)
        start += step

    return chunks


def _python_ast_chunks(path, text):
    chunks = []
    tree = ast.parse(text)

    module_parts = []
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        source = _node_source(text, node)
        if source:
            module_parts.append(source)

    module_source = "\n\n".join(module_parts).strip()
    chunks.append(_build_chunk(path, "Module", os.path.basename(path), module_source))

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            method_nodes = [
                n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            method_names = [n.name for n in method_nodes]

            class_source = _node_source(text, node)
            chunks.append(
                _build_chunk(path, "Class", node.name, class_source, methods=method_names)
            )

            for method_node in method_nodes:
                method_source = _node_source(text, method_node)
                method_name = f"{node.name}.{method_node.name}"
                chunks.append(
                    _build_chunk(
                        path,
                        "Method",
                        method_name,
                        method_source,
                        parent=node.name,
                    )
                )

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            function_source = _node_source(text, node)
            chunks.append(_build_chunk(path, "Function", node.name, function_source))

    return chunks


def chunk_files(files, chunk_size=1200, overlap=200):
    chunks = []

    for path, text in files.items():
        if path.lower().endswith(".py"):
            try:
                chunks.extend(_python_ast_chunks(path, text))
                continue
            except SyntaxError:
                pass

        chunks.extend(_fallback_char_chunks(path, text, chunk_size=chunk_size, overlap=overlap))

    return chunks