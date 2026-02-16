import streamlit as st
import pandas as pd
import importlib
import time
import os
import uuid
import streamlit.components.v1 as components

# Import Core Modules
import core.tor_handler
importlib.reload(core.tor_handler)
from core.tor_handler import TorHandler

import core.crawler
importlib.reload(core.crawler)
from core.crawler import Crawler

import core.storage
importlib.reload(core.storage)
from core.storage import StorageManager, Artifact

import core.llm_processor
importlib.reload(core.llm_processor)
from core.llm_processor import LLMProcessor

import core.analyzer
importlib.reload(core.analyzer)
from core.analyzer import Analyzer

import core.reporter
importlib.reload(core.reporter)
from core.reporter import Reporter

import app_ui.graph_viz
importlib.reload(app_ui.graph_viz)
from app_ui.graph_viz import generate_network_graph

# Page Config
st.set_page_config(
    page_title="Erebus - Dark Web OSINT",
    page_icon="👁️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    /* --- GLOBAL THEME --- */
    .stApp {
        background-color: #000000 !important; /* True Black */
        color: #e0e0e0;
        font-family: 'Consolas', 'Menlo', 'Courier New', monospace;
    }
    
    /* --- TYPOGRAPHY --- */
    h1, h2, h3, h4, h5, h6 {
        color: #00ff41 !important; /* Matrix Green / Cyberpunk Neon */
        text-shadow: 0 0 5px rgba(0, 255, 65, 0.4);
        font-family: 'Consolas', monospace;
        letter-spacing: 1px;
        text-transform: uppercase;
        border-bottom: 1px solid #111;
        padding-bottom: 5px;
    }
    
    /* --- SIDEBAR --- */
    section[data-testid="stSidebar"] {
        background-color: #050505;
        border-right: 1px solid #1f1f1f;
    }
    
    /* --- BUTTONS --- */
    .stButton>button {
        background: #0a0a0a;
        border: 1px solid #00f2ea; /* Cyan Neon Border */
        color: #00f2ea;
        border-radius: 0px; /* Sharp edges for key aesthetic */
        font-family: 'Consolas', monospace;
        font-weight: bold;
        transition: all 0.3s ease;
        text-transform: uppercase;
        letter-spacing: 2px;
        box-shadow: 0 0 5px rgba(0, 242, 234, 0.2);
    }
    .stButton>button:hover {
        background: #00f2ea !important;
        color: #000 !important;
        box-shadow: 0 0 20px rgba(0, 242, 234, 0.9);
        transform: translateY(-2px);
    }
    
    /* --- PRIMARY INPUTS --- */
    .stTextInput>div>div>input, .stTextArea>div>div>textarea {
        background-color: #080808 !important;
        color: #00ff41 !important;
        border: 1px solid #333 !important;
        border-radius: 0px;
        font-family: 'Consolas', monospace;
    }
    .stTextInput>div>div>input:focus, .stTextArea>div>div>textarea:focus {
        border-color: #00ff41 !important;
        box-shadow: 0 0 10px rgba(0, 255, 65, 0.3);
    }
    
    /* --- CARDS / CONTAINERS --- */
    div[data-testid="stExpander"] {
        background-color: #040404;
        border: 1px solid #222;
        border-radius: 0px;
    }
    
    /* --- DATAFRAMES / TABLES --- */
    div[data-testid="stDataFrame"] {
        background-color: #0a0a0a;
        border: 1px solid #333;
    }
    
    /* --- ALERTS / INFO BOXES --- */
    .stAlert {
        background-color: #0a0a0a;
        border-left: 5px solid #ff0055; /* Cyberpunk Red accent */
        color: #ddd;
    }
    
    /* --- SCROLLBAR --- */
    ::-webkit-scrollbar {
        width: 10px;
    }
    ::-webkit-scrollbar-track {
        background: #000;
    }
    ::-webkit-scrollbar-thumb {
        background: #333;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: #00f2ea;
    }
</style>
""", unsafe_allow_html=True)

# Initialize Session State
if 'results' not in st.session_state: st.session_state.results = []
if 'artifacts' not in st.session_state: st.session_state.artifacts = []
if 'investigation_id' not in st.session_state: st.session_state.investigation_id = None
if 'graph_path' not in st.session_state: st.session_state.graph_path = None
if 'report_path' not in st.session_state: st.session_state.report_path = None
if 'search_mode' not in st.session_state: st.session_state.search_mode = None

# --- SHARED FUNCTIONS (Moved to Top) ---
def _process_results(raw_results, analyzer, status, limit):
    processed_results = []
    all_artifacts = []
    
    from collections import namedtuple
    ResultObj = namedtuple("ResultObj", ["id", "title", "url", "engine", "snippet"])
    ArtifactObj = namedtuple("ArtifactObj", ["id", "result_id", "type", "value", "context"])

    # Limit results
    to_process = raw_results[:limit]
    
    progress_bar = status.progress(0)
    for i, res in enumerate(to_process):
        r_obj = ResultObj(i, res.get('title'), res.get('link'), res.get('engine'), res.get('snippet'))
        processed_results.append(r_obj)
        
        arts = analyzer.extract_artifacts(f"{res.get('title')} {res.get('snippet')}")
        for j, a in enumerate(arts):
            all_artifacts.append(ArtifactObj(f"{i}_{j}", i, a['type'], a['value'], a.get('context')))
            
        progress_bar.progress((i + 1) / len(to_process))
    
    st.session_state.results = processed_results
    st.session_state.artifacts = all_artifacts
    status.update(label="Investigation Complete", state="complete", expanded=False)

def _run_search(query, mode, proxy, limit, use_llm):
    # Reset
    st.session_state.results = []
    st.session_state.results = []
    st.session_state.artifacts = []
    st.session_state.search_mode = "generic"
    
    status = st.status("Initializing Investigation...", expanded=True)
    try:
        tor = TorHandler(proxy_url=proxy)
        crawler = Crawler(tor_handler=tor)
        llm = LLMProcessor()
        analyzer = Analyzer()
        
        if use_llm and mode == "generic":
            status.write("🤖 Refining query with LLM...")
            refined_query = llm.refine_query(query)
        else:
            refined_query = query
        
        status.write(f"🕷️ Crawling Dark Web Engines: {refined_query}")
        raw_results = crawler.search(refined_query)
        
        _process_results(raw_results, analyzer, status, limit)
        
    except Exception as e:
        status.update(label="Error Occurred", state="error")
        st.error(f"Error: {e}")

def _run_direct(urls, proxy):
    st.session_state.results = []
    st.session_state.results = []
    st.session_state.artifacts = []
    st.session_state.search_mode = "direct"
    status = st.status("Processing Targets...", expanded=True)
    try:
        tor = TorHandler(proxy_url=proxy)
        crawler = Crawler(tor_handler=tor)
        analyzer = Analyzer()
        
        status.write(f"Pinging {len(urls)} URLs...")
        raw_results = crawler.scrape_direct(urls)
        
        # Enhanced Display for Direct Targets
        if raw_results:
            st.success(f"Scrape Complete! Analyzed {len(raw_results)} targets.")
            for res in raw_results:
                with st.expander(f"{res.get('title')} ({res.get('tech_stack', 'Unknown Stack')})", expanded=True):
                    cols = st.columns([3, 1])
                    with cols[0]:
                        st.markdown(f"**URL:** `{res.get('link')}`")
                        st.markdown(f"**Snippet:** {res.get('snippet')}")
                        
                        # Wallets
                        wallets = res.get('wallets', [])
                        if wallets:
                            st.markdown("##### 💰 Detected Wallets")
                            for w in wallets:
                                st.code(w, language="text")
                                
                        # Ghost Text
                        comments = res.get('comments', [])
                        if comments:
                            st.markdown("##### 👻 Ghost Text (Hidden Comments)")
                            for c in comments:
                                st.markdown(f"> *{c}*")
                                
                    with cols[1]:
                            st.write("Open Tor Browser manually.")

        # Persist results to session state for Reporting
        if raw_results:
            # We manually reconstruct result objects to avoid triggering the generic progress bar UI again
            from collections import namedtuple
            ResultObj = namedtuple("ResultObj", ["id", "title", "url", "engine", "snippet"])
            ArtifactObj = namedtuple("ArtifactObj", ["id", "result_id", "type", "value", "context"])
            
            processed_results = []
            all_artifacts = []
            
            for i, res in enumerate(raw_results):
                # result
                r_obj = ResultObj(i, res.get('title'), res.get('link'), res.get('engine'), res.get('snippet'))
                processed_results.append(r_obj)
                
                # artifacts (wallets, ghosts)
                for w in res.get('wallets', []):
                    all_artifacts.append(ArtifactObj(f"{i}_w", i, "Crypto Wallet", w, "Direct Scrape"))
                for c in res.get('comments', []):
                    all_artifacts.append(ArtifactObj(f"{i}_c", i, "Hidden Comment", c, "Direct Scrape"))
                if res.get('hash') and res.get('hash') != "N/A":
                    all_artifacts.append(ArtifactObj(f"{i}_h", i, "Content Hash", res.get('hash'), "Direct Scrape"))

            st.session_state.results = processed_results
            st.session_state.artifacts = all_artifacts
            
    except Exception as e:
        status.update(label="Error", state="error")
        st.error(f"Error: {e}")

def _run_person_search(query, proxy, limit, use_llm):
    st.session_state.results = []
    st.session_state.results = []
    st.session_state.artifacts = []
    st.session_state.search_mode = "person"
    
    status = st.status(f"Profiling Target: {query}...", expanded=True)
    try:
        tor = TorHandler(proxy_url=proxy)
        crawler = Crawler(tor_handler=tor)
        analyzer = Analyzer()
        
        status.write(f"🕷️ Generating dorks for auto-profiling...")
        raw_results = crawler.search_person(query)
        
        status.write(f"Found {len(raw_results)} potential matches. Analyzing...")
        _process_results(raw_results, analyzer, status, limit)
        
    except Exception as e:
        status.update(label="Error Occurred", state="error")
        st.error(f"Error: {e}")

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuration")
    
    st.subheader("Tor Connection")
    
    # Auto-detect Tor port if not already in session (and no env var override)
    if 'tor_proxy_val' not in st.session_state:
        env_proxy = os.getenv("TOR_PROXY_URL")
        if env_proxy:
            st.session_state.tor_proxy_val = env_proxy
        else:
            # Attempt auto-detection
            try:
                # Initialize handler without args triggers its internal auto-detect
                # because it defaults proxy_url=None
                detector = TorHandler() 
                st.session_state.tor_proxy_val = detector.proxy_url
            except Exception:
                st.session_state.tor_proxy_val = "socks5h://127.0.0.1:9050"

    tor_proxy = st.text_input("Tor Proxy URL", key="tor_proxy_val", help="e.g., socks5h://127.0.0.1:9150")
    
    if st.button("Check Tor Status"):
        with st.spinner(f"Checking {tor_proxy}..."):
            tor = TorHandler(proxy_url=tor_proxy)
            success, ip = tor.check_connection()
            if success:
                st.success(f"Connected! IP: {ip}")
            else:
                st.error(f"Failed. Error: {ip}")
                st.info("Ensure Tor Browser is open (opens port 9150) or Tor service is running (port 9050).")
                
    st.divider()
    st.subheader("Search Settings")
    limit = st.slider("Max Results", 10, 100, 20)
    use_llm = st.checkbox("Enable LLM Refinement", value=True)
    st.divider()
    st.info("Erebus v1.0\nCreated with ❤️ by Antigravity")

# Main Content
st.title("👁️ Erebus: AI-Powered Dark Web OSINT")
st.markdown("Search across multiple dark web engines, analyze content with LLMs, and visualize connections.")

# Tabs for Modes
tab_search, tab_direct, tab_person = st.tabs(["🔍 Search Engines", "🎯 Direct Targets", "👥 Person Search"])

# --- SEARCH TAB ---
with tab_search:
    query = st.text_input("Enter search query (e.g., 'data leak company.com', 'site:example.onion')", placeholder="Search target...")
    if st.button("🚀 Start Investigation", type="primary", key="btn_search"):
        if not query:
            st.warning("Please enter a query.")
        else:
            _run_search(query, "generic", tor_proxy, limit, use_llm)

# --- DIRECT TARGETS TAB ---
with tab_direct:
    st.info("Paste a list of .onion URLs to directly scrape and analyze them (one per line).")
    target_urls_input = st.text_area("Target URLs", height=150, placeholder="http://example.onion\nhttp://another.onion")
    if st.button("🕷️ Scrape Targets", type="primary", key="btn_direct"):
        if not target_urls_input.strip():
            st.warning("Please enter at least one URL.")
        else:
            _run_direct(target_urls_input.strip().split("\n"), tor_proxy)

# --- PERSON SEARCH TAB ---
with tab_person:
    st.markdown("### 🕵️‍♂️ Missing Person / Target Profiler")
    st.info("Advanced OSINT: Deep search for PII, leaks, dating profiles, and media. Enter a name, email, or username below.")
    
    person_query = st.text_input("Target Identifier", placeholder="e.g., John Doe, johndoe@example.com, or username123")
    
    if st.button("🔎 Find Target", type="primary", key="btn_person"):
        if not person_query:
            st.warning("Please enter a target identifier.")
        else:
            _run_person_search(person_query, tor_proxy, limit, use_llm)
            
    # Deep Scan / Context Analysis for Person Search Results
    if st.session_state.results and st.session_state.get('search_mode') == 'person': 
        st.divider()
        st.subheader("🔬 Deep Analysis")
        st.info("Want to know exactly *where* the name appears? Run a Deep Scan to visit these sites and extract context.")
        
        if st.button("🕵️‍♂️ Run Deep Scan on Results", type="primary"):
            status_ds = st.status("Deep Scanning Targets...", expanded=True)
            try:
                # Get top 10 URLs from results to avoid overloading
                targets = [r.url for r in st.session_state.results[:10]]
                status_ds.write(f"Scraping top {len(targets)} sites for context...")
                
                # Reuse crawler from direct mode
                tor = TorHandler(proxy_url=tor_proxy)
                crawler = Crawler(tor_handler=tor)
                analyzer = Analyzer()
                
                scraped_data = crawler.scrape_direct(targets)
                
                status_ds.write("Analyzing content for target name...")
                
                found_contexts = []
                for item in scraped_data:
                    # Check if LIVE
                    if "LIVE" in item.get('title', ''):
                        # Extract context using the new analyzer method
                        # We need the original query for this. 
                        # Hack: search_person puts query in 'context_query', but let's just use the input field if available
                        target_name = person_query if person_query else "" 
                        
                        # Fallback: try to guess target from snippet if input empty? No, rely on input.
                        if target_name:
                            snippets = analyzer.extract_context(item.get('snippet', ''), target_name)
                            if snippets:
                                for s in snippets:
                                    found_contexts.append({"url": item['link'], "context": s, "source": item['title']})
                
                if found_contexts:
                    st.success(f"Found {len(found_contexts)} confirmed mentions of '{person_query}'!")
                    for ctx in found_contexts:
                        st.markdown(f"**Site:** `{ctx['source']}` ({ctx['url']})")
                        st.caption(f"...{ctx['context']}...")
                        st.divider()
                else:
                    st.warning(f"Scraped {len(scraped_data)} sites but found no direct text matches for '{person_query}' in the main content. (Note: Only scraped homepage/landing).")
                    
                status_ds.update(label="Deep Scan Complete", state="complete", expanded=True)
                
            except Exception as e:
                status_ds.update(label="Error", state="error")
                st.error(f"Deep Scan failed: {e}")

# --- DISPLAY SECTION (Shared) ---
if st.session_state.results:
    st.divider()
    tab1, tab2, tab3 = st.tabs(["📊 Results", "🕸️ Network Graph", "📝 Report"])
    
    with tab1:
        st.subheader("Found Links")
        df_data = [{"Title": r.title, "URL": r.url, "Source": r.engine, "Snippet": r.snippet} for r in st.session_state.results]
        st.dataframe(pd.DataFrame(df_data), use_container_width=True)
        
        st.subheader("Extracted Artifacts")
        if st.session_state.artifacts:
            df_art = [{"Type": a.type, "Value": a.value, "Source Link": st.session_state.results[a.result_id].url} for a in st.session_state.artifacts]
            st.dataframe(pd.DataFrame(df_art), use_container_width=True)
        else:
            st.info("No artifacts found.")
            
    with tab2:
        st.subheader("Investigation Graph")
        if st.button("Generate Graph"):
            with st.spinner("Generating interactive graph..."):
                try:
                    path = generate_network_graph(st.session_state.results, st.session_state.artifacts, query_node="Investigation")
                    st.session_state.graph_path = path
                except Exception as e:
                    st.error(f"Graph generation failed: {e}")
        
        if st.session_state.graph_path:
            with open(st.session_state.graph_path, 'r', encoding='utf-8') as f:
                components.html(f.read(), height=600, scrolling=True)
            
    with tab3:
        st.subheader("Investigation Report")
        if st.button("Generate Report"):
            with st.status("Synthesizing Report...", expanded=True) as status:
                status.write("Initializing Reporter...")
                rep = Reporter()
                from collections import namedtuple
                InvObj = namedtuple("InvObj", ["id", "query", "status"])
                
                # Handle missing query if coming from direct mode
                q_text = query if query else "Direct Target Scraping"
                inv = InvObj("temp", q_text, "active")
                
                status.write("Consulting LLM for summary...")
                llm = LLMProcessor()
                res_dicts = [{"title": r.title, "link": r.url, "snippet": r.snippet} for r in st.session_state.results]
                
                if not res_dicts:
                    status.warning("No results to summarize.")
                    summary = "No search results available to summarize."
                else:
                    summary = llm.generate_report(q_text, res_dicts)
                
                status.write("Saving report files...")
                path = rep.save_report(inv, st.session_state.results, st.session_state.artifacts, llm_summary=summary, format="html")
                st.session_state.report_path = path
                status.update(label="Report Generated!", state="complete", expanded=False)
                
        if st.session_state.report_path:
            st.success(f"Report saved: {st.session_state.report_path}")
            with open(st.session_state.report_path, "rb") as f:
                st.download_button("Download HTML", f, file_name="report.html")
