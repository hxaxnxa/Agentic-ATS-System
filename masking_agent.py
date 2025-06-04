import re
import random
import uuid
from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
from presidio_analyzer.nlp_engine import NlpEngineProvider
from pii_store_mongo import store_mapping_with_id, does_collection_id_exist

class PIIMasker:
    def __init__(self):
        # Configure Presidio to use en_core_web_sm
        configuration = {
            "nlp_engine_name": "spacy",
            "models": [
                {"lang_code": "en", "model_name": "en_core_web_sm"}
            ]
        }
        provider = NlpEngineProvider(nlp_configuration=configuration)
        nlp_engine = provider.create_engine()
        
        # Initialize AnalyzerEngine for address only
        self.analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["en"])
        
        # Indian address pattern
        address_pattern = r"\b\d{1,5}\s+[A-Za-z0-9\s.,/-]+,\s*[A-Za-z\s]+,\s*[A-Za-z\s]+,\s*[A-Z]{2}\s*\d{6}\b"
        address_recognizer = PatternRecognizer(
            supported_entity="ADDRESS",
            patterns=[Pattern("address", address_pattern, 0.9)]
        )
        self.analyzer.registry.add_recognizer(address_recognizer)
        
        self.generated_masked_values = set()

    def _generate_unique_collection_id(self):
        while True:
            new_id = str(uuid.uuid4())
            if not does_collection_id_exist(new_id):
                return new_id

    def _generate_unique_masked_value(self, entity_type):
        for _ in range(100):
            masked_value = f"<{entity_type}_{random.randint(1000, 9999)}>"
            if masked_value not in self.generated_masked_values:
                self.generated_masked_values.add(masked_value)
                return masked_value
        raise Exception("Could not generate unique masked value")

    def mask_text(self, text):
        collection_id = self._generate_unique_collection_id()
        mappings = {}
        masked_text = text

        # Step 1: Mask addresses using Presidio
        results = self.analyzer.analyze(text=text, language='en', entities=["ADDRESS"])
        for res in results:
            if res.score > 0.6:
                original_value = text[res.start:res.end]
                masked_value = self._generate_unique_masked_value(res.entity_type)
                mappings[masked_value] = original_value
                store_mapping_with_id(collection_id, masked_value, original_value)

        # Step 2: Mask phone numbers and emails using regex
        regex_patterns = {
            "PHONE": r"\b(?:\+91\s?|0)?[6-9]\d{9}\b",
            "EMAIL": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
        }

        for key, pattern in regex_patterns.items():
            for match in re.finditer(pattern, text):
                original_value = match.group(0)
                if original_value not in mappings.values():
                    masked_value = self._generate_unique_masked_value(key)
                    mappings[masked_value] = original_value
                    store_mapping_with_id(collection_id, masked_value, original_value)

        # Replace original values with masked values
        for masked, original in mappings.items():
            masked_text = masked_text.replace(original, masked)

        return masked_text, mappings, collection_id

# Interface for app.py
masker = PIIMasker()
def mask_text(text):
    return masker.mask_text(text)