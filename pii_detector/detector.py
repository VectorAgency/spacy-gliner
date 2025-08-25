"""
SpaCy component for PII detection using GLiNER
"""

from typing import List, Dict, Any, Tuple
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
        
        # Register custom attribute for processing metadata on Doc
        if not Doc.has_extension("pii_processing_metadata"):
            Doc.set_extension("pii_processing_metadata", default={})
        
        # Load false positives filter (convert to lowercase for case-insensitive matching)
        self.false_positives = {}
        if filter_false_positives:
            fp_data = load_false_positives(filter_file)
            # Convert all false positives to lowercase for case-insensitive matching
            for label, terms in fp_data.items():
                self.false_positives[label] = set(term.lower() for term in terms)
    
    def __call__(self, doc: Doc) -> Doc:
        """Process a spaCy Doc"""
        text = doc.text
        
        # Initialize metadata storage
        from .config import GLINER_MODEL_NAME
        metadata = {
            'chunk_boundaries': [],
            'filtered_false_positives': [],
            'overlapping_entities_removed': [],
            'all_raw_entities': [],
            'model_info': {
                'name': GLINER_MODEL_NAME,
                'threshold': self.threshold,
                'chunk_size': self.chunk_size,
                'overlap': self.overlap
            }
        }
        
        # Extract entities with chunking (modified to also return chunks)
        raw_entities, chunks = self._extract_chunked_with_metadata(text)
        metadata['chunk_boundaries'] = chunks
        metadata['all_raw_entities'] = raw_entities.copy()
        
        # Filter false positives if enabled
        filtered_out = []
        if self.filter_false_positives:
            raw_entities, filtered_out = self._filter_entities_with_tracking(raw_entities)
            metadata['filtered_false_positives'] = filtered_out
        
        # Convert to spaCy spans
        spans = []
        failed_conversions = []
        for ent in raw_entities:
            # GLiNER always provides a score field - if missing, something is wrong
            if 'score' not in ent:
                raise ValueError(f"GLiNER entity missing score: {ent}")
            span = self._char_to_token_span(doc, ent['start'], ent['end'], ent['label'], ent['score'])
            if span:
                spans.append(span)
            else:
                failed_conversions.append(ent)
        
        # Track overlapping entities before filtering
        all_spans = spans.copy()
        filtered_spans = filter_spans(spans)
        
        # Find which spans were removed due to overlap
        removed_spans = []
        for span in all_spans:
            if span not in filtered_spans:
                removed_spans.append({
                    'text': span.text,
                    'label': span.label_,
                    'start': span.start_char,
                    'end': span.end_char,
                    'score': span._.confidence if hasattr(span._, 'confidence') else 1.0
                })
        metadata['overlapping_entities_removed'] = removed_spans
        
        # Set doc entities and metadata
        doc.ents = filtered_spans
        doc._.pii_processing_metadata = metadata
        
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
        """Filter out known false positives (case-insensitive)"""
        filtered = []
        
        for entity in entities:
            label = entity['label']
            text_lower = entity['text'].strip().lower()
            
            # Check if it's in false positives list (case-insensitive)
            if label in self.false_positives:
                if text_lower in self.false_positives[label]:
                    continue
            
            filtered.append(entity)
        
        return filtered
    
    def _extract_chunked_with_metadata(self, text: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Extract entities with chunking, also return chunk boundaries"""
        all_entities = []
        chunks = chunk_text(text, self.chunk_size, self.overlap)
        chunk_boundaries = []
        
        for chunk_info in chunks:
            chunk_content = chunk_info['text']
            chunk_start = chunk_info['start']
            chunk_end = chunk_info['end']
            
            # Store chunk boundary info
            chunk_boundaries.append({
                'start': chunk_start,
                'end': chunk_end,
                'length': len(chunk_content)
            })
            
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
        deduplicated = deduplicate_entities(all_entities)
        return deduplicated, chunk_boundaries
    
    def _filter_entities_with_tracking(self, entities: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Filter out known false positives and track what was filtered"""
        filtered = []
        filtered_out = []
        
        for entity in entities:
            label = entity['label']
            text_lower = entity['text'].strip().lower()
            
            # Check if it's in false positives list (case-insensitive)
            if label in self.false_positives:
                if text_lower in self.false_positives[label]:
                    filtered_out.append(entity)
                    continue
            
            filtered.append(entity)
        
        return filtered, filtered_out
    
    def _char_to_token_span(self, doc: Doc, start_char: int, end_char: int, label: str, score: float) -> Span:
        """Convert character offsets to token span using spaCy's built-in method"""
        # Use spaCy's built-in char_span method with contract alignment mode
        # This ensures we don't extend beyond the actual entity boundaries
        span = doc.char_span(start_char, end_char, label=label, alignment_mode="contract")
        
        if span:
            # Store the GLiNER confidence score on the span
            span._.confidence = score
            return span
        
        # Fallback to expand mode if contract didn't work
        span = doc.char_span(start_char, end_char, label=label, alignment_mode="expand")
        if span:
            span._.confidence = score
            return span
        
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