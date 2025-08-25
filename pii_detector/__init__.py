"""
PII Detector - SpaCy pipeline for PII detection and anonymization
"""

from .detector import PiiDetector, create_pipeline
from .anonymizer import anonymize_doc, EntityResolver, create_anonymizer
from .utils import DEFAULT_LABELS, DEFAULT_THRESHOLD

__version__ = "0.1.0"

__all__ = [
    "PiiDetector",
    "create_pipeline",
    "anonymize_doc", 
    "EntityResolver",
    "create_anonymizer",
    "DEFAULT_LABELS",
    "DEFAULT_THRESHOLD"
]