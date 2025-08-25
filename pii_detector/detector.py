"""
SpaCy component for PII detection using GLiNER
"""

from typing import List, Dict, Any
import spacy
from spacy.language import Language
from spacy.tokens import Doc, Span
from spacy.util import filter_spans

from .utils import (
    load_gliner_model,
    load_false_positives,
    chunk_text,
    deduplicate_entities,
    DEFAULT_LABELS,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_OVERLAP,
    DEFAULT_THRESHOLD
)


@Language.factory(
    "pii_detector",
    default_config={
        "labels": DEFAULT_LABELS,
        "threshold": DEFAULT_THRESHOLD,
        "chunk_size": DEFAULT_CHUNK_SIZE,
        "overlap": DEFAULT_OVERLAP,
        "filter_false_positives": False,
        "filter_file": "data/false_positives.json"
    }
)
class PiiDetector:
    """SpaCy component for PII detection"""
    
    def __init__(self, nlp, name, labels, threshold, chunk_size, overlap,
                 filter_false_positives, filter_file):
        self.nlp = nlp
        self.labels = labels
        self.threshold = threshold
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.filter_false_positives = filter_false_positives
        self.filter_file = filter_file
        self.model = load_gliner_model()
        
        # Register custom attribute for confidence scores on Span
        if not Span.has_extension("confidence"):
            Span.set_extension("confidence", default=None)
        
        # Load false positives filter
        self.false_positives = {}
        if filter_false_positives:
            self.false_positives = load_false_positives(filter_file)
    
    def __call__(self, doc: Doc) -> Doc:
        """Process a spaCy Doc"""
        text = doc.text
        
        # Extract entities with chunking
        raw_entities = self._extract_chunked(text)
        
        # Filter false positives if enabled
        if self.filter_false_positives:
            raw_entities = self._filter_entities(raw_entities)
        
        # Convert to spaCy spans
        spans = []
        for ent in raw_entities:
            # GLiNER always provides a score field - if missing, something is wrong
            if 'score' not in ent:
                raise ValueError(f"GLiNER entity missing score: {ent}")
            span = self._char_to_token_span(doc, ent['start'], ent['end'], ent['label'], ent['score'])
            if span:
                spans.append(span)
        
        # Filter overlapping spans and set as doc entities
        doc.ents = filter_spans(spans)
        
        return doc
    
    def _extract_chunked(self, text: str) -> List[Dict[str, Any]]:
        """Extract entities with chunking"""
        all_entities = []
        chunks = chunk_text(text, self.chunk_size, self.overlap)
        
        for chunk_info in chunks:
            chunk_content = chunk_info['text']
            chunk_start = chunk_info['start']
            
            # Get entities from GLiNER
            entities = self.model.predict_entities(
                chunk_content, 
                self.labels, 
                threshold=self.threshold
            )
            
            # Adjust positions to document level
            for entity in entities:
                entity['start'] += chunk_start
                entity['end'] += chunk_start
                all_entities.append(entity)
        
        # Remove duplicates
        return deduplicate_entities(all_entities)
    
    def _filter_entities(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter out known false positives"""
        filtered = []
        
        for entity in entities:
            label = entity['label']
            text = entity['text'].strip()
            
            # Check if it's in false positives list
            if label in self.false_positives:
                if text in self.false_positives[label]:
                    continue
            
            filtered.append(entity)
        
        return filtered
    
    def _char_to_token_span(self, doc: Doc, start_char: int, end_char: int, label: str, score: float) -> Span:
        """Convert character offsets to token span"""
        start_token = None
        end_token = None
        
        # Find token boundaries
        for token in doc:
            if start_token is None and token.idx <= start_char < token.idx + len(token.text):
                start_token = token.i
            if token.idx < end_char <= token.idx + len(token.text):
                end_token = token.i + 1
                break
            if token.idx >= end_char:
                end_token = token.i
                break
        
        # Fallback for boundary cases
        if start_token is None:
            for token in doc:
                if token.idx >= start_char:
                    start_token = token.i
                    break
        
        if end_token is None:
            end_token = len(doc)
        
        # Create span if valid
        if start_token is not None and end_token is not None and start_token < end_token:
            try:
                span = Span(doc, start_token, end_token, label=label)
                # Store the GLiNER confidence score on the span
                span._.confidence = score
                return span
            except Exception:
                return None
        
        return None


def create_pipeline(language: str = "de",
                   threshold: float = DEFAULT_THRESHOLD,
                   filter_false_positives: bool = False,
                   filter_file: str = "data/false_positives.json") -> Language:
    """Create a spaCy pipeline with PII detection
    
    Args:
        language: Language code (de, en, etc.)
        threshold: Confidence threshold for entity detection
        filter_false_positives: Whether to filter known false positives
        filter_file: Path to false positives JSON file
    
    Returns:
        Configured spaCy Language object
    """
    # Create blank pipeline
    nlp = spacy.blank(language)
    
    # Add sentencizer for sentence boundaries
    nlp.add_pipe("sentencizer")
    
    # Add PII detector
    config = {
        "threshold": threshold,
        "filter_false_positives": filter_false_positives,
        "filter_file": filter_file
    }
    nlp.add_pipe("pii_detector", config=config)
    
    return nlp