"""
Fuzzy matching for catching entity variations not detected by GLiNER
"""

import re
from typing import List, Dict, Tuple, Set
from difflib import SequenceMatcher


class FuzzyEntityMatcher:
    """Catches entity variations using fuzzy matching after GLiNER detection"""
    
    def __init__(self, similarity_threshold: float = 0.85):
        self.similarity_threshold = similarity_threshold
    
    def find_all_variations(self, text: str, detected_entities: Dict[str, List[str]]) -> List[Tuple[int, int, str, str]]:
        """
        Find all variations of detected entities in text, including possessives
        
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
            
            for entity_text in entity_texts:
                # Find exact and fuzzy matches
                matches = self._find_entity_variations(
                    text, 
                    entity_text, 
                    allow_possessive=allow_possessive
                )
                
                for start, end, matched_text in matches:
                    all_matches.append((start, end, matched_text, entity_text))
        
        # Sort by position and remove overlaps
        return self._remove_overlaps(all_matches)
    
    def _find_entity_variations(self, text: str, entity: str, allow_possessive: bool = True) -> List[Tuple[int, int, str]]:
        """Find all variations of an entity in text"""
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
    entity_to_placeholder: Dict[str, str]
) -> str:
    """
    Replace all entity variations with placeholders
    
    Args:
        text: Original text
        entities_by_type: Dict of entity type to list of entity texts
        entity_to_placeholder: Mapping from canonical entity text to placeholder
    
    Returns:
        Text with all variations replaced
    """
    matcher = FuzzyEntityMatcher()
    
    # Find all variations
    variations = matcher.find_all_variations(text, entities_by_type)
    
    # Sort by position (reverse for replacement)
    variations = sorted(variations, key=lambda x: x[0], reverse=True)
    
    # Replace all variations
    for start, end, matched_text, canonical_form in variations:
        if canonical_form in entity_to_placeholder:
            placeholder = entity_to_placeholder[canonical_form]
            text = text[:start] + placeholder + text[end:]
    
    return text