import logging
import re
import uuid
import time
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
from .tor_handler import TorHandler

try:
    from ..config import MAX_WORKERS, RECURSION_DEPTH, REQUEST_TIMEOUT
except ImportError:
    MAX_WORKERS = 5
    RECURSION_DEPTH = 1
    REQUEST_TIMEOUT = 45

logger = logging.getLogger(__name__)

# List of Search Engines
SEARCH_ENGINES = [
    {"name": "Ahmia", "url": "http://juhanurmihxlp77nkq76byazcldy2hlmovfu2epvl5ankdibsot4csyd.onion/search/?q={query}"},
    {"name": "Daniel", "url": "http://danielas3rtn54uwmofdo3x2bsdifr47huadnmbg7lgn5d4fjgi7oe6a.onion/onions.php?q={query}"},
    {"name": "Torch", "url": "http://xmh57jrzrnw6insl.onion/4a1f6b371c/search.cgi?q={query}"},
    {"name": "Haystak", "url": "http://haystak5njsmn2hqkewecpaxetahtwhsbsa64jom2k22z5afxhnpxfid.onion/?q={query}"},
    {"name": "OnionLand", "url": "http://3bbad7fauom4d6sgppalyqddsqbf5u5p56b5k5uk2zxsy3d6ey2jobad.onion/search?q={query}"}
]

class Crawler:
    def __init__(self, tor_handler=None):
        self.tor_handler = tor_handler or TorHandler()
        self.session = self.tor_handler.get_session()

    def fetch_page(self, url):
        try:
            logger.info(f"Fetching: {url}")
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    def parse_search_results(self, html, engine_name):
        results = []
        soup = BeautifulSoup(html, 'html.parser')
        
        # Generic heuristic for search results: look for links with interesting text
        # This can be specialized per engine if needed
        for a in soup.find_all('a', href=True):
            href = a['href']
            text = a.get_text(strip=True)
            
            # Simple validation for .onion links
            if '.onion' in href and len(text) > 3:
                # Resolve relative URLs
                if href.startswith('/'):
                    # This assumes we know the base domain, which is tricky in generic parsing
                    # For now, let's just grab absolute onion links or keep relative if we can
                    pass 
                
                # Check if it's a valid onion v3 link (56 chars) or v2 (16 chars)
                onion_match = re.search(r'(https?://[a-z2-7]{16,56}\.onion)', href)
                if onion_match:
                    full_link = onion_match.group(1)
                    results.append({
                        "title": text,
                        "link": full_link,
                        "engine": engine_name,
                        "snippet": "" # Future: extract snippet
                    })
        return results

    def search_single_engine(self, engine, query):
        url = engine['url'].format(query=query)
        html = self.fetch_page(url)
        if html:
            return self.parse_search_results(html, engine['name'])
        return []

    def search(self, query):
        """
        Queries all configured search engines concurrently.
        Automatically enforces .onion context if not present.
        """
        # Global .onion enforcement
        if query and "site:onion" not in query:
             query = f"{query} site:onion"
             
        all_results = []
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_engine = {
                executor.submit(self.search_single_engine, engine, query): engine 
                for engine in SEARCH_ENGINES
            }
            
            for future in as_completed(future_to_engine):
                engine = future_to_engine[future]
                try:
                    results = future.result()
                    logger.info(f"Engine {engine['name']} found {len(results)} results.")
                    all_results.extend(results)
                except Exception as e:
                    logger.error(f"Engine {engine['name']} failed: {e}")
        
        # Deduplication
        unique_results = {res['link']: res for res in all_results}.values()
        return list(unique_results)

    def crawl_deep(self, url, depth=1):
        """
        Recursively crawls a URL to the specified depth.
        depth=0 means just fetch this page.
        depth=1 means fetch this page and followed links.
        """
        if depth < 0:
            return []
            
        content = self.fetch_page(url)
        if not content:
            return []
            
        start_data = [{"url": url, "content": content, "depth": depth}]
        
        if depth > 0:
            soup = BeautifulSoup(content, 'html.parser')
            links = [a['href'] for a in soup.find_all('a', href=True) if '.onion' in a['href']]
            # Limit number of sub-links to avoid explosion?
            
            # Simple recursion
            # Note: This can be exponential. In production, need a visited set shared across calls.
            # For now, implementing shallow depth (depth=1 usually means just the page itself in some contexts, 
            # but here let's say depth=1 means 'this page').
            # If RECURSION_DEPTH is 1 (from config), we usually just want the search result page content.
            pass
            
        return start_data

    def scrape_direct(self, urls):
        """
        Directly scans a list of URLs for forensic artifacts.
        Extracts: Tech Stack, Headers, Comments, Crypto Wallets, and Content Hash.
        """
        import hashlib
        from bs4 import Comment
        results = []
        
        # Crypto Regex Patterns
        CRYPTO_REGEX = {
            "BTC": r'\b(bc1|[13])[a-zA-HJ-NP-Z0-9]{25,39}\b',
            "ETH": r'\b0x[a-fA-F0-9]{40}\b',
            "XMR": r'\b4[0-9AB][1-9A-HJ-NP-Za-km-z]{93}\b'
        }
        
        def process_url(url_input):
            url_input = url_input.strip()
            if not url_input: return None
            
            # Simple heuristic: try to extract http[s]://...onion...
            # If not found, assume it might be just text, but let's try to be smart.
            match = re.search(r'(https?://[a-zA-Z0-9.-]+\.onion\S*)', url_input)
            if match:
                url = match.group(1)
            else:
                # If no http/https, maybe it's just domain.onion...
                match_domain = re.search(r'([a-zA-Z0-9.-]+\.onion\S*)', url_input)
                if match_domain:
                    url = "http://" + match_domain.group(1)
                else:
                    url = url_input # Fallback
            
            # Ensure protocol
            if not url.startswith("http"): url = "http://" + url
            
            try:
                # 1. Check Liveness & Latency
                session = self.tor_handler.get_session()
                start_time = time.time()
                resp = session.get(url, timeout=30)
                latency = round((time.time() - start_time), 2)
                
                # 2. Tech Stack Fingerprinting (Headers)
                headers = resp.headers
                server_sig = headers.get("Server", "Unknown")
                powered_by = headers.get("X-Powered-By", "")
                tech_stack = f"{server_sig} {powered_by}".strip()
                
                # 3. Content Hashing (Change Detection)
                content_hash = hashlib.md5(resp.content).hexdigest()
                
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    title = soup.title.string.strip() if soup.title else url
                    text = soup.get_text()
                    
                    # 4. "Ghost Text" (HTML Comments)
                    comments = soup.find_all(string=lambda text: isinstance(text, Comment))
                    ghost_text = [c.strip() for c in comments if len(c.strip()) > 5] # Filter short noise
                    
                    # 5. Crypto Extraction
                    wallets = []
                    for c_type, pattern in CRYPTO_REGEX.items():
                        found = list(set(re.findall(pattern, text)))
                        for f in found:
                            wallets.append(f"{c_type}: {f}")
                            
                    # 6. Extract Forms (Existing)
                    forms = []
                    for f in soup.find_all("form"):
                        method = f.get("method", "get").upper()
                        inputs = [i.get("name") for i in f.find_all("input") if i.get("name")]
                        forms.append(f"{method} Form: {inputs}")
                    
                    # Construct Snippet
                    snippet_parts = []
                    if wallets: snippet_parts.append(f"💰 Wallets: {len(wallets)}")
                    if ghost_text: snippet_parts.append(f"👻 Hidden Comments: {len(ghost_text)}")
                    if forms: snippet_parts.append(f"🔑 Forms: {len(forms)}")
                    snippet_parts.append(text[:200].replace("\n", " "))
                    
                    return {
                        "title": f"[LIVE {latency}s] {title}",
                        "link": url,
                        "engine": "Direct",
                        "snippet": " | ".join(snippet_parts),
                        "tech_stack": tech_stack,
                        "hash": content_hash,
                        "wallets": wallets,
                        "comments": ghost_text
                    }
                else:
                    return {
                        "title": f"[OFFLINE {resp.status_code}] {url}",
                        "link": url,
                        "engine": "Direct",
                        "snippet": "Site is offline.",
                        "tech_stack": "N/A",
                        "hash": "N/A",
                        "wallets": [],
                        "comments": []
                    }
            except Exception as e:
                # Sanitize error message
                err_msg = str(e)
                if "SOCKSHTTPConnectionPool" in err_msg or "NewConnectionError" in err_msg:
                    snippet = "⚠️ Connection Failed: Tor could not reach this site (Offline or Invalid)."
                elif "ReadTimeout" in err_msg or "ConnectTimeout" in err_msg:
                    snippet = "⏱️ Connection Timed Out."
                else:
                    snippet = f"⚠️ Error: {err_msg[:100]}..." # Truncate generic errors

                return {
                    "title": f"[ERROR] {url}",
                    "link": url,
                    "engine": "Direct",
                    "snippet": snippet,
                    "tech_stack": "Error",
                    "hash": "Error",
                    "wallets": [],
                    "comments": []
                }

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(process_url, u) for u in urls]
            for future in as_completed(futures):
                if res := future.result():
                    results.append(res)
        return results

    def _deduplicate(self, results):
        """
        Deduplicates results based on URL link.
        """
        unique = {res['link']: res for res in results}
        return list(unique.values())

    def search_person(self, query):
        """
        Performs a deep targeted search for a person using a single query string.
        Generates multiple dorks across all categories automatically.
        """
        if not query: return []
        
        # Base selector
        sel = f'"{query.strip()}"'
        queries = []
        
        # 1. General & Exact
        queries.append(f"{sel} site:onion")
        
        # 2. Leaks/Breaches
        queries.append(f"{sel} (password OR hash OR dump OR database OR leak) site:onion")
        queries.append(f"{sel} site:paste") # 'site:paste' usually finds onion pastes too, but let's be strict if needed. 
        # Actually, for 'site:paste' it's a specific dork often used in these engines for their own internal pastebins or general paste sites.
        # To be safe and strict as requested:
        queries.append(f"{sel} (paste OR privnote OR zerobin) site:onion")
        
        # 3. Media/Visuals
        queries.append(f"{sel} (jpg OR png OR jpeg OR mp4 OR mov OR avi OR zip OR rar) site:onion")
        queries.append(f"{sel} \"DCIM\" site:onion")
        
        # 4. Social/Chats
        queries.append(f"{sel} (chat OR log OR message OR conversation OR profile) site:onion")
        queries.append(f"{sel} \"last seen\" site:onion")
        
        # 5. Dating
        queries.append(f"{sel} (dating OR match OR tinder OR bumble OR profile OR \"looking for\") site:onion")
                
        # Deduplicate
        queries = list(set(queries))
        logger.info(f"Generated {len(queries)} person-search dorks for '{query}': {queries}")
        
        # Execute Searches
        all_results = []
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_query = {executor.submit(self.search, q): q for q in queries}
            for future in as_completed(future_to_query):
                q = future_to_query[future]
                try:
                    res = future.result()
                    for r in res: r['context_query'] = q
                    all_results.extend(res)
                except Exception as e:
                    logger.error(f"Dork '{q}' failed: {e}")
                    
        return self._deduplicate(all_results)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    crawler = Crawler()
    # results = crawler.search("test")
    # print(f"Total unique results: {len(results)}")
