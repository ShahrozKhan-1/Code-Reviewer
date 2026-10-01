import re
import urllib.request
import zipfile
import io
import os
from pathlib import Path


import fnmatch
from pathlib import Path

EXCLUDE_DIRS = {
    ".git", ".svn", ".hg", ".bzr",
    # JS/TS
    "node_modules", "bower_components", ".yarn", ".pnp", ".pnpm-store",
    # Python
    "venv", ".venv", "env", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".tox", ".nox", ".hypothesis", "htmlcov",
    # Build outputs
    "dist", "build", "out", "obj", "target",
    ".next", ".nuxt", ".parcel-cache", ".turbo", ".vite", ".webpack",
    "coverage",
    # Vendor
    "vendor", ".bundle", ".gradle", ".m2", ".nuget",
    "Pods", ".dart_tool", ".pub-cache",
    # IDE / OS
    ".idea", ".vscode", ".vs", ".fleet",
    # Docs builds
    "_build", ".docusaurus",
}

EXCLUDE_FILES = {
    # Lockfiles
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb",
    "npm-shrinkwrap.json", "go.sum", "Cargo.lock", "poetry.lock",
    "Pipfile.lock", "Gemfile.lock", "composer.lock", "gradle.lockfile",
    # OS
    ".DS_Store", "Thumbs.db", "desktop.ini",
    # Logs
    "npm-debug.log", "yarn-debug.log", "yarn-error.log", "pnpm-debug.log",
}

EXCLUDE_GLOBS = {
    "*.egg-info", "*.tmp", "*.temp", "*.bak", "*.swp", "*.swo",
}

EXCLUDE_SUFFIXES = {
    # media, archives, binaries, ML — as in the suggestion
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".bmp", ".tiff", ".avif", ".heic",
    ".mp3", ".wav", ".ogg", ".flac", ".aac", ".m4a",
    ".mp4", ".mov", ".avi", ".mkv", ".webm", ".wmv",
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".rar", ".7z", ".iso",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
    ".exe", ".dll", ".so", ".dylib", ".class", ".jar", ".apk", ".aab", ".msi",
    ".pyc", ".pyo", ".o", ".obj", ".a", ".lib",
    ".min.js", ".min.css", ".map",
    ".db", ".sqlite", ".sqlite3", ".mdb",
    ".pkl", ".pickle", ".joblib",
    ".pt", ".pth", ".ckpt", ".onnx", ".safetensors",
    ".parquet", ".feather",
}

# Secrets: excluded from Explorer reads, but *signaled* to the Planner.
SENSITIVE_FILES = {
    ".env", ".env.local", ".env.development", ".env.production", ".env.test",
    "credentials.json", "secrets.json", "service-account.json",
    "id_rsa", "id_ed25519",
}
SENSITIVE_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".crt"}
SENSITIVE_ALLOWLIST = {
    ".env.example", ".env.sample", ".env.template", ".env.dist",
}

MAX_FILE_BYTES = 250_000


def _is_sensitive(name: str) -> bool:
    if name in SENSITIVE_ALLOWLIST:
        return False
    if name in SENSITIVE_FILES:
        return True
    return any(name.endswith(s) for s in SENSITIVE_SUFFIXES)


def _is_visible(item: Path) -> bool:
    name = item.name
    if item.is_dir():
        return name not in EXCLUDE_DIRS
    if name in EXCLUDE_FILES:
        return False
    if any(fnmatch.fnmatch(name, g) for g in EXCLUDE_GLOBS):
        return False
    if any(name.endswith(s) for s in EXCLUDE_SUFFIXES):
        return False
    if _is_sensitive(name):
        return False   # keep out of tree/read; flag separately
    try:
        if item.stat().st_size > MAX_FILE_BYTES:
            return False
    except OSError:
        return False
    return True

URL_RE = re.compile(
    r'https?://'
    r'(?:www\.)?'
    r'(?:github\.com|gitlab\.com|bitbucket\.org)'
    r'/[^\s]+',
    re.IGNORECASE,
)

def parse_user_message(text: str) -> tuple[str, str]:
    matches = URL_RE.findall(text)
    if not matches:
        raise ValueError("No repo URL found in message")
    if len(matches) > 1:
        raise ValueError(f"Multiple URLs found: {matches}")

    url = matches[0].rstrip('.,;:!?)]}"')
    query = text.replace(url, ' ').strip()
    query = re.sub(r'\s+', ' ', query)
    return url, query


def clone_repo(repo_url: str, dest: str = "./tmp") -> str:

    url = repo_url.strip().rstrip("/").removesuffix(".git")
    if "github.com/" not in url:
        raise ValueError("Only github.com URLs are supported")
    owner, repo = url.split("github.com/")[1].split("/")[:2]

    zip_url = f"https://github.com/{owner}/{repo}/archive/HEAD.zip"

    req = urllib.request.Request(zip_url, headers={"User-Agent": "Mozilla/5.0"})
    data = urllib.request.urlopen(req).read()

    os.makedirs(dest, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        z.extractall(dest)

    return dest


def get_directory_tree(directory, max_depth: int = 4) -> str:
    directory = Path(directory)

    def build_tree(path: Path, prefix: str = "", depth: int = 0) -> list[str]:
        if depth >= max_depth:
            return []

        items = sorted(
            (i for i in path.iterdir() if _is_visible(i)),
            key=lambda x: (x.is_file(), x.name.lower()),
        )

        tree = []
        for index, item in enumerate(items):
            is_last = index == len(items) - 1
            connector = "`-- " if is_last else "|-- "

            tree.append(prefix + connector + item.name)

            if item.is_dir():
                extension = "    " if is_last else "|   "
                tree.extend(build_tree(item, prefix + extension, depth + 1))

        return tree

    tree = [directory.name]
    tree.extend(build_tree(directory))
    return "\n".join(tree)


def get_file_list(directory) -> list[str]:
    root = Path(directory)
    files = []

    for p in root.rglob("*"):
        if not p.is_file():
            continue

        rel = p.relative_to(root)

        # skip excluded directories anywhere in the path
        if any(part in EXCLUDE_DIRS for part in rel.parts):
            continue

        if _is_visible(p):
            files.append(str(rel).replace("\\", "/"))

    return sorted(files)