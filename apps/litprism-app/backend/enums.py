from enum import StrEnum


class ReviewType(StrEnum):
    SYSTEMATIC = "systematic"
    SCOPING = "scoping"
    RAPID = "rapid"
    LITERATURE = "literature"
    STATE_OF_ART = "state_of_art"
