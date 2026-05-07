from pathlib import Path

from llm_code_cache.ingest.walker import walk_repo


def _touch(root: Path, rel: str, content: str = "") -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def test_walk_repo_returns_only_python_files(tmp_path: Path) -> None:
    _touch(tmp_path, "a.py")
    _touch(tmp_path, "b.txt")
    _touch(tmp_path, "sub/c.py")
    _touch(tmp_path, "sub/d.md")

    found = {p.relative_to(tmp_path).as_posix() for p in walk_repo(tmp_path)}

    assert found == {"a.py", "sub/c.py"}


def test_walk_repo_excludes_built_in_dirs(tmp_path: Path) -> None:
    _touch(tmp_path, "keep.py")
    _touch(tmp_path, ".git/hidden.py")
    _touch(tmp_path, "__pycache__/cached.py")
    _touch(tmp_path, ".venv/lib/site-packages/pkg/mod.py")
    _touch(tmp_path, "node_modules/pkg/index.py")
    _touch(tmp_path, ".mypy_cache/x.py")

    found = {p.relative_to(tmp_path).as_posix() for p in walk_repo(tmp_path)}

    assert found == {"keep.py"}


def test_walk_repo_honors_gitignore(tmp_path: Path) -> None:
    _touch(tmp_path, ".gitignore", "build/\nignored.py\n")
    _touch(tmp_path, "keep.py")
    _touch(tmp_path, "ignored.py")
    _touch(tmp_path, "build/artifact.py")
    _touch(tmp_path, "build/sub/nested.py")

    found = {p.relative_to(tmp_path).as_posix() for p in walk_repo(tmp_path)}

    assert found == {"keep.py"}


def test_walk_repo_returns_empty_for_empty_tree(tmp_path: Path) -> None:
    assert walk_repo(tmp_path) == []


def test_walk_repo_returns_empty_when_no_python_files(tmp_path: Path) -> None:
    _touch(tmp_path, "readme.md")
    _touch(tmp_path, "data/sample.json", "{}")

    assert walk_repo(tmp_path) == []
