"""
PII Masking (Phase 12 extension - Evidence Sanitization)
Detects and masks sensitive info in extracted evidence text BEFORE it's
processed further, per the case study's requirement: mask first, analyze
the masked version only. Also masks the known client name as a custom
recognizer, since Presidio's built-ins don't know "Cadence" is sensitive.
"""
from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
from presidio_anonymizer import AnonymizerEngine
import sys, os as _os
sys.path.append(_os.path.join(_os.path.dirname(__file__), "..", "agents"))

analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()

# Custom recognizer: the client's company name isn't a "standard" PII type,
# so Presidio wouldn't catch it without being told explicitly.
client_name_pattern = Pattern(name="client_name_pattern", regex=r"\bCadence(?:\s+Ltd\.?)?\b", score=0.9)
client_name_recognizer = PatternRecognizer(supported_entity="CLIENT_NAME", patterns=[client_name_pattern])
analyzer.registry.add_recognizer(client_name_recognizer)
ip_pattern = Pattern(name="ip_pattern", regex=r"\b(?:\d{1,3}\.){3}\d{1,3}\b", score=0.85)
ip_recognizer = PatternRecognizer(supported_entity="IP_ADDRESS", patterns=[ip_pattern])
analyzer.registry.add_recognizer(ip_recognizer)

ENTITIES_TO_MASK = ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "CLIENT_NAME", "IP_ADDRESS"]

def mask_evidence_text(text):
    results = analyzer.analyze(text=text, entities=ENTITIES_TO_MASK, language="en")
    masked = anonymizer.anonymize(text=text, analyzer_results=results)
    return masked.text, len(results)


if __name__ == "__main__":
    from evidence_extraction import extract_evidence_text
    import os

    folder = "data/raw"
    for filename in sorted(os.listdir(folder)):
        path = os.path.join(folder, filename)
        raw_text = extract_evidence_text(path)
        if raw_text.startswith("[Unsupported"):
            continue
        masked_text, count = mask_evidence_text(raw_text)
        print(f"\n{'='*60}\n{filename} — {count} sensitive items masked\n{'='*60}")
        print(masked_text[:600])