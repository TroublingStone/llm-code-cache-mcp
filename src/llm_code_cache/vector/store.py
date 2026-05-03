import logging
from llama_index.vector_stores.postgres import PGVectorStore


logger = logging.getLogger(__name__)

class VectorStore:
    def __init__(self, config, embed_dim) -> None:
        self._config = config
        self._embed_dim = embed_dim
        self._inner_store: PGVectorStore | None = None

    def connect(self) -> None:
        """Initialize the pgvector connection and ensure the table exists."""
        self._inner = PGVectorStore.from_params(
            database=self._config.database,
            host=self._config.host,
            port=self._config.port,
            user=self._config.user,
            password=self._config.password,
            table_name=self._config.table_name,
            embed_dim=self._embed_dim,
        )
        logger.info(
            "vector store connected: table=%s embed_dim=%d",
            self._config.table_name,
            self._embed_dim,
        )
    
    @property
    def inner(self) -> PGVectorStore:
        if self._inner is None:
            raise RuntimeError("VectorStore.connect() must be called first")
        return self._inner