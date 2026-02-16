import re
import logging

logger = logging.getLogger(__name__)

# --- Regex Patterns ---
# Comprehensive regex patterns for common OSINT artifacts
PATTERNS = {
    "email": r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
    "ipv4": r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b',
    # Bitcoin: Legacy (1...), Script (3...), SegWit (bc1...)
    "btc_address": r'\b(bc1|[13])[a-zA-HJ-NP-Z0-9]{25,39}\b',
    "xmr_address": r'\b4[0-9AB][1-9A-HJ-NP-Za-km-z]{93}\b',
    "eth_address": r'\b0x[a-fA-F0-9]{40}\b',
    "onion_v3": r'[a-z2-7]{56}\.onion',
    "onion_v2": r'[a-z2-7]{16}\.onion',
    "ssn": r'\b(?!000|666|9\d{2})([0-8]\d{2}|7([0-6]\d|7[012]))[- ]?(?!00)\d{2}[- ]?(?!0000)\d{4}\b',
    # Basic Credit Card (Major brands) - High false positive potential without Luhn
    "credit_card": r'\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|3(?:0[0-5]|[68][0-9])[0-9]{11}|6(?:011|5[0-9]{2})[0-9]{12}|(?:2131|1800|35\d{3})\d{11})\b',
    "api_key_generic": r'\b[a-zA-Z0-9]{32,}\b', # Too broad? Maybe limit to specific prefixes
    "aws_access_key": r'\bAKIA[0-9A-Z]{16}\b',
    "google_api_key": r'\bAIza[0-9A-Za-z-_]{35}\b'
}

class Analyzer:
    def __init__(self):
        self.compiled_patterns = {name: re.compile(regex) for name, regex in PATTERNS.items()}

    def analyze_content(self, text):
        """
        Scans text for all defined patterns and returns a dictionary of findings.
        """
        results = {}
        for name, pattern in self.compiled_patterns.items():
            matches = pattern.findall(text)
            if matches:
                 # Deduplicate matches
                results[name] = list(set(matches))
        return results

    def extract_artifacts(self, text):
        """
        Returns a flat list of artifact objects for easier storage.
        """
        raw_results = self.analyze_content(text)
        artifacts = []
        for type_, values in raw_results.items():
            for val in values:
                # Basic context extraction could go here (grab surrounding chars)
                artifacts.append({
                    "type": type_,
                    "value": val,
                    "context": "" # TODO: Add context window (e.g. +/- 50 chars)
                })
        return artifacts

    def extract_context(self, text, keyword, window=100):
        """
        Extracts a snippet of text surrounding a keyword.
        Returns a list of unique snippets.
        """
        if not text or not keyword: return []
        
        # Escape keyword for regex
        escaped_key = re.escape(keyword)
        # Regex to find keyword with window, case-insensitive
        pattern = re.compile(f".{{0,{window}}}{escaped_key}.{{0,{window}}}", re.IGNORECASE | re.DOTALL)
        
        matches = pattern.findall(text)
        # Clean up whitespace
        clean_matches = [m.replace("\n", " ").strip() for m in matches]
        return list(set(clean_matches))
if __name__ == "__main__":
    text = "Contact me at test@example.com or send BTC to 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa. Also 127.0.0.1"
    analyzer = Analyzer()
    print(analyzer.analyze_content(text))
