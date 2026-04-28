from enum import Enum


class NodeKind(str, Enum):
    FUNCTION = "function"
    METHOD = "method"
    CLASS = "class"
