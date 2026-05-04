CREATE CONSTRAINT file_qn_unique IF NOT EXISTS
FOR (n:File) REQUIRE n.qualified_name IS UNIQUE;

CREATE CONSTRAINT function_qn_unique IF NOT EXISTS
FOR (n:Function) REQUIRE n.qualified_name IS UNIQUE;

CREATE CONSTRAINT method_qn_unique IF NOT EXISTS
FOR (n:Method) REQUIRE n.qualified_name IS UNIQUE;

CREATE CONSTRAINT class_qn_unique IF NOT EXISTS
FOR (n:Class) REQUIRE n.qualified_name IS UNIQUE;

CREATE CONSTRAINT unresolved_qn_unique IF NOT EXISTS
FOR (n:Unresolved) REQUIRE n.qualified_name IS UNIQUE;
