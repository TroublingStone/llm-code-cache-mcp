UNWIND $edges AS edge
MATCH (a {qualified_name: edge.source})
MATCH (b {qualified_name: edge.target})
MERGE (a)-[r:__REL_TYPE__]->(b)
