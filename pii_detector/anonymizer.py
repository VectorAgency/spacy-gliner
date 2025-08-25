"""
Anonymization and entity resolution for PII detection
"""

from typing import Dict, List, Tuple, Optional, Set, Callable
from collections import defaultdict
from spacy.tokens import Doc, Span
from .fuzzy_matcher import create_comprehensive_replacements
from .config import LABEL_MAPPING, PLACEHOLDER_FORMATS, DEFAULT_PLACEHOLDER_FORMAT


class EntityCluster:
    """Represents a cluster of coreferent entities"""
    def __init__(self, label: str):
        self.label = label
        self.members: List[Span] = []
        self.canonical: str = ""  # Longest or most complete form
        self.first_position: float = float('inf')
    
    def add_member(self, span: Span):
        self.members.append(span)
        # Update canonical to longest form
        if len(span.text) > len(self.canonical):
            self.canonical = span.text
        # Track first appearance
        if span.start_char < self.first_position:
            self.first_position = span.start_char


class EntityResolver:
    """Resolve coreferences between entities (e.g., 'Anna' and 'Anna Meier')"""
    
    def __init__(self, similarity_threshold: float = 0.8):
        self.similarity_threshold = similarity_threshold
    
    def cluster_entities(self, entities: List[Span]) -> List[EntityCluster]:
        """Group entities that refer to the same real-world entity
        
        Args:
            entities: List of spaCy Span objects
        
        Returns:
            List of EntityCluster objects
        """
        if not entities:
            return []
        
        # Group entities by label
        entities_by_label = defaultdict(list)
        for ent in entities:
            entities_by_label[ent.label_].append(ent)
        
        # Resolve within each label group
        all_clusters = []
        
        for label, label_entities in entities_by_label.items():
            clusters = self._cluster_entities(label, label_entities)
            all_clusters.extend(clusters)
        
        return all_clusters
    
    def _cluster_entities(self, label: str, entities: List[Span]) -> List[EntityCluster]:
        """Cluster entities that likely refer to the same thing
        
        Simple rules:
        1. Exact match -> same cluster
        2. One name contained in another -> same cluster (e.g., 'Anna' in 'Anna Meier')
        3. Apply similarity threshold for merging decisions
        """
        if not entities:
            return []
        
        clusters = []
        
        for ent in entities:
            matched = False
            ent_text = ent.text.strip()
            ent_tokens = set(t.lower() for t in ent_text.split())
            
            # Check against existing clusters
            for cluster in clusters:
                # Check similarity with cluster canonical
                if self._should_merge(ent, cluster):
                    cluster.add_member(ent)
                    matched = True
                    break
            
            # Create new cluster if no match
            if not matched:
                new_cluster = EntityCluster(label)
                new_cluster.add_member(ent)
                clusters.append(new_cluster)
        
        return clusters
    
    def _should_merge(self, entity: Span, cluster: EntityCluster) -> bool:
        """Decide if entity should be merged into cluster"""
        ent_text = entity.text.strip()
        ent_tokens = set(t.lower() for t in ent_text.split())
        
        # Check against each member in cluster
        for member in cluster.members:
            member_text = member.text.strip()
            member_tokens = set(t.lower() for t in member_text.split())
            
            # Rule 1: Exact match (case-insensitive)
            if ent_text.lower() == member_text.lower():
                return True
            
            # Rule 2: Containment (for person names only)
            if entity.label_ == "person":
                # Check if all tokens of one are subset of the other
                if ent_tokens.issubset(member_tokens) or member_tokens.issubset(ent_tokens):
                    # Apply similarity threshold
                    jaccard = len(ent_tokens & member_tokens) / len(ent_tokens | member_tokens)
                    if jaccard >= self.similarity_threshold:
                        return True
        
        return False
    


def span_key(ent: Span) -> Tuple[int, int, str]:
    """Create unique key for a span"""
    return (ent.start_char, ent.end_char, ent.label_)


def anonymize_doc(doc: Doc, 
                  resolve_entities: bool = True,
                  label_mapping: Optional[Dict[str, str]] = None,
                  placeholder_format: str = None,
                  include_scores: bool = False,
                  use_fuzzy_matching: bool = True) -> Tuple[str, Dict[str, str]]:
    """Anonymize a spaCy Doc by replacing entities with placeholders
    
    Args:
        doc: spaCy Doc with entities
        resolve_entities: Whether to resolve coreferences
        label_mapping: Optional dict to map labels (e.g., {"person": "NAME"})
        placeholder_format: Format string for placeholders (uses config default if None)
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
    # Use default format if not specified
    if placeholder_format is None:
        placeholder_format = PLACEHOLDER_FORMATS[DEFAULT_PLACEHOLDER_FORMAT]
    
    # Use default label mapping if not specified
    if label_mapping is None:
        label_mapping = LABEL_MAPPING
    if not doc.ents:
        return doc.text, {}
    
    # Build clusters of entities
    if resolve_entities:
        resolver = EntityResolver()
        clusters = resolver.cluster_entities(list(doc.ents))
        
        # Sort clusters by first appearance for deterministic IDs
        clusters.sort(key=lambda c: c.first_position)
        
        # Group clusters by label and assign IDs
        clusters_by_label = defaultdict(list)
        for cluster in clusters:
            clusters_by_label[cluster.label].append(cluster)
        
        placeholder_for_cluster = {}
        for label, label_clusters in clusters_by_label.items():
            for idx, cluster in enumerate(label_clusters):
                # Apply label mapping
                mapped_label = label_mapping.get(label, label)
                if mapped_label:
                    mapped_label = mapped_label.upper()
                else:
                    mapped_label = label.upper()
                placeholder = placeholder_format.format(label=mapped_label, id=idx)
                placeholder_for_cluster[id(cluster)] = placeholder
        
        # Map each span to its cluster's placeholder
        span_to_cluster = {}
        for cluster in clusters:
            for member in cluster.members:
                span_to_cluster[span_key(member)] = cluster
    else:
        # Simple counter-based IDs without clustering
        entity_counts = defaultdict(int)
        span_to_placeholder = {}
        
        sorted_entities = sorted(doc.ents, key=lambda e: e.start_char)
        for ent in sorted_entities:
            label = ent.label_
            mapped_label = label_mapping.get(label, label)
            if mapped_label:
                mapped_label = mapped_label.upper()
            else:
                mapped_label = label.upper()
            placeholder = placeholder_format.format(label=mapped_label, id=entity_counts[label])
            span_to_placeholder[span_key(ent)] = placeholder
            entity_counts[label] += 1
    
    # Build mappings
    placeholder_to_original = {}
    replaced_spans: Set[Tuple[int, int]] = set()  # Track replaced regions
    
    if resolve_entities:
        # Build mappings from clusters
        canonical_to_placeholder = {}
        entities_by_type = defaultdict(list)
        
        for cluster in clusters:
            placeholder = placeholder_for_cluster[id(cluster)]
            
            # Store mapping with canonical form
            if placeholder not in placeholder_to_original:
                if include_scores:
                    # Get best score from cluster members
                    best_score = 1.0
                    for member in cluster.members:
                        score = member._.confidence if (hasattr(member._, 'confidence') and 
                                                       member._.confidence is not None) else 1.0
                        best_score = max(best_score, score)
                    
                    placeholder_to_original[placeholder] = {
                        "text": cluster.canonical,
                        "score": round(best_score, 3)
                    }
                else:
                    placeholder_to_original[placeholder] = cluster.canonical
            
            # For fuzzy matching, use cluster canonicals only
            canonical_to_placeholder[cluster.canonical] = placeholder
            entities_by_type[cluster.label].append(cluster.canonical)
    else:
        # Build mappings without clusters
        canonical_to_placeholder = {}
        entities_by_type = defaultdict(set)
        
        for ent in doc.ents:
            placeholder = span_to_placeholder[span_key(ent)]
            canonical_to_placeholder[ent.text] = placeholder
            entities_by_type[ent.label_].add(ent.text)
            
            if placeholder not in placeholder_to_original:
                if include_scores:
                    score = ent._.confidence if (hasattr(ent._, 'confidence') and 
                                               ent._.confidence is not None) else 1.0
                    placeholder_to_original[placeholder] = {
                        "text": ent.text,
                        "score": round(score, 3)
                    }
                else:
                    placeholder_to_original[placeholder] = ent.text
    
    # Replace entities in text
    text = doc.text
    
    # First pass: Replace doc entities (exact spans)
    sorted_entities = sorted(doc.ents, key=lambda e: e.start_char, reverse=True)
    
    for ent in sorted_entities:
        if resolve_entities:
            cluster = span_to_cluster.get(span_key(ent))
            if cluster:
                placeholder = placeholder_for_cluster[id(cluster)]
            else:
                continue
        else:
            placeholder = span_to_placeholder[span_key(ent)]
        
        text = text[:ent.start_char] + placeholder + text[ent.end_char:]
        replaced_spans.add((ent.start_char, ent.end_char))
    
    # Second pass: Fuzzy matching (if enabled)
    if use_fuzzy_matching:
        # Convert to format expected by fuzzy matcher
        entities_by_type_list = {k: list(v) if isinstance(v, set) else v 
                                 for k, v in entities_by_type.items()}
        
        # Create comprehensive replacements with safety check
        text = create_comprehensive_replacements(
            text,
            entities_by_type_list,
            canonical_to_placeholder,
            replaced_spans=replaced_spans  # Pass already replaced regions
        )
    
    return text, placeholder_to_original


def create_anonymizer(resolve_entities: bool = True) -> Callable[[Doc], Tuple[str, Dict[str, str]]]:
    """Create an anonymizer function with configuration
    
    Args:
        resolve_entities: Whether to resolve entity coreferences
    
    Returns:
        Configured anonymizer function
    """
    def anonymizer(doc: Doc) -> Tuple[str, Dict[str, str]]:
        return anonymize_doc(doc, resolve_entities=resolve_entities)
    
    return anonymizer