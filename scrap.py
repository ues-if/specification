#!/usr/bin/env python3
"""Fetch public IPD-related source data referenced in docs/ai-deep-search.adoc.

The script intentionally uses only the Python standard library so it can run in
this repository without extra dependencies.

Examples:
    python scrap.py --list
    python scrap.py --source eurostat
    python scrap.py --source taiwan_plos
    python scrap.py --source taiwan_plos --verbose
    python scrap.py --source all --out data/raw
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import re
import time
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0 Safari/537.36"
)
DOC_PATH = Path("docs/ai-deep-search.adoc")
ANSUR_PAGE_URL = "https://www.openlab.psu.edu/ansur2/"


@dataclass
class FetchResult:
    source: str
    requested_url: str
    url: str
    path: str | None
    status: str
    content_type: str | None = None
    bytes: int = 0
    redirected: bool = False
    error: str | None = None
    analysis: dict[str, object] | None = None


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.scripts: list[str] = []
        self.meta_refreshes: list[str] = []
        self.title_parts: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {name.lower(): value for name, value in attrs}
        if tag.lower() == "title":
            self._in_title = True
        if tag.lower() == "script" and attr_map.get("src"):
            self.scripts.append(attr_map["src"] or "")
        if tag.lower() == "meta" and (attr_map.get("http-equiv") or "").lower() == "refresh":
            if attr_map.get("content"):
                self.meta_refreshes.append(attr_map["content"] or "")
        for name, value in attrs:
            if name.lower() == "href" and value:
                self.links.append(value)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data.strip())


SOURCES = {
    "eurostat": "Eurostat demo_pjan JSON for EU27 population by age and sex",
    "taiwan_plos": "PLOS One Taiwan respirator supplementary dataset XLSX",
    "ansur2": "ANSUR II OpenLab page with best-effort downloadable-link discovery",
    "document_urls": "All URLs listed in docs/ai-deep-search.adoc as raw files",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        choices=tuple(SOURCES) + ("all",),
        default="all",
        help="Source to fetch.",
    )
    parser.add_argument("--out", type=Path, default=Path("data/raw"), help="Output directory.")
    parser.add_argument("--list", action="store_true", help="List supported sources and exit.")
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Seconds to wait between requests when fetching multiple URLs.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print per-step progress while fetching.",
    )
    args = parser.parse_args()

    if args.list:
        for name, description in SOURCES.items():
            print(f"{name:<14} {description}")
        return

    args.out.mkdir(parents=True, exist_ok=True)
    results: list[FetchResult] = []
    selected = tuple(SOURCES) if args.source == "all" else (args.source,)
    progress(args.verbose, f"Selected {len(selected)} source group(s): {', '.join(selected)}")
    for index, source in enumerate(selected, 1):
        progress(args.verbose, f"[{index}/{len(selected)}] Starting {source}: {SOURCES[source]}")
        if source == "eurostat":
            results.extend(fetch_eurostat(args.out / "eurostat", verbose=args.verbose))
        elif source == "taiwan_plos":
            results.append(fetch_url(
                source="taiwan_plos",
                url="https://doi.org/10.1371/journal.pone.0188638.s002",
                out_dir=args.out / "taiwan_plos",
                fallback_name="journal.pone.0188638.s002",
                verbose=args.verbose,
            ))
        elif source == "ansur2":
            results.extend(fetch_ansur2(args.out / "ansur2", delay=args.delay, verbose=args.verbose))
        elif source == "document_urls":
            results.extend(fetch_document_urls(
                args.out / "document_urls",
                delay=args.delay,
                verbose=args.verbose,
            ))
        progress(args.verbose, f"[{index}/{len(selected)}] Finished {source}")

    manifest_path = args.out / "manifest.json"
    manifest_path.write_text(
        json.dumps([asdict(result) for result in results], indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote manifest: {manifest_path}")
    for result in results:
        target = result.path or result.error or "-"
        print(f"{result.status:<7} {result.source:<14} {target}")
    counts = {status: sum(1 for result in results if result.status == status) for status in ("ok", "mismatch", "error")}
    print(
        "Summary: "
        f"{counts['ok']} ok, "
        f"{counts['mismatch']} mismatch, "
        f"{counts['error']} error"
    )


def fetch_eurostat(out_dir: Path, verbose: bool) -> list[FetchResult]:
    base_url = (
        "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
        "demo_pjan?format=JSON&lang=en&geo=EU27_2020&time=2023&sex={sex}"
    )
    sexes = ("F", "M", "T")
    results: list[FetchResult] = []
    progress(verbose, f"Fetching Eurostat JSON for {len(sexes)} sex filters")
    for index, sex in enumerate(sexes, 1):
        progress(verbose, f"Eurostat [{index}/{len(sexes)}] sex={sex}")
        results.append(fetch_url(
            source=f"eurostat_{sex}",
            url=base_url.format(sex=sex),
            out_dir=out_dir,
            fallback_name=f"demo_pjan_EU27_2020_2023_{sex}.json",
            verbose=verbose,
        ))
    return results


def fetch_ansur2(out_dir: Path, delay: float, verbose: bool) -> list[FetchResult]:
    page_url = ANSUR_PAGE_URL
    progress(verbose, "Fetching ANSUR II landing page for link discovery")
    page = fetch_url("ansur2_page", page_url, out_dir, "ansur2.html", verbose=verbose)
    if page.status != "ok" or page.path is None:
        return [page]

    html = Path(page.path).read_text(encoding="utf-8", errors="replace")
    links = extract_links(html, page_url)
    downloadable = [
        link for link in links
        if looks_downloadable(link) and "ansur" in link.lower()
    ]
    downloadable = unique(downloadable)
    progress(verbose, f"ANSUR II page has {len(links)} link(s); {len(downloadable)} look downloadable")
    results = [page]
    for index, url in enumerate(downloadable, 1):
        progress(verbose, f"ANSUR II download [{index}/{len(downloadable)}]")
        time.sleep(delay)
        results.append(fetch_url(
            "ansur2",
            url,
            out_dir,
            fallback_name=filename_from_url(url),
            verbose=verbose,
        ))
    return results


def fetch_document_urls(out_dir: Path, delay: float, verbose: bool) -> list[FetchResult]:
    if not DOC_PATH.exists():
        return [FetchResult(
            source="document_urls",
            requested_url=str(DOC_PATH),
            url=str(DOC_PATH),
            path=None,
            status="error",
            error="doc not found",
        )]

    text = DOC_PATH.read_text(encoding="utf-8", errors="replace")
    urls = unique(re.findall(r"https?://[^\s\]\)<>]+", text))
    progress(verbose, f"Found {len(urls)} URL(s) in {DOC_PATH}")
    results: list[FetchResult] = []
    for index, url in enumerate(urls, 1):
        progress(verbose, f"Document URL [{index}/{len(urls)}]")
        time.sleep(delay)
        parsed = urlparse(url)
        host_dir = out_dir / safe_name(parsed.netloc)
        results.append(fetch_url(
            "document_urls",
            url,
            host_dir,
            filename_from_url(url),
            verbose=verbose,
        ))
    return results


def fetch_url(
    source: str,
    url: str,
    out_dir: Path,
    fallback_name: str,
    verbose: bool,
) -> FetchResult:
    out_dir.mkdir(parents=True, exist_ok=True)
    progress(verbose, f"GET {url}")
    try:
        request = Request(url, headers=request_headers(url))
        with urlopen(request, timeout=60) as response:
            body = response.read()
            final_url = response.geturl()
            content_type = response.headers.get("content-type")
            redirected = final_url != url
            name = choose_filename(
                content_disposition=response.headers.get("content-disposition"),
                final_url=final_url,
                fallback_name=fallback_name,
                content_type=content_type,
            )
            html_analysis = None
            if is_html_response(content_type, body):
                html_analysis = analyze_html(body, final_url)
            validation_error = validate_download(name, content_type, body)
            if validation_error and is_html_response(content_type, body):
                name = f"{name}.html"
            path = unique_path(out_dir / safe_name(name))
            path.write_bytes(body)
            analysis_path = None
            if html_analysis is not None:
                analysis_path = path.with_name(f"{path.name}.analysis.json")
                analysis_path.write_text(
                    json.dumps(html_analysis, indent=2) + "\n",
                    encoding="utf-8",
                )
            if validation_error:
                progress(verbose, f"MISMATCH {len(body):,} bytes -> {path}: {validation_error}")
            else:
                progress(verbose, f"OK  {len(body):,} bytes -> {path}")
            if redirected:
                progress(verbose, f"REDIRECT {url} -> {final_url}")
            if html_analysis is not None:
                progress(verbose, summarize_html_analysis(html_analysis, analysis_path))
            return FetchResult(
                source=source,
                requested_url=url,
                url=final_url,
                path=str(path),
                status="mismatch" if validation_error else "ok",
                content_type=content_type,
                bytes=len(body),
                redirected=redirected,
                error=validation_error,
                analysis=html_analysis,
            )
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        progress(verbose, f"ERR {url}: {exc}")
        return FetchResult(
            source=source,
            requested_url=url,
            url=url,
            path=None,
            status="error",
            error=str(exc),
        )


def request_headers(url: str) -> dict[str, str]:
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix == ".csv":
        accept = "text/csv,application/csv,application/vnd.ms-excel,application/octet-stream,*/*;q=0.8"
    elif suffix == ".pdf":
        accept = "application/pdf,application/octet-stream,*/*;q=0.8"
    elif suffix == ".xlsx":
        accept = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/octet-stream,*/*;q=0.8"
    else:
        accept = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": accept,
    }
    parsed = urlparse(url)
    if parsed.netloc.lower() == "tools.openlab.psu.edu" and parsed.path.startswith("/publicData/"):
        headers["Referer"] = ANSUR_PAGE_URL
    return headers


def extract_links(html: str, base_url: str) -> list[str]:
    parser = LinkParser()
    parser.feed(html)
    return [urljoin(base_url, link) for link in parser.links]


def analyze_html(body: bytes, base_url: str) -> dict[str, object]:
    text = body.decode("utf-8", errors="replace")
    parser = LinkParser()
    parser.feed(text)
    links = unique(urljoin(base_url, link) for link in parser.links)
    scripts = unique(urljoin(base_url, script) for script in parser.scripts if script)
    meta_refreshes = [parse_meta_refresh(refresh, base_url) for refresh in parser.meta_refreshes]
    downloadable_links = [link for link in links if looks_downloadable(link)]
    embedded_urls = unique(re.findall(r"https?://[^\s'\"<>\\)]+", text))
    embedded_downloads = [url for url in embedded_urls if looks_downloadable(url)]
    lower_text = text.lower()
    error_hints = [
        phrase for phrase in (
            "not found",
            "404",
            "forbidden",
            "access denied",
            "unauthorized",
            "error",
        )
        if phrase in lower_text
    ]
    app_hints = [
        hint for hint in (
            "vite",
            "type=\"module\"",
            "<div id=\"root\"",
            "<div id=\"app\"",
        )
        if hint in lower_text
    ]
    title = " ".join(part for part in parser.title_parts if part).strip()
    return {
        "title": title or None,
        "link_count": len(links),
        "links": links[:100],
        "script_count": len(scripts),
        "scripts": scripts[:50],
        "meta_refreshes": meta_refreshes,
        "downloadable_link_count": len(downloadable_links),
        "downloadable_links": downloadable_links[:100],
        "embedded_download_count": len(embedded_downloads),
        "embedded_downloads": embedded_downloads[:100],
        "error_hints": error_hints,
        "app_shell_hints": app_hints,
    }


def parse_meta_refresh(content: str, base_url: str) -> dict[str, object]:
    match = re.search(r"url\s*=\s*([^;]+)", content, flags=re.IGNORECASE)
    target = urljoin(base_url, match.group(1).strip(" '\"")) if match else None
    delay_match = re.match(r"\s*(\d+(?:\.\d+)?)", content)
    return {
        "content": content,
        "delay_seconds": float(delay_match.group(1)) if delay_match else None,
        "url": target,
    }


def summarize_html_analysis(analysis: dict[str, object], analysis_path: Path | None) -> str:
    title = analysis.get("title") or "untitled"
    downloads = analysis.get("downloadable_link_count", 0)
    scripts = analysis.get("script_count", 0)
    app_hints = analysis.get("app_shell_hints") or []
    errors = analysis.get("error_hints") or []
    parts = [
        f"HTML title={title!r}",
        f"downloadable_links={downloads}",
        f"scripts={scripts}",
    ]
    if app_hints:
        parts.append(f"app_shell_hints={','.join(str(hint) for hint in app_hints)}")
    if errors:
        parts.append(f"error_hints={','.join(str(error) for error in errors)}")
    if analysis_path is not None:
        parts.append(f"analysis={analysis_path}")
    return " ; ".join(parts)


def looks_downloadable(url: str) -> bool:
    path = urlparse(url).path.lower()
    return path.endswith((".csv", ".zip", ".xlsx", ".xls", ".json", ".txt", ".pdf"))


def filename_from_headers(content_disposition: str | None) -> str | None:
    if not content_disposition:
        return None
    match = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', content_disposition)
    return match.group(1) if match else None


def filename_from_url(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    if not path:
        return "index.html"
    return Path(path).name or "index.html"


def choose_filename(
    content_disposition: str | None,
    final_url: str,
    fallback_name: str,
    content_type: str | None,
) -> str:
    header_name = filename_from_headers(content_disposition)
    if header_name:
        return header_name

    url_name = filename_from_url(final_url)
    fallback_suffix = Path(fallback_name).suffix
    if Path(url_name).suffix:
        return url_name
    if fallback_suffix:
        return fallback_name

    extension = extension_from_content_type(content_type)
    return f"{url_name}{extension}" if extension else url_name


def extension_from_content_type(content_type: str | None) -> str:
    if not content_type:
        return ""
    media_type = content_type.split(";", 1)[0].strip().lower()
    if media_type == "text/html":
        return ".html"
    if media_type == "application/json":
        return ".json"
    if media_type == "application/pdf":
        return ".pdf"
    if media_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        return ".xlsx"
    return mimetypes.guess_extension(media_type) or ""


def validate_download(name: str, content_type: str | None, body: bytes) -> str | None:
    suffix = Path(name).suffix.lower()
    if not suffix:
        return None
    if suffix == ".csv":
        if is_html_response(content_type, body):
            if is_app_shell_response(body):
                return "expected CSV but received HTML app shell"
            return "expected CSV but received HTML"
        return None
    if suffix == ".pdf":
        if not body.startswith(b"%PDF"):
            return "expected PDF magic bytes"
        return None
    if suffix == ".xlsx":
        if not body.startswith(b"PK"):
            return "expected XLSX zip magic bytes"
        return None
    if suffix == ".json":
        if is_html_response(content_type, body):
            return "expected JSON but received HTML"
        try:
            json.loads(body.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            return f"invalid JSON: {exc}"
        return None
    return None


def is_html_response(content_type: str | None, body: bytes) -> bool:
    media_type = (content_type or "").split(";", 1)[0].strip().lower()
    if media_type == "text/html":
        return True
    return body.lstrip().lower().startswith((b"<!doctype html", b"<html"))


def is_app_shell_response(body: bytes) -> bool:
    text = body[:5000].decode("utf-8", errors="replace").lower()
    return "<div id=\"root\"" in text or "vite" in text or "type=\"module\"" in text


def safe_name(name: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name.strip())
    return name.strip("._") or "download"


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    for idx in range(1, 10_000):
        candidate = path.with_name(f"{stem}_{idx}{suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"could not find unique path for {path}")


def unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def progress(verbose: bool, message: str) -> None:
    if verbose:
        print(message, flush=True)


if __name__ == "__main__":
    main()
