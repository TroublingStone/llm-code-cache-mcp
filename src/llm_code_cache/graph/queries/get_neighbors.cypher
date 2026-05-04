MATCH (start {{qualified_name: $qn}})
            MATCH (start){arrow_left}[r:{rel_types}{depth_clause}]{arrow_right}(neighbor)
            OPTIONAL MATCH (neighbor)-[:DEFINED_IN]->(f:File)
            RETURN
                DISTINCT neighbor,
                labels(neighbor) AS labels,
                type(r) AS edge_type,
                f