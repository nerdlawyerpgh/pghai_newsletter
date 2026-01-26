# improved_extraction.py
"""
Enhanced web/content extraction with:
- Better error handling and logging
- Async parallel source fetching
- Improved link ranking with domain reputation
- Paywall detection
- Content freshness checking
- PDF text extraction
"""

import asyncio
import io
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests
import trafilatura
from bs4 import BeautifulSoup
from dateutil import parser as dateparser
from readability import Document

# PDF extraction
try:
    from pypdf import PdfReader
    PDF_SUPPORT = True
except ImportError:
    try:
        from PyPDF2 import PdfReader
        PDF_SUPPORT = True
    except ImportError:
        PDF_SUPPORT = False


# ---------------------------
# Configuration
# ---------------------------

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; NewsletterBot/1.0; +https://example.org)"
}

# Expanded high-value domains for academic/official sources
HIGH_VALUE_DOMAINS = {
    # Academic publishers
    "doi.org", "arxiv.org", "papers.ssrn.com", "dl.acm.org",
    "ieeexplore.ieee.org", "nature.com", "science.org",
    "springer.com", "academic.oup.com", "jamanetwork.com",
    "nejm.org", "thelancet.com", "bmj.com", "plos.org",
    "frontiersin.org", "mdpi.com", "biorxiv.org", "medrxiv.org",
    
    # Government/official sources
    "whitehouse.gov", "nist.gov", "europa.eu", "who.int",
    "oecd.org", "un.org", "fda.gov", "cdc.gov", "nih.gov",
    "nsf.gov", "energy.gov", "nasa.gov",
    
    # Research institutions
    "mit.edu", "stanford.edu", "harvard.edu", "cam.ac.uk",
    "ox.ac.uk", "berkeley.edu",
    
    # AI-specific sources
    "openai.com", "anthropic.com", "deepmind.com",
    "research.google", "ai.meta.com", "blogs.microsoft.com",
}

REPUTABLE_NEWS_DOMAINS = {
    "nytimes.com", "wsj.com", "washingtonpost.com", "ft.com",
    "bloomberg.com", "reuters.com", "apnews.com", "bbc.com",
    "theguardian.com", "economist.com", "nature.com/news",
    "scientificamerican.com", "technologyreview.com",
    "wired.com", "arstechnica.com", "theverge.com",
}

LOW_VALUE_PATTERNS = [
    "twitter.com", "x.com", "facebook.com", "linkedin.com",
    "instagram.com", "tiktok.com", "reddit.com", "pinterest.com",
    "youtube.com", "medium.com/@",  # personal Medium blogs
]

PAYWALL_INDICATORS = [
    "subscribe", "subscription", "paywall", "premium content",
    "login to continue", "sign up to read", "member exclusive",
    "subscriber only", "this content is locked",
]


# ---------------------------
# HTTP helpers
# ---------------------------

@dataclass
class FetchResult:
    """Result of fetching a URL."""
    url: str
    success: bool
    html: str = ""
    error: str = ""
    status_code: int = 0
    
    @property
    def ok(self) -> bool:
        return self.success


def is_pdf_url(url: str) -> bool:
    """Check if URL likely points to a PDF."""
    url_lower = url.lower()
    return (
        url_lower.endswith('.pdf') or 
        '/pdf/' in url_lower or
        'pdf' in url_lower.split('?')[0].split('/')[-1]
    )


def extract_text_from_pdf(pdf_content: bytes, max_pages: int = 50) -> str:
    """
    Extract text from PDF bytes.
    
    Args:
        pdf_content: Raw PDF bytes
        max_pages: Maximum pages to extract (prevent huge documents)
        
    Returns:
        Extracted text or empty string if extraction fails
    """
    if not PDF_SUPPORT:
        return ""
    
    try:
        pdf_file = io.BytesIO(pdf_content)
        reader = PdfReader(pdf_file)
        
        text_parts = []
        num_pages = min(len(reader.pages), max_pages)
        
        for i in range(num_pages):
            try:
                page = reader.pages[i]
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            except Exception:
                # Skip problematic pages
                continue
        
        full_text = "\n\n".join(text_parts)
        
        # Clean up common PDF artifacts
        full_text = re.sub(r'\n{3,}', '\n\n', full_text)
        full_text = re.sub(r' {2,}', ' ', full_text)
        
        return full_text.strip()
        
    except Exception:
        return ""


def fetch_html(
    url: str,
    timeout: int = 30,
    headers: Optional[Dict] = None,
    max_retries: int = 2,
) -> FetchResult:
    """
    Fetch raw HTML with retries and better error handling.
    
    Returns:
        FetchResult with success status and HTML or error message
    """
    h = dict(DEFAULT_HEADERS)
    if headers:
        h.update(headers)
    
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, timeout=timeout, headers=h, allow_redirects=True)
            
            if resp.status_code == 403:
                return FetchResult(
                    url=url,
                    success=False,
                    error="Access forbidden (403) - likely blocking bots",
                    status_code=403,
                )
            elif resp.status_code == 404:
                return FetchResult(
                    url=url,
                    success=False,
                    error="Page not found (404)",
                    status_code=404,
                )
            elif resp.status_code >= 500:
                # Server errors - retry
                if attempt < max_retries - 1:
                    continue
                return FetchResult(
                    url=url,
                    success=False,
                    error=f"Server error ({resp.status_code})",
                    status_code=resp.status_code,
                )
            
            resp.raise_for_status()
            
            # Check if response is a PDF
            content_type = resp.headers.get('content-type', '').lower()
            is_pdf = 'application/pdf' in content_type or is_pdf_url(url)
            
            if is_pdf and PDF_SUPPORT:
                # Extract text from PDF
                text = extract_text_from_pdf(resp.content)
                if text:
                    # Return text wrapped in tag to indicate PDF source
                    return FetchResult(
                        url=url,
                        success=True,
                        html=f"<!-- PDF source -->\n{text}",
                        status_code=resp.status_code,
                    )
                else:
                    return FetchResult(
                        url=url,
                        success=False,
                        error="pdf_extraction_failed",
                        status_code=resp.status_code,
                    )
            elif is_pdf and not PDF_SUPPORT:
                return FetchResult(
                    url=url,
                    success=False,
                    error="pdf_no_extraction_library_install_pypdf",
                    status_code=resp.status_code,
                )
            
            return FetchResult(
                url=url,
                success=True,
                html=resp.text,
                status_code=resp.status_code,
            )
            
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                continue
            return FetchResult(
                url=url,
                success=False,
                error="Request timeout",
            )
        except requests.exceptions.RequestException as e:
            return FetchResult(
                url=url,
                success=False,
                error=f"Request failed: {str(e)[:200]}",
            )
    
    return FetchResult(url=url, success=False, error="Unknown error")


# ---------------------------
# Content extraction
# ---------------------------

def detect_paywall(html: str, text: str) -> bool:
    """
    Detect if content is likely paywalled.
    
    Indicators:
    - Paywall-related text in HTML
    - Very short extracted text
    - Common paywall patterns
    """
    html_lower = html.lower()
    
    # Check for common paywall indicators
    for indicator in PAYWALL_INDICATORS:
        if indicator in html_lower:
            return True
    
    # Short content is suspicious
    if len(text) < 500:
        return True
    
    # Check for truncation markers
    if any(marker in text for marker in ["...", "[...]", "Read more", "Continue reading"]):
        # Only if text is short
        if len(text) < 1500:
            return True
    
    return False


def _readability_fallback_text(html: str) -> str:
    """Enhanced readability extraction with better text cleaning."""
    doc = Document(html)
    soup = BeautifulSoup(doc.summary(), "html.parser")
    
    # Remove script and style elements
    for script in soup(["script", "style", "noscript"]):
        script.decompose()
    
    # Get text with paragraph breaks
    text = soup.get_text(separator="\n").strip()
    
    # Clean up excessive whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)
    
    return text


def _normalize_date(date_str: str) -> str:
    """Normalize to YYYY-MM-DD with better error handling."""
    if not date_str:
        return ""
    try:
        dt = dateparser.parse(date_str)
        if dt:
            return dt.date().isoformat()
    except Exception:
        pass
    return ""


def is_content_fresh(publish_date: str, max_age_days: int = 90) -> bool:
    """Check if content is recent enough to be relevant."""
    if not publish_date:
        return False  # Unknown age
    
    try:
        pub_dt = datetime.fromisoformat(publish_date)
        age = datetime.now() - pub_dt
        return age.days <= max_age_days
    except Exception:
        return False


def extract_article(url: str, max_chars: int = 250_000) -> Dict[str, Any]:
    """
    Enhanced article extraction with better error handling and metadata.
    
    Returns:
        Dict with url, title, author, publisher, publish_date, text, html,
        notes, paywall_detected, is_fresh
    """
    notes: List[str] = []
    
    # Fetch HTML
    fetch_result = fetch_html(url)
    if not fetch_result.ok:
        return {
            "url": url,
            "title": "",
            "author": "",
            "publisher": "",
            "publish_date": "",
            "text": "",
            "html": "",
            "notes": [f"fetch_failed: {fetch_result.error}"],
            "paywall_detected": False,
            "is_fresh": False,
        }
    
    html = fetch_result.html
    
    # Extract text with trafilatura
    text = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=True,  # Changed to True - tables often have data
        favor_precision=True,
        deduplicate=True,
    ) or ""
    text = text.strip()
    
    # Fallback to readability if needed
    if not text or len(text) < 800:
        notes.append("trafilatura_insufficient_using_readability")
        text = _readability_fallback_text(html)
    
    # Detect paywall
    paywall_detected = detect_paywall(html, text)
    if paywall_detected:
        notes.append("paywall_detected_content_may_be_incomplete")
    
    # Truncate if needed
    if len(text) > max_chars:
        notes.append(f"text_truncated_from_{len(text)}_to_{max_chars}_chars")
        text = text[:max_chars]
    
    # Extract metadata
    md = trafilatura.metadata.extract_metadata(html)
    title = (md.title if md and md.title else "") or ""
    author = (md.author if md and md.author else "") or ""
    publisher = (md.sitename if md and md.sitename else "") or ""
    publish_date_raw = (md.date if md and md.date else "") or ""
    publish_date = _normalize_date(publish_date_raw)
    
    if not publish_date and publish_date_raw:
        notes.append("publish_date_unparseable")
    
    # Fallback for title
    if not title:
        try:
            soup = BeautifulSoup(html, "html.parser")
            
            # Try OpenGraph first
            og_title = soup.find("meta", property="og:title")
            if og_title and og_title.get("content"):
                title = og_title["content"].strip()
                notes.append("title_from_og_title")
            elif soup.title and soup.title.text:
                title = soup.title.text.strip()
                notes.append("title_from_html_title")
        except Exception:
            pass
    
    # Check freshness
    is_fresh = is_content_fresh(publish_date, max_age_days=90)
    
    return {
        "url": url,
        "title": title,
        "author": author,
        "publisher": publisher,
        "publish_date": publish_date,
        "text": text or "",
        "html": html,
        "notes": notes,
        "paywall_detected": paywall_detected,
        "is_fresh": is_fresh,
    }


# ---------------------------
# Enhanced link extraction & ranking
# ---------------------------

def extract_outbound_links(base_url: str, html: str) -> List[str]:
    """Extract unique, absolute http(s) links from HTML."""
    soup = BeautifulSoup(html, "html.parser")
    links = set()
    
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href or href.startswith("#") or href.lower().startswith("javascript:"):
            continue
        
        full = urljoin(base_url, href)
        parsed = urlparse(full)
        
        if parsed.scheme in ("http", "https") and parsed.netloc:
            # Remove fragments and normalize
            clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if parsed.query:
                clean_url += f"?{parsed.query}"
            links.add(clean_url)
    
    return sorted(links)


def score_link(url: str, article_domain: str = "") -> int:
    """
    Enhanced heuristic scoring for citation-worthiness.
    
    Higher score = more likely to be a valuable source.
    """
    u = url.lower()
    host = urlparse(u).netloc.replace("www.", "")
    score = 0
    
    # Primary academic/official sources
    if host in HIGH_VALUE_DOMAINS:
        score += 60
    
    # Reputable news sources
    if host in REPUTABLE_NEWS_DOMAINS:
        score += 40
    
    # DOI links are gold standard
    if "doi.org/" in u:
        score += 80
    
    # arXiv preprints
    if "arxiv.org/" in u:
        score += 50
    
    # PDF documents often contain original research
    if any(x in u for x in ["/pdf", ".pdf"]):
        score += 20
    
    # Research paper indicators
    if any(x in u for x in ["paper", "publication", "journal", "conference"]):
        score += 15
    
    # Official documentation
    if any(x in u for x in ["/docs/", "/documentation/", "reference", "spec"]):
        score += 10
    
    # References/bibliography pages
    if any(x in u for x in ["references", "bibliography", "citations"]):
        score += 10
    
    # Press releases (lower value but still official)
    if "press-release" in u or "newsroom" in u:
        score += 5
    
    # Deprioritize social media
    for pattern in LOW_VALUE_PATTERNS:
        if pattern in host or pattern in u:
            score -= 70
    
    # Deprioritize tracking parameters
    if any(x in u for x in ["utm_", "fbclid=", "gclid=", "share="]):
        score -= 5
    
    # Penalize self-citations (same domain as article)
    if article_domain and host == article_domain:
        score -= 20
    
    # Boost .edu and .gov domains
    if host.endswith(".edu"):
        score += 25
    if host.endswith(".gov"):
        score += 30
    
    # Penalize very long URLs (often auto-generated / low quality)
    if len(u) > 200:
        score -= 10
    
    return score


def pick_top_sources(
    links: List[str],
    article_url: str = "",
    n: int = 5,
    min_score: int = 0,
) -> List[Tuple[str, int]]:
    """
    Select top-N links by heuristic score.
    
    Returns:
        List of (url, score) tuples
    """
    article_domain = urlparse(article_url).netloc.replace("www.", "") if article_url else ""
    
    scored = []
    for link in links:
        score = score_link(link, article_domain)
        if score > min_score:
            scored.append((score, link))
    
    scored.sort(reverse=True)
    return [(link, score) for score, link in scored[:n]]


# ---------------------------
# Parallel source fetching
# ---------------------------

def fetch_source_text(url: str, max_chars: int = 12_000) -> Dict[str, Any]:
    """
    Fetch and extract text from a cited source URL.
    
    Returns:
        {url, ok, reason, text, paywall_detected}
    """
    fetch_result = fetch_html(url)
    
    if not fetch_result.ok:
        return {
            "url": url,
            "ok": False,
            "reason": f"fetch_failed: {fetch_result.error}",
            "text": "",
            "paywall_detected": False,
        }
    
    html = fetch_result.html
    
    # Extract text
    text = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=True,
        favor_precision=True,
        deduplicate=True,
    ) or ""
    text = text.strip()
    
    # Fallback
    if not text or len(text) < 500:
        try:
            text = _readability_fallback_text(html)
        except Exception:
            pass
    
    text = (text or "").strip()
    
    # Detect paywall
    paywall_detected = detect_paywall(html, text)
    
    if len(text) < 500:
        return {
            "url": url,
            "ok": False,
            "reason": "insufficient_text_or_paywall" if paywall_detected else "insufficient_text",
            "text": text[:max_chars],
            "paywall_detected": paywall_detected,
        }
    
    return {
        "url": url,
        "ok": True,
        "reason": "",
        "text": text[:max_chars],
        "paywall_detected": paywall_detected,
    }


def fetch_sources_parallel(
    urls: List[str],
    max_chars_each: int = 12_000,
    max_workers: int = 4,
) -> List[Dict[str, Any]]:
    """
    Fetch multiple sources in parallel using thread pool.
    
    Args:
        urls: List of URLs to fetch
        max_chars_each: Max characters per source
        max_workers: Number of parallel workers
        
    Returns:
        List of source packets (same order as input URLs)
    """
    packets = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {
            executor.submit(fetch_source_text, url, max_chars_each): url
            for url in urls
        }
        
        for future in as_completed(future_to_url):
            try:
                packet = future.result()
                packets.append(packet)
            except Exception as e:
                url = future_to_url[future]
                packets.append({
                    "url": url,
                    "ok": False,
                    "reason": f"exception: {str(e)[:200]}",
                    "text": "",
                    "paywall_detected": False,
                })
    
    # Return in original order
    url_to_packet = {p["url"]: p for p in packets}
    return [url_to_packet.get(url, {
        "url": url,
        "ok": False,
        "reason": "not_processed",
        "text": "",
        "paywall_detected": False,
    }) for url in urls]


def gather_cited_sources(
    article_url: str,
    article_html: str,
    max_sources: int = 5,
    max_chars_each: int = 12_000,
    parallel: bool = True,
    max_attempts: int = 15,
) -> Dict[str, Any]:
    """
    End-to-end: extract links, rank, fetch sources.
    
    Keeps fetching until we have max_sources non-paywalled sources,
    up to max_attempts total fetches.
    
    Args:
        article_url: URL of the article
        article_html: HTML content of article
        max_sources: Target number of successful (non-paywalled) sources
        max_chars_each: Max characters per source
        parallel: Use parallel fetching
        max_attempts: Maximum sources to try before giving up
    
    Returns:
        {
            all_links_count: Total outbound links found,
            selected_links_with_scores: [(url, score), ...] of all attempted,
            source_packets: [{url, ok, reason, text, paywall_detected}, ...],
            successful_sources: Number of usable sources,
            paywalled_sources: Number of paywalled sources,
            failed_sources: Number of failed sources,
            paywall_percentage: Percentage of attempted sources that were paywalled,
            attempted_count: Total sources attempted
        }
    """
    links = extract_outbound_links(article_url, article_html)
    all_ranked = pick_top_sources(links, article_url, n=max_attempts, min_score=0)
    
    successful_packets = []
    paywalled_packets = []
    failed_packets = []
    attempted_sources = []
    
    # Process in batches for efficiency
    batch_size = 5 if parallel else 3
    index = 0
    
    while len(successful_packets) < max_sources and index < len(all_ranked):
        # Get next batch
        batch_end = min(index + batch_size, len(all_ranked))
        batch = [url for url, score in all_ranked[index:batch_end]]
        attempted_sources.extend([(url, score) for url, score in all_ranked[index:batch_end]])
        
        # Fetch batch
        if parallel and len(batch) > 1:
            packets = fetch_sources_parallel(batch, max_chars_each)
        else:
            packets = [fetch_source_text(url, max_chars_each) for url in batch]
        
        # Categorize results
        for packet in packets:
            if packet.get("ok"):
                successful_packets.append(packet)
            elif packet.get("paywall_detected") or "paywall" in packet.get("reason", "").lower():
                paywalled_packets.append(packet)
            else:
                failed_packets.append(packet)
        
        index = batch_end
        
        # Stop if we have enough successful sources
        if len(successful_packets) >= max_sources:
            break
    
    # Combine all packets for backward compatibility
    all_packets = successful_packets + paywalled_packets + failed_packets
    
    # Calculate statistics
    total_attempted = len(attempted_sources)
    num_successful = len(successful_packets)
    num_paywalled = len(paywalled_packets)
    num_failed = len(failed_packets)
    
    paywall_percentage = 0
    if total_attempted > 0:
        paywall_percentage = round((num_paywalled / total_attempted) * 100, 1)
    
    return {
        "all_links_count": len(links),
        "selected_links_with_scores": attempted_sources,
        "source_packets": all_packets,
        "successful_sources": num_successful,
        "paywalled_sources": num_paywalled,
        "failed_sources": num_failed,
        "paywall_percentage": paywall_percentage,
        "attempted_count": total_attempted,
    }
