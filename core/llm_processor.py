import logging
import json
import ollama
try:
    from ..config import OLLAMA_BASE_URL, OLLAMA_MODEL
except ImportError:
    OLLAMA_BASE_URL = "http://localhost:11434"
    OLLAMA_MODEL = "llama3"

logger = logging.getLogger(__name__)

# --- Prompts ---

SYSTEM_PROMPT_REFINE = """You are an elite Cyber Intelligence Analyst. 
Your task is to refine a user's natural language query into effective search operators or keywords for Dark Web search engines (Ahmia, Torch, etc.).
- Remove unnecessary words.
- Focus on specific identifiers (email domains, leak keywords, specific market names).
- Return ONLY the refined query string.
- Do not explain.
"""

SYSTEM_PROMPT_FILTER = """You are a Threat Hunter.
Evaluate the following search result snippets against the user's investigation goal.
Return a JSON object with 'relevance_score' (0-10) and 'reason' (short string).
Target: {query}
Snippet: {snippet}
"""

SYSTEM_PROMPT_SUMMARY = """You are a Senior Intelligence Officer.
Synthesize the provided search results into a cohesive investigation summary.
- Highlight key findings (PII, potential threats, actor handles).
- Connect dots between different results.
- Be objective and concise.
- Use Markdown formatting.
"""

class LLMProcessor:
    def __init__(self, model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL):
        self.model = model
        # The ollama python client uses OLLAMA_HOST env var, but we can also set client explicitly if needed.
        # For now, we rely on the standard client which picks up defaults.
        # If base_url is custom and not default, we might need to configure Client.
        self.client = ollama.Client(host=base_url)

    def chat_simple(self, system, user_msg):
        try:
            response = self.client.chat(model=self.model, messages=[
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': user_msg},
            ])
            return response['message']['content']
        except Exception as e:
            logger.error(f"LLM interaction failed: {e}")
            return None

    def refine_query(self, user_query):
        """
        Refines a user's natural language query into a keyword-dense search query.
        """
        logger.info(f"Refining query: {user_query}")
        refined = self.chat_simple(SYSTEM_PROMPT_REFINE, user_query)
        # Clean up tags if LLM ignores instructions
        if refined:
            return refined.strip().strip('"')
        return user_query

    def assess_relevance(self, query, snippet):
        """
        Returns (score, reason) for a result snippet.
        """
        prompt = SYSTEM_PROMPT_FILTER.format(query=query, snippet=snippet)
        try:
            resp = self.chat_simple("You are a JSON-speaking API.", prompt)
            # Try to parse JSON. 
            # LLMs are notoriously bad at strict JSON without grammar constraints.
            # We'll use a heuristic or just expect the LLM to do its best.
            # For robustness, we might want to use a specific 'format="json"' if Ollama supports it (it does in newer versions).
            
            # attempting to force JSON mode in call if supported, logic below is generic
            import re
            json_match = re.search(r'\{.*\}', resp, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                return data.get('relevance_score', 0), data.get('reason', 'Parsed from LLM')
            return 0, "Failed to parse LLM response"
        except Exception as e:
            return 0, f"Error: {e}"

    def generate_report(self, query, results_data):
        """
        Generates a markdown summary of the investigation.
        """
        # Collapse results into a text blob
        context_parts = []
        for r in results_data[:20]: # Limit context
            # Strict truncation of snippets to 200 chars to avoid overflowing context
            snip = r.get('snippet', '')
            if len(snip) > 300: snip = snip[:300] + "..."
            context_parts.append(f"- [{r.get('title', 'No Title')}]({r.get('link')})\n  Snippet: {snip}")
        
        context = "\n".join(context_parts)
        prompt = f"Investigation Target: {query}\n\nData Gathered:\n{context}"
        
        return self.chat_simple(SYSTEM_PROMPT_SUMMARY, prompt)

if __name__ == "__main__":
    params = {'model': 'llama3'} # test
    # basic test
    logger.basicConfig(level=logging.INFO)
    try:
        proc = LLMProcessor()
        print(proc.refine_query("find me credit cards related to chase bank"))
    except Exception as e:
        print(f"Skipping test, Ollama might not be running: {e}")
