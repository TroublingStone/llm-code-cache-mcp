from llm_code_cache.ingest.enums.node_kind import NodeKind
from llm_code_cache.ingest.enums.ts_node_type import TSNodeType

TS_DEFINITION_TYPES = frozenset({TSNodeType.FUNCTION_DEF, TSNodeType.CLASS_DEF})
EMBEDDABLE_KINDS = {NodeKind.FUNCTION, NodeKind.METHOD, NodeKind.CLASS}

MAX_EMBED_TOKENS       = 1500
TOKEN_ESTIMATE_DIVISOR = 3
SOURCE_ENCODING        = "utf-8"
