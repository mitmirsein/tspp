#!/usr/bin/env python3
# /// script
# dependencies = [
#   "requests",
# ]
# ///
"""
Crossref Theology Journal Searcher
Author: Antigravity AI
Version: 1.0.0
Description: Queries the Crossref API for papers Matching the query, restricted
             to our curated database of 58 prestigious theology journals.
"""

import os
import sys
import json
import argparse
from typing import List, Dict, Any, Optional
import requests

# Crossref API Polite Pool configuration
USER_AGENT = "AntigravityTheologyBot/1.0 (mailto:msn@example.com)"
CROSSREF_API_URL = "https://api.crossref.org/works"

class CrossrefJournalSearcher:
    def __init__(self, debug: bool = False):
        self.debug = debug
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.journals = self._load_journals()

    def _load_journals(self) -> List[Dict[str, Any]]:
        """Loads theology journals database from local JSON file"""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(os.path.dirname(script_dir), "theology_journals.json")
        
        if not os.path.exists(json_path):
            if self.debug:
                print(f"[!] Warning: {json_path} not found. Running without journal filter.", file=sys.stderr)
            return []
            
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[!] Error loading journals: {e}", file=sys.stderr)
            return []

    def get_issns(self) -> List[str]:
        """Extracts unique and clean ISSNs from the journals list"""
        issns = set()
        for journal in self.journals:
            issn = journal.get("issn")
            if issn and isinstance(issn, str):
                cleaned = issn.strip()
                if cleaned:
                    issns.add(cleaned)
        return sorted(list(issns))

    def _chunk_list(self, lst: list, chunk_size: int) -> List[list]:
        """Splits a list into smaller lists of chunk_size"""
        return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]

    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Queries Crossref /works endpoint filtering by the journal ISSNs using chunking"""
        issn_list = self.get_issns()
        
        if not issn_list:
            if self.debug:
                print("[*] No ISSN filters available. Querying global Crossref database.", file=sys.stderr)
            return self._query_crossref(query, filter_str=None, limit=limit)

        # Crossref URI filter query length can fail if too many ISSNs are packed in one request.
        # We chunk them in sets of 20.
        chunk_size = 20
        issn_chunks = self._chunk_list(issn_list, chunk_size)
        
        all_results = []
        
        if self.debug:
            print(f"[*] Total ISSNs: {len(issn_list)}. Chunked into {len(issn_chunks)} queries.", file=sys.stderr)

        for idx, chunk in enumerate(issn_chunks, 1):
            if self.debug:
                print(f"[*] Querying chunk {idx}/{len(issn_chunks)} with {len(chunk)} ISSNs...", file=sys.stderr)
                
            # Crossref filter format: filter=issn:1234-5678,issn:8765-4321
            filter_parts = [f"issn:{issn}" for issn in chunk]
            filter_str = ",".join(filter_parts)
            
            # Request limit items from each chunk to ensure we get enough relevant options
            chunk_results = self._query_crossref(query, filter_str=filter_str, limit=limit)
            all_results.extend(chunk_results)

        # Deduplicate by DOI
        deduped = {}
        for item in all_results:
            doi = item.get("doi")
            if doi:
                # Keep the one with the higher relevance score if duplicates exist
                if doi not in deduped or item.get("_score", 0.0) > deduped[doi].get("_score", 0.0):
                    deduped[doi] = item
            else:
                # If no DOI, use title hash to deduplicate
                title_hash = hash(item.get("title", ""))
                if title_hash not in deduped:
                    deduped[title_hash] = item

        # Sort deduplicated results by score descending
        sorted_results = sorted(deduped.values(), key=lambda x: x.get("_score", 0.0), reverse=True)
        
        # Clean private fields (e.g. _score) and slice to requested limit
        final_results = []
        for r in sorted_results[:limit]:
            clean_item = {k: v for k, v in r.items() if not k.startswith("_")}
            final_results.append(clean_item)
            
        return final_results

    def _query_crossref(self, query: str, filter_str: Optional[str], limit: int) -> List[Dict[str, Any]]:
        """Hits the Crossref API for a single filter chunk"""
        params = {
            "query": query,
            "rows": str(limit)
        }
        if filter_str:
            params["filter"] = filter_str

        try:
            resp = self.session.get(CROSSREF_API_URL, params=params, timeout=20)
            if resp.status_code != 200:
                if self.debug:
                    print(f"[!] API call failed with status: {resp.status_code}. Response: {resp.text[:200]}", file=sys.stderr)
                return []
                
            data = resp.json()
            items = data.get("message", {}).get("items", [])
            
            parsed_items = []
            for item in items:
                parsed_items.append(self._parse_item(item))
            return parsed_items
            
        except Exception as e:
            if self.debug:
                print(f"[!] Error querying Crossref: {e}", file=sys.stderr)
            return []

    def _parse_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Normalizes Crossref item structure to the standardized schema"""
        # Title
        titles = item.get("title", [])
        title = titles[0] if titles else "N/A"
        
        # Authors
        authors_list = []
        for aut in item.get("author", []):
            given = aut.get("given", "")
            family = aut.get("family", "")
            if given and family:
                authors_list.append(f"{family}, {given}")
            elif family:
                authors_list.append(family)
            elif given:
                authors_list.append(given)
        authors = ", ".join(authors_list) if authors_list else "N/A"
        
        # Journal
        containers = item.get("container-title", [])
        journal = containers[0] if containers else "N/A"
        
        # Year
        year = "N/A"
        for date_type in ["published-print", "published-online", "issued", "created"]:
            date_parts = item.get(date_type, {}).get("date-parts", [])
            if date_parts and date_parts[0] and date_parts[0][0]:
                year = str(date_parts[0][0])
                break
                
        # Volume, Issue, Pages
        volume = item.get("volume", "")
        issue = item.get("issue", "")
        pages = item.get("page", "")
        
        # DOI & Link
        doi = item.get("DOI", "")
        link = item.get("URL", "")
        if not link and doi:
            link = f"https://doi.org/{doi}"
            
        # Format
        fmt = item.get("type", "journal-article")
        fmt_clean = fmt.replace("-", " ").title()
        
        score = item.get("score", 0.0)

        return {
            "title": title,
            "authors": authors,
            "journal": journal,
            "year": year,
            "volume": volume,
            "issue": issue,
            "pages": pages,
            "doi": doi,
            "link": link,
            "format": fmt_clean,
            "_score": score
        }

def main():
    parser = argparse.ArgumentParser(description="Crossref Premium Theology Journal Searcher CLI")
    parser.add_argument("--query", "-q", required=True, help="Search query (e.g. 'Amos 4:13')")
    parser.add_argument("--limit", "-l", type=int, default=10, help="Maximum records to retrieve (default: 10)")
    parser.add_argument("--debug", "-d", action="store_true", help="Print debug information to stderr")
    parser.add_argument("--format", "-f", choices=["json", "markdown"], default="json", help="Output format (default: json)")
    args = parser.parse_args()

    searcher = CrossrefJournalSearcher(debug=args.debug)
    results = searcher.search(args.query, limit=args.limit)

    if args.format == "json":
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print(f"# 📚 Crossref 저널 검색 결과: \"{args.query}\"\n")
        if not results:
            print("검색 결과가 없습니다.")
            return
            
        for idx, item in enumerate(results, 1):
            title = item["title"]
            authors = item["authors"]
            journal = item["journal"]
            year = item["year"]
            link = item["link"]
            doi = item["doi"]
            fmt = item["format"]
            
            if link:
                print(f"### {idx}. [{title}]({link})")
            else:
                print(f"### {idx}. {title}")
                
            print(f"- **저자**: {authors}")
            print(f"- **유형**: {fmt} | **발행년도**: {year}")
            
            if journal and journal != "N/A":
                vol_info = []
                if item.get("volume"):
                    vol_info.append(f"Vol. {item['volume']}")
                if item.get("issue"):
                    vol_info.append(f"No. {item['issue']}")
                if item.get("pages"):
                    vol_info.append(f"pp. {item['pages']}")
                
                extra = f" ({', '.join(vol_info)})" if vol_info else ""
                print(f"- **저널**: *{journal}*{extra}")
                
            if doi:
                print(f"- **DOI**: [{doi}](https://doi.org/{doi})")
            print()

if __name__ == "__main__":
    main()
