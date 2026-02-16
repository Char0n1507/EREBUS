import argparse
import logging
import sys
import time
from core.tor_handler import TorHandler
from core.crawler import Crawler
from core.storage import StorageManager
from core.llm_processor import LLMProcessor
from core.analyzer import Analyzer

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("ErebusCLI")

def main():
    parser = argparse.ArgumentParser(description="Erebus: Advanced Dark Web OSINT Tool")
    parser.add_argument("-q", "--query", required=True, help="Search query")
    parser.add_argument("--refine", action="store_true", help="Use LLM to refine the query before searching")
    parser.add_argument("--limit", type=int, default=10, help="Max results to process")
    parser.add_argument("--tor-check", action="store_true", help="Check Tor connection before starting")
    parser.add_argument("--report", action="store_true", help="Generate a summary report after crawling")
    
    args = parser.parse_args()
    
    # 1. Initialize Components
    logger.info("Initializing Erebus components...")
    tor = TorHandler()
    
    if args.tor_check:
        logger.info("Checking Tor connection...")
        success, ip = tor.check_connection()
        if not success:
            logger.critical("Tor connection failed! Ensure Tor is running (port 9050).")
            sys.exit(1)
        logger.info(f"Tor active. IP: {ip}")

    crawler = Crawler(tor_handler=tor)
    storage = StorageManager()
    llm = LLMProcessor()
    analyzer = Analyzer()
    
    # 2. Query Refinement
    search_query = args.query
    if args.refine:
        logger.info(f"Refining query: '{search_query}'...")
        refined = llm.refine_query(search_query)
        logger.info(f"Refined query: '{refined}'")
        search_query = refined
        
    # 3. Create Investigation
    inv_id = storage.create_investigation(name=f"CLI Run: {args.query}", query=search_query)
    logger.info(f"Created Investigation ID: {inv_id}")
    
    # 4. Crawl
    logger.info(f"Starting crawl for: '{search_query}'")
    results = crawler.search(search_query)
    logger.info(f"Found {len(results)} raw results.")
    
    # 5. Process & Save
    processed_count = 0
    results_for_report = []
    
    for res in results[:args.limit]:
        # Save to DB
        res_id = storage.add_result(inv_id, res)
        
        # Analyze Artifacts (on snippet + title + link)
        # In a real deep crawl, we'd fetch the content first.
        # Here we just analyze what we have from the search engine.
        text_to_analyze = f"{res.get('title', '')} {res.get('snippet', '')}"
        artifacts = analyzer.extract_artifacts(text_to_analyze)
        
        for art in artifacts:
            storage.add_artifact(res_id, art['type'], art['value'], art.get('context', ''))
            
        logger.info(f"Saved result {res_id} with {len(artifacts)} artifacts.")
        results_for_report.append(res)
        processed_count += 1
        
    logger.info(f"Processed {processed_count} results.")
    
    # 6. Reporting
    if args.report and processed_count > 0:
        logger.info("Generating LLM Report...")
        report = llm.generate_report(search_query, results_for_report)
        if report:
            print("\n" + "="*40)
            print("EREBUS INVESTIGATION REPORT")
            print("="*40)
            print(report)
            print("="*40 + "\n")
        else:
            logger.error("Failed to generate report (LLM issue?).")

if __name__ == "__main__":
    main()
