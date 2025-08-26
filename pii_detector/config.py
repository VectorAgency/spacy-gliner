"""
Configuration for PII detection and anonymization
"""

# GLiNER Model Configuration
# You can use any GLiNER model from HuggingFace here
# Examples:
# - "urchade/gliner_multi_pii-v1" (default, multilingual PII)
# - "urchade/gliner_large-v2.1" (general purpose, more entity types)
# - "urchade/gliner_medium-v2.1" (faster, smaller)
# - "urchade/gliner_small-v2.1" (fastest, least accurate)
GLINER_MODEL_NAME = "urchade/gliner_multi_pii-v1"

# Entity types detected by GLiNER
DEFAULT_LABELS = [
    "person",
    "organization_name", 
    "location",
    "country",
    "email",
    "phone_number",
    "birthdate",
    "medical_diagnosis",
    "address"
]

# Map internal labels to custom anonymization placeholders
LABEL_MAPPING = {
    "person": "PERSON",
    "organization": "COMPANY",
    "location": "PLACE",
    "country": "COUNTRY",
    "email": "EMAIL",
    "phone_number": "PHONE",
    "birthdate": "BIRTHDATE",
    "medical_diagnosis": "MEDICAL_DIAGNOSIS",
    "address": "ADDRESS"
}

# Placeholder formats (can customize)
PLACEHOLDER_FORMATS = {
    "brackets": "[{label}_{id}]",        # [PERSON_0]
    "angles": "<{label}_{id}>",          # <PERSON_0>
    "double_angles": "<<{label}#{id}>>", # <<PERSON#0>>
    "curly": "{{{label}_{id}}}",         # {PERSON_0}
    "custom": "***{label}_{id}***"       # ***PERSON_0***
}

# Default format to use
DEFAULT_PLACEHOLDER_FORMAT = "custom"

# Processing parameters
DEFAULT_CHUNK_SIZE = 1400
DEFAULT_OVERLAP = 200
DEFAULT_THRESHOLD = 0.3