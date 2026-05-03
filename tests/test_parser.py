from pathlib import Path
from unittest.mock import patch

import pytest

from llm_code_cache.ingest.enums.edge_kind import EdgeKind
from llm_code_cache.ingest.enums.node_kind import NodeKind
from llm_code_cache.ingest.parser import make_ts_parser, parse_file, parse_repo, qualified_name


def nodes_by_kind(result, kind):
    return [n for n in result.nodes if n.kind == kind]


def edges_by_kind(result, kind):
    return [e for e in result.edges if e.kind == kind]


@pytest.fixture
def repo(tmp_path):
    """Return (repo_root, write) where write(name, src) -> Path."""
    def write(name: str, src: str) -> Path:
        p = tmp_path / name
        p.write_text(src, encoding="utf-8")
        return p
    return tmp_path, write


@pytest.fixture
def ts_parser():
    return make_ts_parser()


def test_empty_file(repo, ts_parser):
    root, write = repo
    path = write("mod.py", "")
    result = parse_file(path, root, ts_parser)

    assert len(result.nodes) == 1
    assert result.nodes[0].kind == NodeKind.FILE
    assert result.edges == []


def test_bare_function(repo, ts_parser):
    root, write = repo
    path = write("mod.py", "def greet(name): pass\n")
    result = parse_file(path, root, ts_parser)

    fns = nodes_by_kind(result, NodeKind.FUNCTION)
    assert len(fns) == 1
    assert fns[0].name == "greet"

    defined_in = edges_by_kind(result, EdgeKind.DEFINED_IN)
    assert any(e.source == fns[0].qualified_name for e in defined_in)


def test_function_with_docstring(repo, ts_parser):
    root, write = repo
    src = 'def greet(name):\n    """Say hello."""\n    pass\n'
    path = write("mod.py", src)
    result = parse_file(path, root, ts_parser)

    fn = nodes_by_kind(result, NodeKind.FUNCTION)[0]
    assert fn.docstring is not None
    assert "Say hello" in fn.docstring


def test_function_calls(repo, ts_parser):
    root, write = repo
    src = "def greet(name):\n    print(name)\n"
    path = write("mod.py", src)
    result = parse_file(path, root, ts_parser)

    fn = nodes_by_kind(result, NodeKind.FUNCTION)[0]
    calls = edges_by_kind(result, EdgeKind.CALLS)
    assert any(e.source == fn.qualified_name and e.target == "print" for e in calls)


def test_class_with_inheritance(repo, ts_parser):
    root, write = repo
    src = "class Dog(Animal): pass\n"
    path = write("mod.py", src)
    result = parse_file(path, root, ts_parser)

    classes = nodes_by_kind(result, NodeKind.CLASS)
    assert len(classes) == 1
    assert classes[0].name == "Dog"

    inherits = edges_by_kind(result, EdgeKind.INHERITS_FROM)
    assert any(e.source == classes[0].qualified_name and e.target == "Animal" for e in inherits)


def test_class_with_method(repo, ts_parser):
    root, write = repo
    src = "class MyClass:\n    def my_method(self): pass\n"
    path = write("mod.py", src)
    result = parse_file(path, root, ts_parser)

    assert len(nodes_by_kind(result, NodeKind.FILE)) == 1
    assert len(nodes_by_kind(result, NodeKind.CLASS)) == 1
    assert len(nodes_by_kind(result, NodeKind.METHOD)) == 1

    defined_in = edges_by_kind(result, EdgeKind.DEFINED_IN)
    cls = nodes_by_kind(result, NodeKind.CLASS)[0]
    method = nodes_by_kind(result, NodeKind.METHOD)[0]
    file_node = nodes_by_kind(result, NodeKind.FILE)[0]

    assert any(e.source == method.qualified_name and e.target == cls.qualified_name for e in defined_in)
    assert any(e.source == cls.qualified_name and e.target == file_node.qualified_name for e in defined_in)


def test_method_parent_class(repo, ts_parser):
    root, write = repo
    src = "class MyClass:\n    def my_method(self): pass\n"
    path = write("mod.py", src)
    result = parse_file(path, root, ts_parser)

    method = nodes_by_kind(result, NodeKind.METHOD)[0]
    assert method.parent_class == "MyClass"
    assert method.kind == NodeKind.METHOD


def test_decorated_function(repo, ts_parser):
    root, write = repo
    src = "@staticmethod\ndef helper(): pass\n"
    path = write("mod.py", src)
    result = parse_file(path, root, ts_parser)

    fn = nodes_by_kind(result, NodeKind.FUNCTION)[0]
    dec_edges = edges_by_kind(result, EdgeKind.DECORATED_BY)
    assert any(e.source == fn.qualified_name and e.target == "staticmethod" for e in dec_edges)
    assert fn.decorators == ["staticmethod"]


def test_import(repo, ts_parser):
    root, write = repo
    path = write("mod.py", "import os\n")
    result = parse_file(path, root, ts_parser)

    file_node = nodes_by_kind(result, NodeKind.FILE)[0]
    imports = edges_by_kind(result, EdgeKind.IMPORTS)
    assert any(e.source == file_node.qualified_name and e.target == "os" for e in imports)


def test_import_from(repo, ts_parser):
    root, write = repo
    path = write("mod.py", "from pathlib import Path\n")
    result = parse_file(path, root, ts_parser)

    file_node = nodes_by_kind(result, NodeKind.FILE)[0]
    imports = edges_by_kind(result, EdgeKind.IMPORTS)
    assert any(e.source == file_node.qualified_name and e.target == "pathlib.Path" for e in imports)


def test_aliased_import(repo, ts_parser):
    root, write = repo
    path = write("mod.py", "import numpy as np\n")
    result = parse_file(path, root, ts_parser)

    file_node = nodes_by_kind(result, NodeKind.FILE)[0]
    imports = edges_by_kind(result, EdgeKind.IMPORTS)
    assert any(e.source == file_node.qualified_name and e.target == "numpy" for e in imports)


def test_qualified_name_unit(tmp_path):
    pkg = tmp_path / "pkg" / "mod.py"
    pkg.parent.mkdir()
    pkg.touch()
    result = qualified_name(pkg, tmp_path, ["MyClass", "method"])
    assert result == "pkg.mod.MyClass.method"


def test_file_node_line_count(repo, ts_parser):
    root, write = repo
    src = "x = 1\ny = 2\nz = 3"
    path = write("mod.py", src)
    result = parse_file(path, root, ts_parser)

    file_node = nodes_by_kind(result, NodeKind.FILE)[0]
    assert file_node.end_line == 3


def test_parse_repo_merges(tmp_path, ts_parser):
    a = tmp_path / "a.py"
    b = tmp_path / "b.py"
    a.write_text("def fn_a(): pass\n", encoding="utf-8")
    b.write_text("def fn_b(): pass\n", encoding="utf-8")

    result = parse_repo([a, b], tmp_path)

    assert len(nodes_by_kind(result, NodeKind.FILE)) == 2
    assert len(nodes_by_kind(result, NodeKind.FUNCTION)) == 2


def test_no_double_read(repo, ts_parser):
    root, write = repo
    path = write("mod.py", "def f(): pass\n")

    original = Path.read_bytes
    call_count = 0

    def counting_read(self):
        nonlocal call_count
        if self == path:
            call_count += 1
        return original(self)

    with patch.object(Path, "read_bytes", counting_read):
        parse_file(path, root, ts_parser)

    assert call_count == 1
