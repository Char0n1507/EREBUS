import os
import markdown
from datetime import datetime

class Reporter:
    def __init__(self, output_dir="reports"):
        self.output_dir = output_dir
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def generate_markdown(self, investigation, results, artifacts, llm_summary=None):
        """
        Creates a markdown report string.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        md = f"# Argus Investigation Report\n\n"
        md += f"**Target**: {investigation.query}\n"
        md += f"**Date**: {timestamp}\n"
        md += f"**Status**: {investigation.status}\n\n"
        
        if llm_summary:
            md += "## Executive Summary\n\n"
            md += f"{llm_summary}\n\n"
            
        md += "## Key Artifacts\n\n"
        if artifacts:
            # Group by type
            artifacts_by_type = {}
            for art in artifacts:
                if art.type not in artifacts_by_type:
                    artifacts_by_type[art.type] = []
                artifacts_by_type[art.type].append(art.value)
            
            for type_, values in artifacts_by_type.items():
                md += f"### {type_.upper()}\n"
                for val in set(values):
                     md += f"- `{val}`\n"
                md += "\n"
        else:
            md += "_No specific artifacts identified._\n\n"
            
        md += "## Search Results\n\n"
        for res in results:
            md += f"### {res.title}\n"
            md += f"- **URL**: `{res.url}`\n"
            md += f"- **Source**: {res.engine}\n"
            md += f"- **Snippet**: {res.snippet}\n\n"
            
        return md

    def save_report(self, investigation, results, artifacts, llm_summary=None, format="html"):
        """
        Saves the report to disk.
        """
        md_content = self.generate_markdown(investigation, results, artifacts, llm_summary)
        
        filename = f"report_{investigation.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Save Markdown
        md_path = os.path.join(self.output_dir, f"{filename}.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)
            
        # Save HTML
        if format == "html":
            html_content = markdown.markdown(md_content, extensions=['tables', 'fenced_code'])
            # Add simple CSS for professional look
            style = """
            <style>
                body { font-family: sans-serif; line-height: 1.6; max_width: 800px; margin: 0 auto; padding: 20px; color: #333; }
                h1 { color: #2c3e50; border-bottom: 2px solid #eee; padding-bottom: 10px; }
                h2 { color: #34495e; margin-top: 30px; }
                code { background: #f4f4f4; padding: 2px 5px; border-radius: 3px; }
                pre { background: #f4f4f4; padding: 10px; border-radius: 5px; overflow-x: auto; }
            </style>
            """
            full_html = f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>Argus Report</title>{style}</head><body>{html_content}</body></html>"
            
            html_path = os.path.join(self.output_dir, f"{filename}.html")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(full_html)
            return html_path
            
        return md_path
