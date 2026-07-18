from enum import Enum


class Phase(str, Enum):
    QUEUED = "Queued"
    VALIDATING = "Validating"
    SEARCHING = "Searching"
    WRITING_REPORT = "WritingReport"
    DONE = "Done"
    REJECTED = "Rejected"
