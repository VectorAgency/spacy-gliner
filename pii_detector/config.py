"""
Configuration for PII detection and anonymization
"""

# Entity types detected by GLiNER
DEFAULT_LABELS = [
    "person",
    "organization", 
    "location",
    "country",
    "email",
    "phone_number",
    "birthdate",
    "address"
]

# Map internal labels to custom anonymization placeholders
LABEL_MAPPING = {
    "person": "NAME",
    "organization": "COMPANY",
    "location": "PLACE",
    "country": "COUNTRY",
    "email": "EMAIL",
    "phone_number": "PHONE",
    "birthdate": "DOB",
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
DEFAULT_PLACEHOLDER_FORMAT = "brackets"

# Processing parameters
DEFAULT_CHUNK_SIZE = 1400
DEFAULT_OVERLAP = 200
DEFAULT_THRESHOLD = 0.3