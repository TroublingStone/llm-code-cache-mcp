UNWIND $nodes AS node
MERGE (n:__LABEL__ {qualified_name: node.qualified_name})
SET n += node.props
