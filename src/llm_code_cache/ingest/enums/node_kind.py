from enum import StrEnum


class NodeKind(StrEnum):
    FILE = "file"
    FUNCTION = "function"
    METHOD = "method"
    CLASS = "class"
