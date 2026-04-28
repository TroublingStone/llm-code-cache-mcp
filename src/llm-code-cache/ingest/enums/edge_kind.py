from enum import Enum


class EdgeKind(str, Enum):
    CALLS = "calls"
    IMPORTS = "imports"
    DEFINED_IN = "defined_in"
    INHERITS_FROM = "inherits_from"
