from enum import StrEnum


class NodeProperty(StrEnum):
    QUALIFIED_NAME = "qualified_name"
    NAME           = "name"
    DOCSTRING      = "docstring"
    PARENT_CLASS   = "parent_class"
    DECORATORS     = "decorators"
    PATH           = "path"
    START_LINE     = "start_line"
    END_LINE       = "end_line"
    SOURCE         = "source"
    TEXT_REF       = "text_ref"
