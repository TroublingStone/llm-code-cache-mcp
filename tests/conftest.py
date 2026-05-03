import pytest

from llm_code_cache.ingest.enums.node_kind import NodeKind
from llm_code_cache.ingest.models import Chunk, Metadata


@pytest.fixture
def sample_chunks() -> list[Chunk]:
    return [
        Chunk(
            embed_text=(
                "def authenticate(token: str) -> bool:\n"
                '    """Validate a JWT token."""\n'
                "    return verify_signature(token)"
            ),
            metadata=Metadata(
                repo="myrepo",
                path="src/auth.py",
                qualified_name="myrepo.src.auth.authenticate",
                name="authenticate",
                kind=NodeKind.FUNCTION,
                start_line=10,
                end_line=13,
            ),
        ),
        Chunk(
            embed_text=(
                "class UserRepository:\n"
                '    """Handles DB access for user records."""\n'
                "    def find_by_id(self, user_id: int): ..."
            ),
            metadata=Metadata(
                repo="myrepo",
                path="src/repo.py",
                qualified_name="myrepo.src.repo.UserRepository",
                name="UserRepository",
                kind=NodeKind.CLASS,
                start_line=1,
                end_line=5,
            ),
        ),
        Chunk(
            embed_text=(
                "def compute_hash(data: bytes) -> str:\n"
                '    """Return SHA-256 hex digest."""\n'
                "    import hashlib\n"
                "    return hashlib.sha256(data).hexdigest()"
            ),
            metadata=Metadata(
                repo="myrepo",
                path="src/utils.py",
                qualified_name="myrepo.src.utils.compute_hash",
                name="compute_hash",
                kind=NodeKind.FUNCTION,
                start_line=1,
                end_line=4,
            ),
        ),
    ]
