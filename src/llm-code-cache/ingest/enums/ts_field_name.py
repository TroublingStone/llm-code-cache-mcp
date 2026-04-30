from enum import Enum


class TSFieldName(str, Enum):
    NAME         = "name"
    BODY         = "body"
    FUNCTION     = "function"
    SUPERCLASSES = "superclasses"
    MODULE_NAME  = "module_name"
