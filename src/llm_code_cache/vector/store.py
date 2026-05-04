import logging
from dataclasses import asdict

from llama_index.core import VectorStoreIndex
from llama_index.core.embeddings import BaseEmbedding
from llama_index.core.retrievers import BaseRetriever
from llama_index.core.schema import TextNode
from llama_index.vector_stores.postgres import PGVectorStore

from llm_code_cache.ingest.models import Chunk, Metadata
from llm_code_cache.vector.models import VectorHit

logger = logging.getLogger(__name__)

class VectorStore:
    def __init__(self, config, embed_dim: int, embed_model: BaseEmbedding) -> None:
        self._config = config
        self._embed_dim = embed_dim
        self._embed_model = embed_model
        self._connection: PGVectorStore | None = None
        self._index: VectorStoreIndex | None = None
        self._retriever: BaseRetriever | None = None
        self._retriever_top_k: int | None = None

    def connect(self) -> None:
        """Initialize the pgvector connection and ensure the table exists."""
        self._connection = PGVectorStore.from_params(
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
    def connection(self) -> PGVectorStore:
        if self._connection is None:
            raise RuntimeError("VectorStore.connect() must be called first")
        return self._connection

    @property
    def index(self) -> VectorStoreIndex:
        if self._index is None:
            self._index = VectorStoreIndex.from_vector_store(
                self.connection, embed_model=self._embed_model
            )
        return self._index

    def _get_retriever(self, top_k: int) -> BaseRetriever:
        if self._retriever is None or self._retriever_top_k != top_k:
            self._retriever = self.index.as_retriever(similarity_top_k=top_k)
            self._retriever_top_k = top_k
        return self._retriever

    def search(self, query: str, top_k: int = 5) -> list[VectorHit]:
        nodes = self._get_retriever(top_k).retrieve(query)
        return [VectorHit.from_node(node) for node in nodes]

    def upsert_chunks(self, chunks: list[Chunk]) -> None:
        if not chunks:
            return
        nodes = [self._chunk_to_text_node(c) for c in chunks]
        self.index.insert_nodes(nodes)
        logger.info("upserted %d chunks", len(nodes))

    def _chunk_to_text_node(self, chunk: Chunk) -> TextNode:
        return TextNode(
            text=chunk.embed_text,
            metadata=self._serialize_metadata(chunk.metadata),
            id_=chunk.metadata.qualified_name,
        )

    def _serialize_metadata(self, metadata: Metadata) -> dict:
        return asdict(metadata)
