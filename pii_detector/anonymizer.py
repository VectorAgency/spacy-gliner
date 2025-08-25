"""
Anonymization and entity resolution for PII detection
"""

from typing import Dict, List, Tuple, Optional
from collections import defaultdict
from spacy.tokens import Doc, Span
from .fuzzy_matcher import create_comprehensive_replacements


class EntityResolver:
    """Resolve coreferences between entities (e.g., 'Anna' and 'Anna Meier')"""
    
    def __init__(self, similarity_threshold: float = 0.8):
        self.similarity_threshold = similarity_threshold
    
    def resolve_entities(self, entities: List[Span]) -> Dict[Span, str]:
        """Group entities that refer to the same real-world entity
        
        Args:
            entities: List of spaCy Span objects
        
        Returns:
            Mapping from entity span to canonical ID
        """
        if not entities:
            return {}
        
        # Group entities by label
        entities_by_label = defaultdict(list)
        for ent in entities:
            entities_by_label[ent.label_].append(ent)
        
        # Resolve within each label group
        entity_to_id = {}
        
        for label, label_entities in entities_by_label.items():
            clusters = self._cluster_entities(label_entities)
            
            # Assign IDs to clusters
            for cluster_id, cluster in enumerate(clusters):
                for ent in cluster:
                    entity_to_id[ent] = f"{label.upper()}_{cluster_id}"
        
        return entity_to_id
    
    def _cluster_entities(self, entities: List[Span]) -> List[List[Span]]:
        """Cluster entities that likely refer to the same thing
        
        Simple rules:
        1. Exact match -> same cluster
        2. One name contained in another -> same cluster (e.g., 'Anna' in 'Anna Meier')
        3. Same last word (for names) -> likely same cluster
        """
        if not entities:
            return []
        
        clusters = []
        entity_to_cluster = {}
        
        for ent in entities:
            matched = False
            ent_text = ent.text.strip()
            ent_tokens = ent_text.split()
            
            # Check against existing clusters
            for cluster in clusters:
                for existing_ent in cluster:
                    existing_text = existing_ent.text.strip()
                    existing_tokens = existing_text.split()
                    
                    # Rule 1: Exact match
                    if ent_text.lower() == existing_text.lower():
                        cluster.append(ent)
                        matched = True
                        break
                    
                    # Rule 2: Containment (for person names)
                    if ent.label_ == "person":
                        if (self._is_name_subset(ent_tokens, existing_tokens) or 
                            self._is_name_subset(existing_tokens, ent_tokens)):
                            cluster.append(ent)
                            matched = True
                            break
                    
                    # Rule 3: Organizations/locations - exact match only
                    # (to avoid false matches like "Schule" and "Berufsschule")
                    
                if matched:
                    break
            
            # Create new cluster if no match
            if not matched:
                clusters.append([ent])
        
        return clusters
    
    def _is_name_subset(self, tokens1: List[str], tokens2: List[str]) -> bool:
        """Check if all tokens in tokens1 exist in tokens2"""
        if not tokens1 or not tokens2:
            return False
        
        tokens2_lower = [t.lower() for t in tokens2]
        return all(t.lower() in tokens2_lower for t in tokens1)


def anonymize_doc(doc: Doc, 
                  resolve_entities: bool = True,
                  label_mapping: Optional[Dict[str, str]] = None,
                  placeholder_format: str = "[{label}_{id}]",
                  include_scores: bool = False,
                  use_fuzzy_matching: bool = True) -> Tuple[str, Dict[str, str]]:
    """Anonymize a spaCy Doc by replacing entities with placeholders
    
    Args:
        doc: spaCy Doc with entities
        resolve_entities: Whether to resolve coreferences
        label_mapping: Optional dict to map labels (e.g., {"person": "NAME"})
        placeholder_format: Format string for placeholders (default: "[{label}_{id}]")
        include_scores: Whether to include confidence scores in the mapping
        use_fuzzy_matching: Whether to use fuzzy matching to catch all variations
    
    Returns:
        Tuple of (anonymized text, mapping of placeholders to original values)
        If include_scores=True, mapping values will be dicts with 'text' and 'score' keys
    
    Examples:
        placeholder_format="[{label}_{id}]" → [PERSON_0]
        placeholder_format="<<{label}#{id}>>" → <<PERSON#0>>
        With label_mapping={"person": "NAME"} → [NAME_0]
    """
    if not doc.ents:
        return doc.text, {}
    
    # Resolve entities if requested
    if resolve_entities:
        resolver = EntityResolver()
        entity_to_id = resolver.resolve_entities(list(doc.ents))
    else:
        # Simple counter-based IDs
        entity_counts = {}
        entity_to_id = {}
        
        for ent in doc.ents:
            label = ent.label_.upper()
            if label not in entity_counts:
                entity_counts[label] = 0
            entity_to_id[ent] = f"{label}_{entity_counts[label]}"
            entity_counts[label] += 1
    
    # Build mappings for fuzzy matching
    entity_to_placeholder = {}
    placeholder_to_original = {}
    entities_by_type = defaultdict(set)
    
    # Process each entity to create placeholder mappings
    for ent in doc.ents:
        # Extract label and ID from entity_to_id
        entity_id_parts = entity_to_id[ent].split('_')
        label = entity_id_parts[0]
        id_num = entity_id_parts[1] if len(entity_id_parts) > 1 else '0'
        
        # Apply label mapping if provided
        original_label = ent.label_.lower()
        if label_mapping and original_label in label_mapping:
            label = label_mapping[original_label].upper()
        
        # Format placeholder using the provided format
        placeholder = placeholder_format.format(label=label, id=id_num)
        
        # Track canonical forms for fuzzy matching
        entity_to_placeholder[ent.text] = placeholder
        entities_by_type[ent.label_].add(ent.text)
        
        # Store mapping (consolidate multiple texts to same placeholder)
        if placeholder not in placeholder_to_original:
            if include_scores:
                # Use the highest confidence score for this placeholder
                if hasattr(ent._, 'confidence'):
                    placeholder_to_original[placeholder] = {
                        "text": ent.text,
                        "score": round(ent._.confidence, 3)
                    }
                else:
                    placeholder_to_original[placeholder] = {
                        "text": ent.text,
                        "score": 1.0
                    }
            else:
                placeholder_to_original[placeholder] = ent.text
    
    # Use fuzzy matching to replace ALL variations if enabled
    if use_fuzzy_matching:
        # Convert set to list for fuzzy matcher
        entities_by_type_list = {k: list(v) for k, v in entities_by_type.items()}
        
        # Replace all variations comprehensively
        text = create_comprehensive_replacements(
            doc.text,
            entities_by_type_list,
            entity_to_placeholder
        )
    else:
        # Original approach: only replace what GLiNER found
        text = doc.text
        sorted_entities = sorted(doc.ents, key=lambda e: e.start_char, reverse=True)
        
        for ent in sorted_entities:
            placeholder = entity_to_placeholder[ent.text]
            text = text[:ent.start_char] + placeholder + text[ent.end_char:]
    
    return text, placeholder_to_original


def create_anonymizer(resolve_entities: bool = True) -> callable:
    """Create an anonymizer function with configuration
    
    Args:
        resolve_entities: Whether to resolve entity coreferences
    
    Returns:
        Configured anonymizer function
    """
    def anonymizer(doc: Doc) -> Tuple[str, Dict[str, str]]:
        return anonymize_doc(doc, resolve_entities=resolve_entities)
    
    return anonymizer