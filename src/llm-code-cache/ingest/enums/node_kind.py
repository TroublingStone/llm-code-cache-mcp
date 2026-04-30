from enum import Enum


class NodeKind(str, Enum):
    FILE = "file"
    FUNCTION = "function"
    METHOD = "method"
    CLASS = "class"
