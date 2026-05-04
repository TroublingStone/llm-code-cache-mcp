// TODO(v1): cross-repo schema lands here (DESIGN.md Open Questions).
// Node has no repo field today, so this query is effectively a no-op.
MATCH (n {repo: $repo}) DETACH DELETE n
