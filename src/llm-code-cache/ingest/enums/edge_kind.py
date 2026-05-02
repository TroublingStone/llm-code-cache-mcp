from enum import StrEnum


class EdgeKind(StrEnum):
    CALLS = "calls"
    IMPORTS = "imports"
    DEFINED_IN = "defined_in"
    INHERITS_FROM = "inherits_from"
    DECORATED_BY = "decorated_by"
