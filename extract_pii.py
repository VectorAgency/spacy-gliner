#!/usr/bin/env python3
"""
CLI for PII detection and anonymization
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from collections import defaultdict
from pii_detector import create_pipeline, anonymize_doc
from pii_detector.config import PLACEHOLDER_FORMATS


def format_metadata(metadata):
    """Format metadata dictionary into a readable text format"""
    lines = []
    lines.append("=" * 80)
    lines.append("PII EXTRACTION AND ANONYMIZATION METADATA")
    lines.append("=" * 80)
    lines.append(f"Generated: {metadata.get('processing_timestamp', 'N/A')}")
    lines.append(f"Input File: {metadata.get('input_file', 'N/A')}")
    lines.append("")
    
    # 1. Entity Mapping
    lines.append("1. ENTITY MAPPING (Placeholder → Original Text)")
    lines.append("-" * 40)
    mapping = metadata.get('entity_mapping', {})
    if mapping:
        for placeholder, original in sorted(mapping.items()):
            if isinstance(original, dict):
                lines.append(f"  {placeholder} → {original['text']} (score: {original['score']})")
            else:
                lines.append(f"  {placeholder} → {original}")
    else:
        lines.append("  No entities found")
    lines.append("")
    
    # 2. Individual Entity Occurrences
    lines.append("2. INDIVIDUAL ENTITY OCCURRENCES")
    lines.append("-" * 40)
    entities = metadata.get('entities', [])
    if entities:
        for ent in entities[:20]:  # Show first 20
            lines.append(f"  [{ent['label']}] \"{ent['text']}\" at {ent['start']}-{ent['end']} (score: {ent['score']})")
        if len(entities) > 20:
            lines.append(f"  ... and {len(entities) - 20} more entities")
    else:
        lines.append("  No entities detected")
    lines.append("")
    
    # 3. Entity Clustering Details
    lines.append("3. ENTITY CLUSTERING DETAILS")
    lines.append("-" * 40)
    clusters = metadata.get('clustering', [])
    if clusters:
        for cluster in clusters:
            lines.append(f"  {cluster['label']}: {cluster['canonical']}")
            lines.append(f"    Members: {', '.join(cluster['members'])}")
    else:
        lines.append("  No clustering performed or no clusters found")
    lines.append("")
    
    # 4. Fuzzy Match Captures
    lines.append("4. FUZZY MATCH CAPTURES")
    lines.append("-" * 40)
    fuzzy_matches = metadata.get('fuzzy_matches', [])
    if fuzzy_matches:
        for match in fuzzy_matches[:10]:  # Show first 10
            lines.append(f"  \"{match['matched_text']}\" → {match['canonical_form']} ({match['match_type']})")
        if len(fuzzy_matches) > 10:
            lines.append(f"  ... and {len(fuzzy_matches) - 10} more fuzzy matches")
    else:
        lines.append("  No fuzzy matches found")
    lines.append("")
    
    # 5. Confidence Score Statistics
    lines.append("5. CONFIDENCE SCORE STATISTICS")
    lines.append("-" * 40)
    conf_stats = metadata.get('confidence_stats', {})
    if conf_stats:
        for label, stats in sorted(conf_stats.items()):
            lines.append(f"  {label}: min={stats['min']}, max={stats['max']}, avg={stats['avg']}")
    else:
        lines.append("  No confidence statistics available")
    lines.append("")
    
    # 6. Processing Configuration
    lines.append("6. PROCESSING CONFIGURATION")
    lines.append("-" * 40)
    config = metadata.get('configuration', {})
    for key, value in config.items():
        lines.append(f"  {key}: {value}")
    lines.append("")
    
    # 7. Entity Type Distribution
    lines.append("7. ENTITY TYPE DISTRIBUTION")
    lines.append("-" * 40)
    distribution = metadata.get('entity_distribution', {})
    if distribution:
        total = sum(distribution.values())
        for entity_type, count in sorted(distribution.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / total * 100) if total > 0 else 0
            lines.append(f"  {entity_type}: {count} ({percentage:.1f}%)")
    else:
        lines.append("  No entities detected")
    lines.append("")
    
    # 8. Filtered False Positives
    lines.append("8. FILTERED FALSE POSITIVES")
    lines.append("-" * 40)
    filtered = metadata.get('filtered_false_positives', [])
    if filtered:
        for fp in filtered[:10]:  # Show first 10
            lines.append(f"  [{fp['label']}] \"{fp['text']}\" (score: {fp.get('score', 'N/A')})")
        if len(filtered) > 10:
            lines.append(f"  ... and {len(filtered) - 10} more filtered")
    else:
        lines.append("  No false positives filtered")
    lines.append("")
    
    # 9. Processing Statistics
    lines.append("9. PROCESSING STATISTICS")
    lines.append("-" * 40)
    stats = metadata.get('statistics', {})
    for key, value in stats.items():
        lines.append(f"  {key}: {value}")
    lines.append("")
    
    # 10. Overlapping Entities Removed
    lines.append("10. OVERLAPPING ENTITIES REMOVED")
    lines.append("-" * 40)
    overlapping = metadata.get('overlapping_entities_removed', [])
    if overlapping:
        for ent in overlapping[:5]:  # Show first 5
            lines.append(f"  [{ent['label']}] \"{ent['text']}\" at {ent['start']}-{ent['end']}")
        if len(overlapping) > 5:
            lines.append(f"  ... and {len(overlapping) - 5} more overlapping entities")
    else:
        lines.append("  No overlapping entities removed")
    lines.append("")
    
    # 11. Chunk Boundaries
    lines.append("11. CHUNK BOUNDARIES")
    lines.append("-" * 40)
    chunks = metadata.get('chunk_boundaries', [])
    if chunks:
        lines.append(f"  Total chunks: {len(chunks)}")
        for i, chunk in enumerate(chunks[:3]):  # Show first 3
            lines.append(f"  Chunk {i+1}: {chunk['start']}-{chunk['end']} ({chunk['length']} chars)")
        if len(chunks) > 3:
            lines.append(f"  ... and {len(chunks) - 3} more chunks")
    else:
        lines.append("  No chunking performed")
    lines.append("")
    
    # 12. Entity Density Metrics
    lines.append("12. ENTITY DENSITY METRICS")
    lines.append("-" * 40)
    density = metadata.get('entity_density', {})
    for key, value in density.items():
        lines.append(f"  {key}: {value}")
    lines.append("")
    
    # 13. Resolution Decisions Log
    lines.append("13. RESOLUTION DECISIONS LOG")
    lines.append("-" * 40)
    decisions = metadata.get('resolution_decisions', [])
    if decisions:
        for decision in decisions[:10]:  # Show first 10
            lines.append(f"  \"{decision['entity']}\" matched with \"{decision['matched_with']}\"")
            lines.append(f"    Rule: {decision['rule']}, Similarity: {decision['similarity']}")
        if len(decisions) > 10:
            lines.append(f"  ... and {len(decisions) - 10} more decisions")
    else:
        lines.append("  No resolution decisions made")
    lines.append("")
    
    # 14. Model Information
    lines.append("14. MODEL INFORMATION")
    lines.append("-" * 40)
    model_info = metadata.get('model_info', {})
    for key, value in model_info.items():
        lines.append(f"  {key}: {value}")
    lines.append("")
    
    # 15. Warning/Anomaly Flags
    lines.append("15. WARNING/ANOMALY FLAGS")
    lines.append("-" * 40)
    anomalies = metadata.get('anomalies', [])
    if anomalies:
        for anomaly in anomalies:
            if anomaly['type'] == 'low_confidence':
                lines.append(f"  Low confidence: \"{anomaly['entity']}\" (score: {anomaly['score']})")
            elif anomaly['type'] == 'unusually_long':
                lines.append(f"  Unusually long: \"{anomaly['entity'][:50]}...\" (length: {anomaly['length']})")
    else:
        lines.append("  No anomalies detected")
    lines.append("")
    
    lines.append("=" * 80)
    lines.append("END OF METADATA REPORT")
    lines.append("=" * 80)
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description='SpaCy pipeline for PII detection and anonymization'
    )
    
    parser.add_argument('--input', type=str, default='data/text.txt',
                        help='Input text file')
    parser.add_argument('--output', type=str, default=None,
                        help='Output file (default: stdout)')
    parser.add_argument('--language', type=str, default='de',
                        help='Language code (de, en, etc.)')
    parser.add_argument('--threshold', type=float, default=0.3,
                        help='Confidence threshold (0.0-1.0)')
    parser.add_argument('--filter', action='store_true',
                        help='Apply false positive filtering')
    parser.add_argument('--filter-file', type=str, default='data/false_positives.json',
                        help='JSON file with false positives')
    parser.add_argument('--anonymize', action='store_true',
                        help='Output anonymized text with placeholders')
    parser.add_argument('--resolve-entities', action='store_true',
                        help='Resolve entity coreferences when anonymizing')
    parser.add_argument('--placeholder-format', type=str, default='brackets',
                        choices=['brackets', 'angles', 'double_angles', 'curly', 'custom'],
                        help='Placeholder format style (default: brackets)')
    
    args = parser.parse_args()
    
    # Read input text
    if not os.path.exists(args.input):
        print(f"Error: Input file {args.input} not found", file=sys.stderr)
        return 1
    
    with open(args.input, "r", encoding="utf-8") as f:
        text = f.read()
    
    # Start timing
    start_time = time.time()
    
    # Create pipeline
    nlp = create_pipeline(
        language=args.language,
        threshold=args.threshold,
        filter_false_positives=args.filter,
        filter_file=args.filter_file
    )
    
    # Process text
    print(f"Running spaCy pipeline: {nlp.pipe_names}", file=sys.stderr)
    processing_start = time.time()
    doc = nlp(text)
    processing_time = time.time() - processing_start
    print(f"✓ Found {len(doc.ents)} entities", file=sys.stderr)
    
    # Generate output based on mode
    if args.anonymize:
        # Get the placeholder format
        placeholder_format = PLACEHOLDER_FORMATS.get(args.placeholder_format, PLACEHOLDER_FORMATS['brackets'])
        
        # Anonymize the document with metadata collection
        anonymization_start = time.time()
        anonymized_text, mapping, anonymization_metadata = anonymize_doc(
            doc, 
            resolve_entities=args.resolve_entities,
            placeholder_format=placeholder_format,
            include_scores=True,  # Include scores in mapping
            return_metadata=True  # Get detailed metadata
        )
        anonymization_time = time.time() - anonymization_start
        
        # Calculate comprehensive statistics
        entities = []
        entity_type_counts = defaultdict(int)
        confidence_scores = defaultdict(list)
        
        for ent in doc.ents:
            score = ent._.confidence if (hasattr(ent._, "confidence") and 
                                        ent._.confidence is not None) else 1.0
            
            ent_dict = {
                "text": ent.text,
                "label": ent.label_,
                "start": ent.start_char,
                "end": ent.end_char,
                "score": round(score, 3)
            }
            entities.append(ent_dict)
            entity_type_counts[ent.label_] += 1
            confidence_scores[ent.label_].append(score)
        
        # Calculate confidence statistics
        confidence_stats = {}
        for label, scores in confidence_scores.items():
            if scores:
                confidence_stats[label] = {
                    "min": round(min(scores), 3),
                    "max": round(max(scores), 3),
                    "avg": round(sum(scores) / len(scores), 3)
                }
        
        # Calculate entity density metrics
        sentences = list(doc.sents)
        tokens = list(doc)
        entity_density = {
            "entities_per_sentence": round(len(doc.ents) / len(sentences), 2) if sentences else 0,
            "entities_per_100_tokens": round(len(doc.ents) * 100 / len(tokens), 2) if tokens else 0
        }
        
        # Get processing metadata from Doc
        processing_metadata = doc._.pii_processing_metadata if hasattr(doc._, 'pii_processing_metadata') else {}
        
        # Identify potential anomalies
        anomalies = []
        for ent in entities:
            # Low confidence entities
            if ent['score'] < 0.5:
                anomalies.append({
                    'type': 'low_confidence',
                    'entity': ent['text'],
                    'score': ent['score']
                })
            # Unusually long entities
            if len(ent['text']) > 50:
                anomalies.append({
                    'type': 'unusually_long',
                    'entity': ent['text'],
                    'length': len(ent['text'])
                })
        
        # Build comprehensive metadata
        metadata = {
            # 1. Entity mapping
            "entity_mapping": mapping,
            
            # 2. Individual entity occurrences
            "entities": entities,
            
            # 3. Entity clustering details
            "clustering": anonymization_metadata.get('clusters', []) if anonymization_metadata else [],
            
            # 4. Fuzzy match captures
            "fuzzy_matches": anonymization_metadata.get('fuzzy_matches', []) if anonymization_metadata else [],
            
            # 5. Confidence score statistics
            "confidence_stats": confidence_stats,
            
            # 6. Processing configuration
            "configuration": {
                "language": args.language,
                "threshold": args.threshold,
                "filter_false_positives": args.filter,
                "filter_file": args.filter_file,
                "resolve_entities": args.resolve_entities,
                "placeholder_format": args.placeholder_format,
                "chunk_size": processing_metadata.get('model_info', {}).get('chunk_size', 'unknown'),
                "overlap": processing_metadata.get('model_info', {}).get('overlap', 'unknown')
            },
            
            # 7. Entity type distribution
            "entity_distribution": dict(entity_type_counts),
            
            # 8. Filtered false positives
            "filtered_false_positives": processing_metadata.get('filtered_false_positives', []),
            
            # 9. Processing statistics
            "statistics": {
                "total_entities": len(doc.ents),
                "total_tokens": len(tokens),
                "total_sentences": len(sentences),
                "text_length": len(text),
                "processing_time_seconds": round(processing_time, 3),
                "anonymization_time_seconds": round(anonymization_time, 3),
                "total_time_seconds": round(time.time() - start_time, 3)
            },
            
            # 10. Overlapping entities removed
            "overlapping_entities_removed": processing_metadata.get('overlapping_entities_removed', []),
            
            # 11. Chunk boundaries
            "chunk_boundaries": processing_metadata.get('chunk_boundaries', []),
            
            # 12. Entity density metrics
            "entity_density": entity_density,
            
            # 13. Resolution decisions log
            "resolution_decisions": anonymization_metadata.get('resolution_decisions', []) if anonymization_metadata else [],
            
            # 14. Model information
            "model_info": processing_metadata.get('model_info', {}),
            
            # 15. Warning/anomaly flags
            "anomalies": anomalies,
            
            # Additional metadata
            "processing_timestamp": datetime.now().isoformat(),
            "input_file": args.input
        }
        
        # Determine output file names
        if args.output:
            base_name = os.path.splitext(args.output)[0]
            text_file = f"{base_name}.txt"
            meta_file = f"{base_name}_meta.json"
        else:
            text_file = "anonymized.txt"
            meta_file = "anonymized_meta.json"
        
        # Write anonymized text
        with open(text_file, "w", encoding="utf-8") as f:
            f.write(anonymized_text)
        print(f"✓ Anonymized text saved to {text_file}", file=sys.stderr)
        
        # Write metadata as JSON
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        print(f"✓ Metadata saved to {meta_file}", file=sys.stderr)
    
    else:
        # Standard spaCy JSON output with GLiNER scores
        doc_json = doc.to_json()
        
        # Add entities with GLiNER confidence scores
        entities_with_scores = []
        for ent in doc.ents:
            # Get confidence score, using 1.0 as fallback if None
            score = ent._.confidence if (hasattr(ent._, "confidence") and 
                                        ent._.confidence is not None) else 1.0
            
            ent_dict = {
                "text": ent.text,
                "label": ent.label_,
                "start": ent.start_char,
                "end": ent.end_char,
                "token_start": ent.start,
                "token_end": ent.end,
                "score": round(score, 3)
            }
            entities_with_scores.append(ent_dict)
        
        # Add enhanced entities to output
        doc_json["entities_with_scores"] = entities_with_scores
        
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(doc_json, f, ensure_ascii=False, indent=2)
            print(f"Results saved to {args.output}", file=sys.stderr)
        else:
            print(json.dumps(doc_json, ensure_ascii=False, indent=2))
    
    return 0


if __name__ == "__main__":
    sys.exit(main())