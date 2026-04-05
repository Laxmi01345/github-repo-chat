import hashlib
import os
import shutil
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from git import Repo


CACHE_DIR = Path(__file__).resolve().parent.parent / "temp_dir"


SKIP_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".next",
}

SKIP_FILENAMES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
}

SKIP_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".pdf",
    ".zip",
    ".exe",
    ".dll",
    ".bin",
}

MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024


def _normalize_repo_source(path):
    raw = (path or "").strip()
    if not raw:
        return raw

    parsed = urlparse(raw)
    if parsed.scheme in {"http", "https", "git", "ssh"}:
        cleaned = parsed._replace(query="", fragment="")
        normalized = urlunparse(cleaned).rstrip("/")
        return normalized

    return str(Path(raw).expanduser().resolve())


def _repo_cache_name(path):
    parsed = urlparse(path)
    if parsed.scheme in {"http", "https", "git", "ssh"}:
        pieces = [piece for piece in parsed.path.split("/") if piece]
        owner = pieces[-2] if len(pieces) >= 2 else "repo"
        repo = pieces[-1].replace(".git", "") if pieces else "repo"
        base_name = f"{owner}__{repo}" or "repo"
    else:
        base_name = os.path.basename(path.rstrip(os.sep)) or "repo"

    safe_base = "".join(character if character.isalnum() or character in {"-", "_", "."} else "_" for character in base_name)
    digest = hashlib.sha1(path.encode("utf-8")).hexdigest()[:10]
    return f"{safe_base[:60]}_{digest}"


def _repo_cache_path(path):
    return CACHE_DIR / _repo_cache_name(path)


def _repo_has_files(local_path):
    for root, dirs, files in os.walk(local_path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        if files:
            return True

    return False


def _is_ready_repo(local_path):
    return local_path.exists() and (local_path / ".git").exists() and _repo_has_files(local_path)


def prepare_repo(path):
    normalized_path = _normalize_repo_source(path)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    local_path = _repo_cache_path(normalized_path)
    if _is_ready_repo(local_path):
        print(f"Repository already exists at {local_path}, reusing it.")
        return {
            "repo": Repo(str(local_path)),
            "local_path": str(local_path),
            "reused": True,
        }

    if local_path.exists():
        shutil.rmtree(local_path, ignore_errors=True)

    print(f"Cloning repository into {local_path}")
    repo = Repo.clone_from(normalized_path, str(local_path))
    return {
        "repo": repo,
        "local_path": str(local_path),
        "reused": False,
    }


def get_repo(path):
    try:
        normalized_path = _normalize_repo_source(path)
        print(f"Attempting to initialize repository at path: {normalized_path}")
        prepared = prepare_repo(normalized_path)
        return prepared["repo"]
    except Exception as e:
        print(f"Error occurred while initializing repository: {e}")
        return None


def read_all_files(repo_path):
    files_content = {}
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for file in files:
            path = os.path.join(root, file)
            lower_name = file.lower()
            _, extension = os.path.splitext(lower_name)

            if lower_name in SKIP_FILENAMES:
                continue

            if extension in SKIP_EXTENSIONS:
                continue

            try:
                if os.path.getsize(path) > MAX_FILE_SIZE_BYTES:
                    continue
            except OSError:
                continue

            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    files_content[path] = f.read()
            except Exception as e:
                # Skip files that cannot be read (binaries, etc.)
                print(f"Skipped {path}: {e}")
    return files_content

