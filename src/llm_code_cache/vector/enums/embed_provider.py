from enum import StrEnum


class EmbedProvider(StrEnum):
    HUGGINGFACE = "huggingface"
    BEDROCK    = "bedrock"
