"""Live, supplementary validation of OpenAI title-only source matches."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re
import unicodedata
from urllib.parse import urlparse

import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[1]


def load_title_aliases():
    path = ROOT / "output/current_results_sources/_support/title_aliases.json"
    if path.exists():
        return {key: set(values) for key, values in json.loads(path.read_text(encoding="utf-8")).items()}
    aliases = {}
    for source in (ROOT / "random_100_datasets_full_metadata.csv", ROOT / "top 10/requested_10_datasets_full_metadata.csv"):
        metadata = pd.read_csv(source, dtype=str, keep_default_na=False)
        for row in metadata.to_dict("records"):
            aliases.setdefault(row.get("id", ""), set()).update(row.get(key, "") for key in (
                "title", "title_en", "study_title", "study_title_en"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({key: sorted(values) for key, values in aliases.items()}, indent=2), encoding="utf-8")
    return aliases


def normalized(text):
    return " ".join(re.findall(r"\w+", unicodedata.normalize("NFKC", str(text)).casefold()))


class PageEvidence(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.titles, self.headings, self.meta, self.parts = [], [], {}, []
        self.tag = ""
        self.ignored = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"script", "style"}:
            self.ignored = True
        if tag in {"title", "h1"}:
            self.tag = tag
        if tag == "meta":
            key = attrs.get("name", attrs.get("property", "")).lower()
            self.meta.setdefault(key, []).append(attrs.get("content", ""))

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.ignored = False
        if tag == self.tag:
            self.tag = ""

    def handle_data(self, data):
        if self.ignored:
            return
        self.parts.append(data)
        if self.tag == "title":
            self.titles.append(data)
        elif self.tag == "h1":
            self.headings.append(data)


def fetch(url):
    result = {"checked_at": datetime.now(timezone.utc).isoformat(), "requested_url": url,
              "http_status": "", "final_url": "", "redirects": [], "content_type": "",
              "page_title": "", "page_h1": "", "metadata": {}, "body_identity_terms": [], "error": ""}
    if urlparse(url).scheme not in {"http", "https"}:
        result["error"] = "not_an_http_url"
        return result
    try:
        with requests.get(url, timeout=(10, 25), stream=True, allow_redirects=True,
                          headers={"User-Agent": "GESIS-Findability-Link-Audit/1.0"}) as response:
            result.update(http_status=response.status_code, final_url=response.url,
                          redirects=[{"status": item.status_code, "url": item.url} for item in response.history],
                          content_type=response.headers.get("Content-Type", ""))
            if "html" in result["content_type"]:
                content = bytearray()
                for chunk in response.iter_content(65536):
                    content.extend(chunk)
                    if len(content) >= 2_000_000:
                        break
                parser = PageEvidence()
                parser.feed(content.decode(response.encoding or "utf-8", errors="replace"))
                result.update(page_title=" ".join(parser.titles).strip(), page_h1=" ".join(parser.headings).strip(),
                              metadata=parser.meta)
                body = " ".join(parser.parts)
                result["body_identity_terms"] = sorted(set(re.findall(r"\bZA\d{4,6}\b|10\.\d{4,9}/[\w./-]+", body, re.I)))
                result["challenge_page"] = any(term in normalized(result["page_title"] + " " + body[:3000])
                    for term in ("access denied", "verify you are human", "just a moment", "captcha", "robot check"))
    except requests.RequestException as exc:
        result["error"] = type(exc).__name__
    return result


def classify(page, source_id, source_titles, source_doi):
    status = page["http_status"]
    if page["error"]:
        return "inconclusive_request_error"
    if status in (401, 403, 429) or page.get("challenge_page"):
        return "inconclusive_blocked"
    if status in (404, 410):
        return "not_found_at_check_time"
    if not isinstance(status, int) or status >= 400:
        return "inconclusive_http_error"
    if "html" not in page["content_type"]:
        return "document_or_non_html_identity_unverified"
    final = urlparse(page["final_url"])
    if final.path.rstrip("/") in ("", "/research_data") and not final.query:
        return "generic_page_not_dataset_record"
    metadata = page.get("metadata", {})
    primary_titles = [page["page_title"], page["page_h1"]] + [
        title for key in ("citation_title", "dc.title", "dcterms.title", "og:title") for title in metadata.get(key, [])]
    exact_title = any(normalized(title) == normalized(source) for title in primary_titles
                      for source in source_titles if title and source)
    primary_ids = " ".join([page["final_url"]] + [value for key in (
        "citation_doi", "dc.identifier", "dcterms.identifier", "citation_dataset_id") for value in metadata.get(key, [])])
    id_match = bool(source_id and re.search(r"(?<![\w-])" + re.escape(source_id) + r"(?![\w-])", primary_ids, re.I))
    dois = re.findall(r"10\.\d{4,9}/[^\s\"<>]+", source_doi)
    doi_match = any(doi.lower().strip('[]\",') in primary_ids.lower() for doi in dois)
    if id_match or doi_match:
        return "source_identifier_supported_by_destination"
    if exact_title:
        return "source_title_supported_identity_or_version_unverified"
    # Body mentions and previously assigned matching labels are not record identity.
    if source_id.upper() in [term.upper() for term in page.get("body_identity_terms", [])]:
        return "source_mentioned_record_identity_unverified"
    return "inconclusive_page_identity"


def audit(fetch_live, refresh=False, report_dir=None):
    report = report_dir or ROOT / "reports/current_results"
    cache = ROOT / "output/current_results_sources/_support/title_only_link_validation/cache"
    cache.mkdir(parents=True, exist_ok=True)
    selected = []
    for sample in ("random100", "top10"):
        data = pd.read_csv(report / "openai" / sample / "returned_items.csv", sep=";", keep_default_na=False)
        rows = data[(data.provider == "OpenAI") & (pd.to_numeric(data.is_source_dataset) == 1)
                    & (pd.to_numeric(data.is_strict_source_dataset) == 0)].copy()
        rows.insert(0, "sample", sample)
        queries = pd.read_csv(report / "openai" / sample / "queries.csv", sep=";", keep_default_na=False)
        selected.append(rows.merge(queries[["provider", "variant", "query_id", "source_title", "source_doi"]],
                                   on=["provider", "variant", "query_id"], validate="many_to_one"))
    data = pd.concat(selected, ignore_index=True)
    urls = list(data.returned_url_or_doi.unique())

    def cached(url):
        path = cache / (hashlib.sha256(url.encode()).hexdigest() + ".json")
        if path.exists() and not refresh:
            return url, json.loads(path.read_text(encoding="utf-8"))
        if not fetch_live:
            raise ValueError("Missing cached page; use --fetch for live HTTP checks")
        page = fetch(url)
        path.write_text(json.dumps(page, indent=2), encoding="utf-8")
        print(f"{page['http_status']} {url}", flush=True)
        return url, page

    with ThreadPoolExecutor(max_workers=4) as pool:
        pages = dict(pool.map(cached, urls))
    # Include both original-language and English source titles, not just query titles.
    aliases = load_title_aliases()
    results = []
    for row in data.to_dict("records"):
        page = pages[row["returned_url_or_doi"]]
        titles = aliases.get(row["source_dataset_id"], set()) | {row["source_title"]}
        classification = classify(page, row["source_dataset_id"], titles, row["source_doi"])
        results.append({**row, "validation_class": classification,
                        **{key: page.get(key, "") for key in ("checked_at", "http_status", "final_url", "content_type", "page_title", "page_h1", "error")}})
    output = report / "link_validation"
    output.mkdir(exist_ok=True)
    frame = pd.DataFrame(results)
    frame.to_csv(output / "title_only_items.csv", sep=";", index=False, encoding="utf-8-sig")
    summary = frame.groupby(["sample", "variant", "validation_class"]).size().reset_index(name="item_rows")
    summary.to_csv(output / "summary.csv", sep=";", index=False, encoding="utf-8-sig")
    inputs = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
              for sample in ("random100", "top10") for path in (
                  report / "openai" / sample / "returned_items.csv", report / "openai" / sample / "queries.csv")}
    alias_path = ROOT / "output/current_results_sources/_support/title_aliases.json"
    for path in [alias_path] + [cache / (hashlib.sha256(url.encode()).hexdigest() + ".json") for url in urls]:
        inputs[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    (output / "provenance.json").write_text(json.dumps({"built_at": datetime.now(timezone.utc).isoformat(),
        "input_sha256": inputs, "item_rows": len(frame), "unique_urls": len(urls),
        "output_sha256": {name: hashlib.sha256((output / name).read_bytes()).hexdigest()
                          for name in ("title_only_items.csv", "summary.csv")},
        "scope": "OpenAI item rows with is_source_dataset=1 and is_strict_source_dataset=0; all ranks",
        "metrics_changed": False}, indent=2), encoding="utf-8")
    print(frame.validation_class.value_counts().to_string())
    print(f"Audited {len(frame)} rows / {len(urls)} unique URLs. Existing metrics unchanged.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true", help="Fetch uncached public pages (no model API calls)")
    parser.add_argument("--refresh", action="store_true", help="Refresh cached checks; requires --fetch")
    args = parser.parse_args()
    if args.refresh and not args.fetch:
        parser.error("--refresh requires --fetch")
    audit(args.fetch, args.refresh)
