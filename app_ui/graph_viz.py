import networkx as nx
from pyvis.network import Network
import tempfile
import os

def generate_network_graph(results, artifacts, query_node="Investigation"):
    """
    Generates a PyVis interactive network graph from search results and artifacts.
    Returns the path to the generated HTML file.
    """
    net = Network(height="600px", width="100%", bgcolor="#000000", font_color="#00ff41",  directed=False) # select_menu=True
    net.force_atlas_2based()
    
    # Add Central Node (Query/Investigation)
    net.add_node(query_node, label=query_node, color="#ff0055", title="Investigation Target", size=40)
    
    # Add Result Nodes (Websites/Onions)
    for res in results:
        node_id = f"url_{res.id}"
        # Truncate label
        label = res.title[:20] + "..." if len(res.title) > 20 else res.title
        title_hover = f"Title: {res.title}\nURL: {res.url}\nEngine: {res.engine}"
        
        net.add_node(node_id, label=label, color="#00f2ea", title=title_hover, size=20, shape="dot")
        net.add_edge(query_node, node_id, color="#333333")
        
    # Add Artifact Nodes (PII, Crypto)
    for art in artifacts:
        # Artifact ID needs to be unique in graph
        art_node_id = f"art_{art.id}"
        source_node_id = f"url_{art.result_id}"
        
        color_map = {
            "email": "#ffeb3b", # Yellow
            "btc_address": "#ff9800", # Orange
            "credit_card": "#f44336", # Red
            "onion_v3": "#4caf50", # Green
        }
        color = color_map.get(art.type, "#9e9e9e") # Grey default
        
        net.add_node(art_node_id, label=art.value, color=color, title=f"Type: {art.type}\nValue: {art.value}", size=15, shape="diamond")
        
        # Link artifact to its source result
        # Check if source exists in graph (it should)
        if hasattr(art, 'result_id'):
             net.add_edge(source_node_id, art_node_id, color="#777777")

    # Generate graph
    # Save to a temporary file or return HTML
    # Streamlit html component requires reading string or file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".html", mode='w+', encoding='utf-8') as f:
        path = f.name
        
    net.save_graph(path)
    return path
