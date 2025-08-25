"""
Fuzzy matching for catching entity variations not detected by GLiNER
"""

import re
from typing import List, Dict, Tuple, Set, Optional
from difflib import SequenceMatcher


class FuzzyEntityMatcher:
    """Catches entity variations using fuzzy matching after GLiNER detection"""
    
    def __init__(self, similarity_threshold: float = 0.85):
        self.similarity_threshold = similarity_threshold
    
    def find_all_variations(self, text: str, detected_entities: Dict[str, List[str]]) -> List[Tuple[int, int, str, str]]:
        """
        Find all variations of detected entities in text, including possessives and fuzzy matches
        
        Args:
            text: Original text
            detected_entities: Dict mapping entity types to list of entity texts
        
        Returns:
            List of (start, end, original_text, canonical_form) tuples
        """
        all_matches = []
        
        for entity_type, entity_texts in detected_entities.items():
            # Skip non-person entities for possessive matching
            allow_possessive = entity_type.lower() == "person"
            allow_fuzzy = entity_type.lower() in ["person", "organization", "location"]
            
            for entity_text in entity_texts:
                # Find exact and fuzzy matches
                matches = self._find_entity_variations(
                    text, 
                    entity_text, 
                    allow_possessive=allow_possessive,
                    allow_fuzzy=allow_fuzzy
                )
                
                for start, end, matched_text in matches:
                    all_matches.append((start, end, matched_text, entity_text))
        
        # Sort by position and remove overlaps
        return self._remove_overlaps(all_matches)
    
    def _find_entity_variations(self, text: str, entity: str, allow_possessive: bool = True, allow_fuzzy: bool = False) -> List[Tuple[int, int, str]]:
        """Find all variations of an entity in text including fuzzy matches"""
        matches = []
        entity_lower = entity.lower()
        
        # For person names, extract first/last name components
        name_parts = entity.split()
        
        # Pattern 1: Exact matches (case-insensitive)
        pattern = re.compile(re.escape(entity), re.IGNORECASE)
        for match in pattern.finditer(text):
            matches.append((match.start(), match.end(), match.group()))
        
        # Pattern 2: Possessive forms (German: add 's' or just 's')
        if allow_possessive and name_parts:
            for name_part in name_parts:
                if len(name_part) > 2:  # Skip short parts
                    # German possessive: Annas, Adrians
                    possessive_pattern = re.compile(
                        rf'\b{re.escape(name_part)}s\b', 
                        re.IGNORECASE
                    )
                    for match in possessive_pattern.finditer(text):
                        matches.append((match.start(), match.end(), match.group()))
        
        # Pattern 3: Subset matching for names (Anna in "Anna Meier")
        if allow_possessive and len(name_parts) == 1:
            # Single name - might be part of a longer name
            single_name = name_parts[0]
            if len(single_name) > 2:
                word_pattern = re.compile(rf'\b{re.escape(single_name)}\b', re.IGNORECASE)
                for match in word_pattern.finditer(text):
                    if not any(m[0] == match.start() for m in matches):
                        matches.append((match.start(), match.end(), match.group()))
        
        # Pattern 4: Fuzzy matching for typos and variations
        if allow_fuzzy and len(entity) > 3:  # Only for entities longer than 3 chars
            # Find potential fuzzy matches using sliding window
            matches.extend(self._find_fuzzy_matches(text, entity))
        
        return matches
    
    def _find_fuzzy_matches(self, text: str, entity: str) -> List[Tuple[int, int, str]]:
        """Find fuzzy matches for an entity in text using SequenceMatcher"""
        matches = []
        entity_lower = entity.lower()
        text_lower = text.lower()
        entity_len = len(entity)
        
        # Use sliding window approach for fuzzy matching
        # Check windows of similar size (±20% of entity length)
        min_len = max(3, int(entity_len * 0.8))
        max_len = int(entity_len * 1.2) + 1
        
        # Find word boundaries to search within
        import re
        words = list(re.finditer(r'\b\w+\b', text))
        
        for word_match in words:
            word = word_match.group()
            word_lower = word.lower()
            
            # Skip if word is too different in length
            if len(word) < min_len or len(word) > max_len:
                continue
            
            # Calculate similarity using SequenceMatcher
            similarity = SequenceMatcher(None, entity_lower, word_lower).ratio()
            
            # If similarity is above threshold, consider it a match
            if similarity >= self.similarity_threshold:
                # Don't add if it's already covered by exact matching
                if word_lower != entity_lower:
                    matches.append((word_match.start(), word_match.end(), word))
        
        return matches
    
    def _remove_overlaps(self, matches: List[Tuple[int, int, str, str]]) -> List[Tuple[int, int, str, str]]:
        """Remove overlapping matches, keeping the longest ones"""
        if not matches:
            return []
        
        # Sort by start position, then by length (descending)
        sorted_matches = sorted(matches, key=lambda x: (x[0], -(x[1] - x[0])))
        
        result = []
        last_end = -1
        
        for match in sorted_matches:
            start, end, text, canonical = match
            if start >= last_end:
                result.append(match)
                last_end = end
        
        return result


def create_comprehensive_replacements(
    text: str,
    entities_by_type: Dict[str, List[str]],
    entity_to_placeholder: Dict[str, str],
    replaced_spans: Optional[Set[Tuple[int, int]]] = None
) -> str:
    """
    Replace all entity variations with placeholders
    
    Args:
        text: Original text
        entities_by_type: Dict of entity type to list of entity texts
        entity_to_placeholder: Mapping from canonical entity text to placeholder
        replaced_spans: Set of (start, end) tuples indicating already replaced regions
    
    Returns:
        Text with all variations replaced
    """
    if replaced_spans is None:
        replaced_spans = set()
    
    matcher = FuzzyEntityMatcher()
    
    # Find all variations
    variations = matcher.find_all_variations(text, entities_by_type)
    
    # Filter out variations that overlap with already replaced spans
    filtered_variations = []
    for start, end, matched_text, canonical_form in variations:
        # Check if this span overlaps with any already replaced region
        overlaps = False
        for replaced_start, replaced_end in replaced_spans:
            if not (end <= replaced_start or start >= replaced_end):
                overlaps = True
                break
        
        if not overlaps:
            filtered_variations.append((start, end, matched_text, canonical_form))
    
    # Sort by position (reverse for replacement)
    filtered_variations = sorted(filtered_variations, key=lambda x: x[0], reverse=True)
    
    # Replace all variations
    for start, end, matched_text, canonical_form in filtered_variations:
        if canonical_form in entity_to_placeholder:
            placeholder = entity_to_placeholder[canonical_form]
            text = text[:start] + placeholder + text[end:]
    
    return text