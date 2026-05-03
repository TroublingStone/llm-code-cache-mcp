CREATE INDEX file_repo_idx IF NOT EXISTS FOR (n:File) ON (n.repo);

CREATE INDEX function_repo_idx IF NOT EXISTS FOR (n:Function) ON (n.repo);

CREATE INDEX method_repo_idx IF NOT EXISTS FOR (n:Method) ON (n.repo);

CREATE INDEX class_repo_idx IF NOT EXISTS FOR (n:Class) ON (n.repo);
