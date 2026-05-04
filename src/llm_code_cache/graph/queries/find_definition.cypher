MATCH (n {qualified_name: $qn})
WHERE NOT n:Unresolved
OPTIONAL MATCH (n)-[:DEFINED_IN]->(f:File)
RETURN n, labels(n) AS labels, f
LIMIT 1
