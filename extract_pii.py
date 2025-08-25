#!/usr/bin/env python3
"""
CLI for PII detection and anonymization
"""

import argparse
import json
import os
import sys
from pii_detector import create_pipeline, anonymize_doc


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
    
    args = parser.parse_args()
    
    # Read input text
    if not os.path.exists(args.input):
        print(f"Error: Input file {args.input} not found", file=sys.stderr)
        return 1
    
    with open(args.input, "r", encoding="utf-8") as f:
        text = f.read()
    
    # Create pipeline
    nlp = create_pipeline(
        language=args.language,
        threshold=args.threshold,
        filter_false_positives=args.filter,
        filter_file=args.filter_file
    )
    
    # Process text
    print(f"Running spaCy pipeline: {nlp.pipe_names}", file=sys.stderr)
    doc = nlp(text)
    print(f"✓ Found {len(doc.ents)} entities", file=sys.stderr)
    
    # Generate output based on mode
    if args.anonymize:
        # Anonymize the document
        anonymized_text, mapping = anonymize_doc(
            doc, 
            resolve_entities=args.resolve_entities,
            include_scores=False  # Don't include scores in mapping
        )
        
        # Extract all entities with their details
        entities = []
        for ent in doc.ents:
            # Check if score exists - it should always be there from GLiNER
            if not hasattr(ent._, "confidence"):
                raise ValueError(f"Entity missing GLiNER confidence score: {ent.text}")
            
            ent_dict = {
                "text": ent.text,
                "label": ent.label_,
                "start": ent.start_char,
                "end": ent.end_char,
                "score": round(ent._.confidence, 3)  # No fallback - must be from GLiNER
            }
            entities.append(ent_dict)
        
        result = {
            "anonymized_text": anonymized_text,
            "entity_mapping": mapping,
            "entities": entities,  # All individual entity occurrences with scores
            "statistics": {
                "total_entities": len(doc.ents),
                "total_tokens": len(doc),
                "total_sentences": len(list(doc.sents)),
                "entity_resolution": "enabled" if args.resolve_entities else "disabled"
            }
        }
        
        # Output result
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"Anonymized result saved to {args.output}", file=sys.stderr)
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
    
    else:
        # Standard spaCy JSON output with GLiNER scores
        doc_json = doc.to_json()
        
        # Add entities with GLiNER confidence scores
        entities_with_scores = []
        for ent in doc.ents:
            # Check if score exists - it should always be there from GLiNER
            if not hasattr(ent._, "confidence"):
                raise ValueError(f"Entity missing GLiNER confidence score: {ent.text}")
            
            ent_dict = {
                "text": ent.text,
                "label": ent.label_,
                "start": ent.start_char,
                "end": ent.end_char,
                "token_start": ent.start,
                "token_end": ent.end,
                "score": round(ent._.confidence, 3)  # No fallback - must be from GLiNER
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