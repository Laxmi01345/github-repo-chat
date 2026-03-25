from git import Repo
import os


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
def get_repo(path):
    print(f"Attempting to initialize repository at path: {path}")
    try:
        temp_dir = "temp_dir"
        repo_name = path.split("/")[-1].replace(".git", "")
        local_path= os.path.join(temp_dir, repo_name)
        if os.path.exists(local_path):
            print(f"Repository already exists at {local_path}, reusing it.")
            return Repo(local_path)
        repo_path = os.path.join(temp_dir, repo_name)
        repo = Repo.clone_from(path, repo_path)
        return repo
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

