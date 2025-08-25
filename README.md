# spacy-gliner

A modular spaCy pipeline for PII detection and anonymization using GLiNER's state-of-the-art entity recognition model. Features smart entity resolution with fuzzy matching to catch all entity variations, including possessive forms and missed occurrences.

## Features

- 🔍 **Multilingual PII Detection**: Optimized for German text, supports multiple languages
- 🤖 **spaCy Integration**: Runs as native spaCy component in standard NLP pipelines
- 🔗 **Entity Resolution**: Smart coreference resolution (links "Anna" with "Anna Meier")
- 🎨 **Fuzzy Matching**: Catches ALL entity variations including possessive forms ("Annas")
- 🔒 **Document Anonymization**: Replace PII with placeholders like `[PERSON_0]`
- 🚀 **Efficient Processing**: Chunks large documents to avoid truncation
- 🎯 **Configurable Filtering**: Remove false positives with customizable filter lists
- 💾 **Model Caching**: Uses HuggingFace's built-in caching for reliability
- 📊 **Multiple Output Formats**: spaCy JSON, dual output (anonymized text + metadata JSON)

## Installation

### Option 1: Conda environment (recommended)

```bash
conda env create -f environment.yml
conda activate spacy-gliner
```

### Option 2: pip install

```bash
pip install -r requirements.txt
```

## Usage

### Basic extraction (spaCy JSON output)
```bash
python extract_pii.py --filter
```

### Anonymize document with entity resolution
```bash
python extract_pii.py --anonymize --filter --resolve-entities
```
This intelligently groups entities: "Anna" and "Anna Meier" → `[PERSON_0]`

### Save output to file
```bash
python extract_pii.py --anonymize --filter --resolve-entities --output results
```
Creates two files:
- `results.txt`: Clean anonymized text
- `results_meta.json`: Comprehensive metadata (15 categories of information)


### Python API usage
```python
from pii_detector import create_pipeline, anonymize_doc

# Create pipeline
nlp = create_pipeline(language="de", filter_false_positives=True)

# Process text
doc = nlp(text)

# Basic anonymization
anonymized_text, mapping, metadata = anonymize_doc(doc, resolve_entities=True, return_metadata=True)

# Custom label mapping (person → NAME, organization → COMPANY)
label_mapping = {
    "person": "NAME",
    "organization": "COMPANY",
    "location": "PLACE"
}
anonymized_text, mapping, metadata = anonymize_doc(
    doc, 
    label_mapping=label_mapping,
    placeholder_format="<<{label}#{id}>>",  # → <<NAME#0>>
    return_metadata=True
)
```

## Command-line Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--input` | data/text.txt | Input text file |
| `--output` | stdout | Output file |
| `--threshold` | 0.3 | Confidence threshold (0.0-1.0) |
| `--filter` | False | Apply false positive filtering |
| `--filter-file` | data/false_positives.json | JSON file with false positives |
| `--anonymize` | False | Output anonymized text with placeholders |
| `--resolve-entities` | False | Resolve coreferences when anonymizing |
| `--language` | de | Language code (de, en, etc.) |
| `--placeholder-format` | brackets | Placeholder style: brackets, angles, double_angles, curly, custom |

## Detected Entity Types

- **person**: Names of individuals
- **organization**: Companies, institutions
- **location**: Cities, regions
- **country**: Country names
- **email**: Email addresses
- **phone_number**: Phone numbers
- **birthdate**: Dates of birth
- **address**: Physical addresses

## False Positive Filtering

Edit `false_positives.json` to customize filtering (case-insensitive matching):

```json
{
  "person": [
    "Mutter",  // Generic family terms
    "Eltern",
    "Patient"  // Generic roles
  ],
  "organization": [
    "Schule",  // Generic institutions
    "Krankenhaus"
  ]
}
```

Note: Filtering is now case-insensitive, so "Mutter", "mutter", and "MUTTER" will all be filtered.

## Output Formats

### 1. Standard spaCy JSON
```json
{
  "text": "...",
  "ents": [
    {"start": 44, "end": 54, "label": "person"}
  ],
  "sents": [{"start": 0, "end": 24}],
  "tokens": [...]
}
```

### 2. Anonymized Output (dual file format)

**File 1: anonymized.txt**
```
Name der Patientin: [PERSON_0]
[PERSON_0] ist 15 Jahre alt...
```

**File 2: anonymized_meta.json**
```json
{
  "entity_mapping": {
    "[PERSON_0]": {"text": "Anna Meier", "score": 0.95},
    "[PERSON_1]": {"text": "Dr. med. Marco Weber", "score": 0.98}
  },
  "clustering": [...],
  "fuzzy_matches": [...],
  "confidence_stats": {...},
  "statistics": {
    "total_entities": 41,
    "processing_time_seconds": 1.23
  },
  // ... 10 more metadata categories
}
```


## Project Structure

| Directory/File | Description |
|------|-------------|
| `pii_detector/` | Main package with modular components |
| `├── detector.py` | spaCy component with GLiNER integration |
| `├── anonymizer.py` | Anonymization and entity resolution |
| `├── fuzzy_matcher.py` | Fuzzy matching for entity variations |
| `├── config.py` | Configuration and label mappings |
| `└── utils.py` | Shared utilities and model loading |
| `data/` | Data files directory |
| `├── false_positives.json` | List of terms to filter out |
| `├── gold_dataset.json` | Reference dataset of known PII entities |
| `└── text.txt` | Sample input text (German psychological report) |
| `extract_pii.py` | CLI script |
| `environment.yml` | Conda environment configuration |

## Performance

- Processes ~1200 characters per chunk to stay within model limits
- F1 score: ~0.75 on German psychological reports
- Recall: ~70-80% for core PII entities
- Precision: High with filtering enabled

## Technical Details

### How Anonymization Labels Work

The labels like `[PERSON_0]` are created through this process:

1. **GLiNER Detection**: Detects entities with labels: person, organization, location, etc.
2. **Label Transformation**: `person` → `PERSON` (uppercase)
3. **ID Assignment**: 
   - Without resolution: Sequential (`[PERSON_0]`, `[PERSON_1]`, `[PERSON_2]`)
   - With resolution: Same ID for coreferent entities (all "Anna" → `[PERSON_0]`)
4. **Placeholder Format**: Default `[{label}_{id}]` but customizable

### Customizing Labels

You can customize labels in multiple ways:

```python
# 1. Change label names (config.py or via API)
label_mapping = {
    "person": "NAME",
    "organization": "COMPANY",
    "email": "CONTACT_EMAIL"
}

# 2. Change placeholder format
placeholder_format = "<<{label}#{id}>>"      # <<NAME#0>>
placeholder_format = "{{{label}_{id}}}"       # {NAME_0}
placeholder_format = "***{label}_{id}***"     # ***NAME_0***

# 3. Add new entity types (in utils.py)
DEFAULT_LABELS = ["person", "organization", "location", "ssn", "credit_card"]
```

### Entity Resolution & Fuzzy Matching
The anonymizer uses three-phase matching for comprehensive coverage:

**Phase 1: Entity Resolution** (groups related entities)
- **Exact match**: "Anna" == "Anna" → same entity
- **Subset matching**: "Anna" ⊂ "Anna Meier" → same entity  
- **Similarity threshold**: Uses Jaccard similarity (default 0.8) for merging decisions
- **Works for person names only** (avoids false matches for organizations)
- **Deterministic clustering**: Entities grouped by first appearance position

**Phase 2: Direct Replacement** (replaces detected spans)
- **Span-based identity**: Uses (start_char, end_char, label) to avoid collisions
- **Right-to-left replacement**: Ensures correct positioning

**Phase 3: Fuzzy Matching** (catches ALL variations)
- **Possessive forms**: "Annas" (German genitive) → matches "Anna"
- **Case variations**: "anna", "ANNA" → matches "Anna"
- **Typo detection**: Uses SequenceMatcher for similarity scoring (threshold: 0.85)
- **Missed occurrences**: Finds entities GLiNER didn't detect
- **Word boundaries**: Respects word boundaries to avoid false matches
- **Placeholder safety**: Avoids replacing inside already-replaced regions

### Processing Pipeline
1. Text is chunked (1400 chars with 200 char overlap)
2. GLiNER extracts entities from each chunk with confidence scores
3. Duplicates removed with O(n) algorithm based on position proximity
4. Optional case-insensitive false positive filtering applied
5. Entities converted to spaCy spans using built-in `char_span()` method
6. Optional entity resolution groups coreferent mentions
7. Fuzzy matching finds and replaces all variations

### Notes
- **First run downloads the model (~500MB)**, cached by HuggingFace in `~/.cache/huggingface/`
- No manual pickle caching - uses HuggingFace's robust caching mechanism
- Works best with **English entity labels** (model training language)
- German text is fully supported for extraction
- All confidence scores preserved from GLiNER output

## License

This tool uses the GLiNER model (Apache 2.0 License)