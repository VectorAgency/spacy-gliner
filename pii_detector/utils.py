"""
Shared utilities for PII detection
"""

import os
import json
from typing import List, Dict, Any, Optional
from gliner import GLiNER
from .config import (
    DEFAULT_LABELS, 
    DEFAULT_CHUNK_SIZE, 
    DEFAULT_OVERLAP, 
    DEFAULT_THRESHOLD,
    GLINER_MODEL_NAME
)

# Global model cache (singleton pattern)
_cached_model: Optional[GLiNER] = None


def load_gliner_model() -> GLiNER:
    """Load GLiNER model with HuggingFace caching
    
    Uses HuggingFace's built-in caching mechanism which stores models
    in ~/.cache/huggingface/ by default. This is more robust than
    pickling the entire model object.
    
    Returns:
        Loaded GLiNER model
    """
    global _cached_model
    
    if _cached_model is None:
        # Model will be cached by HuggingFace transformers library
        # in ~/.cache/huggingface/hub/ automatically
        print(f"Loading GLiNER model: {GLINER_MODEL_NAME}")
        _cached_model = GLiNER.from_pretrained(GLINER_MODEL_NAME)
    
    return _cached_model


def load_false_positives(file_path: str) -> Dict[str, List[str]]:
    """Load false positives filter from JSON file
    
    Args:
        file_path: Path to false positives JSON file
    
    Returns:
        Dictionary mapping labels to lists of false positive terms
    """
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def chunk_text(text: str, chunk_size: int = DEFAULT_CHUNK_SIZE, 
               overlap: int = DEFAULT_OVERLAP) -> List[Dict[str, Any]]:
    """Split text into overlapping chunks for processing
    
    Args:
        text: Text to chunk
        chunk_size: Size of each chunk
        overlap: Overlap between chunks
    
    Returns:
        List of dicts with 'text', 'start', 'end' keys
    """
    chunks = []
    text_length = len(text)
    position = 0
    
    while position < text_length:
        chunk_start = max(0, position - overlap if position > 0 else 0)
        chunk_end = min(position + chunk_size, text_length)
        
        chunks.append({
            'text': text[chunk_start:chunk_end],
            'start': chunk_start,
            'end': chunk_end
        })
        
        position += chunk_size
    
    return chunks


def deduplicate_entities(entities: List[Dict[str, Any]], 
                        proximity_threshold: int = 10) -> List[Dict[str, Any]]:
    """Remove duplicate entities based on proximity and text (O(n) complexity)
    
    Args:
        entities: List of entity dicts with 'text', 'label', 'start', 'end', 'score'
        proximity_threshold: Maximum character distance to consider duplicates
    
    Returns:
        Deduplicated list of entities
    """
    if not entities:
        return []
    
    # Sort by position and score (higher score first)
    sorted_entities = sorted(entities, key=lambda x: (x['start'], -x.get('score', 0)))
    
    unique_entities = []
    # Track last position for each (label, text) combination for O(1) lookup
    last_positions = {}
    
    for entity in sorted_entities:
        # Create a key based on label and normalized text
        key = (entity['label'], entity['text'].lower())
        
        # Check if we've seen this entity recently
        if key in last_positions:
            last_start = last_positions[key]
            # If it's too close to the last occurrence, skip it
            if abs(entity['start'] - last_start) < proximity_threshold:
                continue
        
        # Add to unique entities and update last position
        unique_entities.append(entity)
        last_positions[key] = entity['start']
    
    return unique_entities