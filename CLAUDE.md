# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Environment Setup
```bash
conda env create -f environment.yml
conda activate spacy-gliner
```

### Running PII Extraction
```bash
# Standard spaCy JSON output
python extract_pii.py --filter

# Anonymize with basic placeholders
python extract_pii.py --anonymize --filter

# Anonymize with entity resolution (groups "Anna" and "Anna Meier")
python extract_pii.py --anonymize --filter --resolve-entities
```

### Python API Usage
```python
from pii_detector import create_pipeline, anonymize_doc

# Create pipeline
nlp = create_pipeline(language="de", filter_false_positives=True)

# Process text
doc = nlp(text)
print(f"Found {len(doc.ents)} entities")

# Anonymize with entity resolution
anonymized_text, mapping = anonymize_doc(doc, resolve_entities=True)
```

### Installing Dependencies
```bash
pip install gliner spacy torch transformers huggingface-hub tabulate
```

## Architecture

Modular spaCy pipeline with GLiNER integration for PII detection and anonymization:

### Project Structure
```
pii_detector/           # Main package
├── detector.py         # SpaCy component & GLiNER integration  
├── anonymizer.py       # Anonymization & entity resolution
├── fuzzy_matcher.py    # Fuzzy matching for entity variations
├── config.py          # Configuration & label mappings
└── utils.py           # Shared utilities (model loading, chunking)

data/                  # Data files
├── false_positives.json
├── text.txt
└── gold_dataset.json

extract_pii.py         # CLI wrapper
```

### Key Features

1. **Entity Resolution**: Smart coreference resolution groups "Anna" and "Anna Meier" as same entity

2. **Fuzzy Matching**: Catches ALL variations including possessive forms ("Annas"), case variations, and missed occurrences

3. **spaCy Integration**: GLiNER runs transparently as `pii_detector` component

4. **Entity Detection**: Extracts 8 PII types: person, organization, location, country, email, phone_number, birthdate, address

5. **Anonymization Modes**:
   - Basic: Sequential IDs (`[PERSON_0]`, `[PERSON_1]`)
   - With resolution: Same ID for coreferent entities
   - With fuzzy matching: Comprehensive replacement of ALL variations

6. **Output Formats**:
   - Standard spaCy JSON (`doc.to_json()`)
   - Anonymized text with entity mappings

7. **False Positive Filtering**: Optional filtering using `data/false_positives.json`

## Key Implementation Details

### Entity Resolution & Fuzzy Matching

#### How Labels Are Created (anonymizer.py + fuzzy_matcher.py)
```python
# Phase 1 - GLiNER Detection:
1. GLiNER detects: person, organization, location, etc.
2. Transform: person → PERSON (uppercase)
3. Add ID: PERSON_0, PERSON_1, etc.
4. Format: [PERSON_0] (customizable)

# Phase 2 - Entity Resolution:
1. Exact match: "Anna" == "Anna" → same ID
2. Subset match: "Anna" ⊂ "Anna Meier" → same ID (persons only)
3. Result: All detected "Anna" mentions → [PERSON_0]

# Phase 3 - Fuzzy Matching (NEW):
1. For each unique entity, find ALL variations in text
2. Possessive forms: "Annas" → matches "Anna" 
3. Case variations: "anna", "ANNA" → matches "Anna"
4. Missed occurrences: Catches entities GLiNER didn't detect
5. Result: COMPREHENSIVE replacement of all variations
```

#### Customization Options (config.py)
```python
# Change label names
LABEL_MAPPING = {
    "person": "NAME",
    "organization": "COMPANY"
}

# Change placeholder format
PLACEHOLDER_FORMATS = {
    "brackets": "[{label}_{id}]",      # [NAME_0]
    "angles": "<<{label}#{id}>>",      # <<NAME#0>>
    "custom": "***{label}_{id}***"     # ***NAME_0***
}
```

### Component Responsibilities
- **detector.py**: spaCy component, chunking, GLiNER integration, confidence scores
- **anonymizer.py**: Entity resolution, placeholder generation, fuzzy matching integration
- **fuzzy_matcher.py**: Pattern matching for possessive forms, case variations, missed occurrences
- **config.py**: Label mappings, placeholder formats, configuration constants
- **utils.py**: Model caching, text chunking, deduplication

### Configuration
- Default threshold: 0.3 (adjustable via --threshold)
- Chunk size: 1400 chars with 200 char overlap
- Deduplication: Removes entities within 10 chars of each other
- Model: GLiNER multi_pii-v1 (~500MB, cached locally)