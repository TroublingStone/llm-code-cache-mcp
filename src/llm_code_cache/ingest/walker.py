from pathlib import Path

import pathspec

PY_SUFFIX = ".py"
EXCLUDED_DIR_NAMES: frozenset[str] = frozenset({
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
})

# TODO(v1): nested .gitignore handling, symlink loop protection,
# robust binary-file detection beyond extension.


def walk_repo(repo_root: Path) -> list[Path]:
    """Return all Python files under repo_root, honoring .gitignore and built-in excludes."""
    spec = _load_gitignore(repo_root)
    matches: list[Path] = []
    for path in repo_root.rglob("*"):
        if not path.is_file() or path.suffix != PY_SUFFIX:
            continue
        rel = path.relative_to(repo_root)
        if _is_excluded_dir(rel) or _is_gitignored(spec, rel):
            continue
        matches.append(path)
    return matches


def _load_gitignore(repo_root: Path) -> pathspec.PathSpec | None:
    gitignore = repo_root / ".gitignore"
    if not gitignore.is_file():
        return None
    return pathspec.PathSpec.from_lines("gitignore", gitignore.read_text().splitlines())


def _is_excluded_dir(rel: Path) -> bool:
    return any(part in EXCLUDED_DIR_NAMES for part in rel.parts)


def _is_gitignored(spec: pathspec.PathSpec | None, rel: Path) -> bool:
    return spec is not None and spec.match_file(rel.as_posix())
