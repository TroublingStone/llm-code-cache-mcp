from enum import Enum


class TSNodeType(str, Enum):
    FUNCTION_DEF    = "function_definition"
    CLASS_DEF       = "class_definition"
    DECORATED_DEF   = "decorated_definition"
    IMPORT          = "import_statement"
    IMPORT_FROM     = "import_from_statement"
    DECORATOR       = "decorator"
    CALL            = "call"
    DOTTED_NAME     = "dotted_name"
    ALIASED_IMPORT  = "aliased_import"
    IDENTIFIER      = "identifier"
    ATTRIBUTE       = "attribute"
    EXPRESSION_STMT = "expression_statement"
    STRING          = "string"
