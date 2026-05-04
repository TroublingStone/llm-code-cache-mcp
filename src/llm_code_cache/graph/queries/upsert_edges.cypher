UNWIND $edges AS edge
MATCH (a {qualified_name: edge.source})
OPTIONAL MATCH (real {qualified_name: edge.target})
WHERE NOT real:Unresolved
WITH edge, a, real
CALL {
  WITH edge, real
  WITH edge, real WHERE real IS NULL
  MERGE (stub:Unresolved {text_ref: edge.target})
  RETURN stub
  UNION
  WITH edge, real
  WITH edge, real WHERE real IS NOT NULL
  RETURN real AS stub
}
MERGE (a)-[r:__REL_TYPE__]->(stub)
