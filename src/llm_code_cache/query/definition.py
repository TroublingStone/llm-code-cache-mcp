from llm_code_cache.graph import GraphDefinitionRecord
from llm_code_cache.query.models import DefinitionResult
from llm_code_cache.query.stores import GraphStoreProtocol


def find_definition(graph: GraphStoreProtocol, qualified_name: str) -> DefinitionResult | None:
    record = graph.get_definition(qualified_name)
    if record is None:
        return None
    return _to_definition_result(record)


def _to_definition_result(record: GraphDefinitionRecord) -> DefinitionResult:
    return DefinitionResult(
        qualified_name=record.qualified_name,
        name=record.name,
        kind=record.kind,
        file_path=record.file_path,
        start_line=record.start_line,
        end_line=record.end_line,
        source=record.source,
        docstring=record.docstring,
        parent_class=record.parent_class,
        decorators=record.decorators,
    )
