MATCH (start {{qualified_name: $qn}})
MATCH path = (start){arrow_left}[:{rel_types}{depth_clause}]{arrow_right}(neighbor)
WHERE neighbor <> start
WITH neighbor, relationships(path) AS rels
OPTIONAL MATCH (neighbor)-[:DEFINED_IN]->(f:File)
RETURN
    DISTINCT neighbor,
    labels(neighbor) AS labels,
    type(last(rels)) AS edge_type,
    f
