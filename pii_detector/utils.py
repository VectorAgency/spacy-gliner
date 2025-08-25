"""
Shared utilities for PII detection
"""

import os
import pickle
import json
from typing import List, Dict, Any
from gliner import GLiNER


# Configuration constants
DEFAULT_LABELS = [
    "person", "organization", "location", "country",
    "email", "phone_number", "birthdate", "address"
]

DEFAULT_CHUNK_SIZE = 1400
DEFAULT_OVERLAP = 200
DEFAULT_THRESHOLD = 0.3
MODEL_CACHE_PATH = "gliner_model_cache.pkl"


def load_gliner_model(cache_path: str = MODEL_CACHE_PATH) -> GLiNER:
    """Load GLiNER model with caching support
    
    Args:
        cache_path: Path to cache file
    
    Returns:
        Loaded GLiNER model
    """
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "rb") as f:
                return pickle.load(f)
        except Exception:
            pass
    
    print("Downloading PII model (first time only, ~500MB)...", flush=True)
    model = GLiNER.from_pretrained("urchade/gliner_multi_pii-v1")
    
    try:
        with open(cache_path, "wb") as f:
            pickle.dump(model, f)
    except Exception:
        pass
    
    return model


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
    """Remove duplicate entities based on proximity and text
    
    Args:
        entities: List of entity dicts with 'text', 'label', 'start', 'end', 'score'
        proximity_threshold: Maximum character distance to consider duplicates
    
    Returns:
        Deduplicated list of entities
    """
    if not entities:
        return []
    
    # Sort by position and score
    sorted_entities = sorted(entities, key=lambda x: (x['start'], -x.get('score', 0)))
    
    unique_entities = []
    seen = set()
    
    for entity in sorted_entities:
        key = (entity['text'], entity['label'], entity['start'])
        is_duplicate = False
        
        for seen_text, seen_label, seen_start in seen:
            if (entity['label'] == seen_label and 
                abs(entity['start'] - seen_start) < proximity_threshold and
                entity['text'] == seen_text):
                is_duplicate = True
                break
        
        if not is_duplicate:
            unique_entities.append(entity)
            seen.add(key)
    
    return sorted(unique_entities, key=lambda x: x['start'])