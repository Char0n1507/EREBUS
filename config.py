import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# --- Tor Configuration ---
# proxy URL for requests
TOR_PROXY_URL = os.getenv("TOR_PROXY_URL", "socks5h://127.0.0.1:9050")
# Tor control port for circuit rotation (requires Tor to be configured with ControlPort)
TOR_CONTROL_PORT = int(os.getenv("TOR_CONTROL_PORT", "9051"))
TOR_PASSWORD = os.getenv("TOR_PASSWORD", None) # Set if your Tor control port has a password

# --- LLM Configuration ---
# Base URL for Ollama
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
# Model to use (default to llama3, but user can change)
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

# --- Search Configuration ---
# Max concurrent threads for crawling
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "5"))
# Request timeout in seconds (Tor can be slow)
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "45"))
# Global recursion depth limit (1 = search results only, 2 = crawl one link deep)
RECURSION_DEPTH = int(os.getenv("RECURSION_DEPTH", "1"))

# --- Database ---
DB_URL = "sqlite:///erebus.db"

# --- Paths ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(BASE_DIR, "reports")

# Ensure reports directory exists
os.makedirs(REPORTS_DIR, exist_ok=True)
