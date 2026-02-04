
"""
Streamlined AI Newsletter Article Analysis
- No sidebar, cleaner UI
- Progressive inline results display
- Step-by-step highlighting
"""

import json
import uuid
import re
import time
import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from urllib.parse import urlparse
from ipaddress import ip_address, IPv4Address, IPv6Address

import streamlit as st

from airtable_storage import AirtableStorage
from improved_llm import LLMClient, estimate_tokens, estimate_cost
from improved_extraction import extract_article, gather_cited_sources
from pathlib import Path


# Configuration (hardcoded)
MAX_SOURCES = 5
MAX_CHARS_EACH = 18000
AUDIENCE = "Nonprofit AI community: engineers, founders, policy experts, and researchers."
MISSION = "Accuracy-first AI literacy. Avoid hype. Prioritize evidence and transparency."

# Rate limiting configuration
MAX_SUBMISSIONS_PER_HOUR = 5
MAX_SUBMISSIONS_PER_DAY = 20

# ============================================================================
# CONFIGURATION HELPERS
# ============================================================================

def get_secret(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Get secret from environment variables (Render) or Streamlit secrets (local).
    
    Checks in this order:
    1. Environment variables (for Render deployment)
    2. Streamlit secrets (for local development)
    3. Default value
    
    Args:
        key: Secret key to retrieve
        default: Default value if not found
        
    Returns:
        Secret value or default
    """
    # First check environment variables (Render, production)
    value = os.getenv(key)
    if value is not None:
        return value
    
    # Fall back to Streamlit secrets (local development)
    try:
        if hasattr(st, 'secrets') and key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    
    # Return default if provided
    return default


# ============================================================================
# INPUT SANITIZATION & VALIDATION
# ============================================================================

def sanitize_text(text: str, max_length: int = 500) -> str:
    """
    Sanitize text input to prevent XSS and limit length.
    
    Args:
        text: Raw text input
        max_length: Maximum allowed length
        
    Returns:
        Sanitized text
    """
    if not text:
        return ""
    
    # Remove any HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Remove potentially dangerous characters
    text = text.replace('<', '').replace('>', '').replace('"', '').replace("'", '')
    
    # Limit length
    text = text[:max_length].strip()
    
    return text


def validate_email(email: str) -> bool:
    """
    Validate email format.
    
    Args:
        email: Email address to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not email:
        return True  # Email is optional
    
    # Basic email regex pattern
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_url(url: str) -> tuple[bool, str]:
    """
    Validate URL and check for security issues.
    
    Args:
        url: URL to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not url or not url.strip():
        return False, "URL is required"
    
    url = url.strip()
    
    # Check protocol
    if not url.startswith(('http://', 'https://')):
        return False, "URL must start with http:// or https://"
    
    try:
        parsed = urlparse(url)
        
        # Check for valid scheme
        if parsed.scheme not in ['http', 'https']:
            return False, "Only HTTP and HTTPS protocols are allowed"
        
        # Check for hostname
        if not parsed.hostname:
            return False, "Invalid URL: missing hostname"
        
        # Block localhost and private IPs
        blocked_hosts = [
            'localhost',
            '127.0.0.1',
            '0.0.0.0',
            '[::]',
            '[::1]'
        ]
        
        if parsed.hostname.lower() in blocked_hosts:
            return False, "Cannot analyze localhost URLs"
        
        # Check for private IP ranges
        try:
            ip = ip_address(parsed.hostname)
            if ip.is_private or ip.is_loopback or ip.is_reserved:
                return False, "Cannot analyze private or internal IP addresses"
        except ValueError:
            # Not an IP address, which is fine (it's a domain name)
            pass
        
        # Block file:// and other dangerous schemes
        if parsed.scheme not in ['http', 'https']:
            return False, "Only HTTP and HTTPS URLs are allowed"
        
        # Check URL length
        if len(url) > 2000:
            return False, "URL is too long (max 2000 characters)"
        
        return True, ""
        
    except Exception as e:
        return False, f"Invalid URL format: {str(e)}"


# ============================================================================
# RATE LIMITING
# ============================================================================

def init_rate_limit_state():
    """Initialize rate limiting session state."""
    if 'submission_times' not in st.session_state:
        st.session_state.submission_times = []


def check_rate_limit() -> tuple[bool, str, int]:
    """
    Check if user has exceeded rate limits.
    
    Returns:
        Tuple of (is_allowed, error_message, remaining_submissions)
    """
    init_rate_limit_state()
    
    current_time = time.time()
    
    # Clean up old submissions (older than 24 hours)
    st.session_state.submission_times = [
        t for t in st.session_state.submission_times 
        if current_time - t < 86400  # 24 hours
    ]
    
    # Count recent submissions
    one_hour_ago = current_time - 3600
    recent_submissions = [
        t for t in st.session_state.submission_times 
        if t > one_hour_ago
    ]
    
    daily_submissions = len(st.session_state.submission_times)
    hourly_submissions = len(recent_submissions)
    
    # Check hourly limit
    if hourly_submissions >= MAX_SUBMISSIONS_PER_HOUR:
        time_until_reset = 3600 - (current_time - min(recent_submissions))
        minutes_remaining = int(time_until_reset / 60)
        return False, f"Rate limit exceeded. You can submit {MAX_SUBMISSIONS_PER_HOUR} articles per hour. Please wait {minutes_remaining} minutes.", 0
    
    # Check daily limit
    if daily_submissions >= MAX_SUBMISSIONS_PER_DAY:
        oldest_submission = min(st.session_state.submission_times)
        time_until_reset = 86400 - (current_time - oldest_submission)
        hours_remaining = int(time_until_reset / 3600)
        return False, f"Daily limit reached. You can submit {MAX_SUBMISSIONS_PER_DAY} articles per day. Please wait {hours_remaining} hours.", 0
    
    # Calculate remaining submissions
    remaining_hourly = MAX_SUBMISSIONS_PER_HOUR - hourly_submissions
    remaining_daily = MAX_SUBMISSIONS_PER_DAY - daily_submissions
    remaining = min(remaining_hourly, remaining_daily)
    
    return True, "", remaining


def record_submission():
    """Record a submission for rate limiting."""
    init_rate_limit_state()
    st.session_state.submission_times.append(time.time())


def get_rate_limit_info() -> str:
    """Get current rate limit status as formatted string."""
    init_rate_limit_state()
    
    current_time = time.time()
    one_hour_ago = current_time - 3600
    
    # Clean old entries
    st.session_state.submission_times = [
        t for t in st.session_state.submission_times 
        if current_time - t < 86400
    ]
    
    hourly_count = len([t for t in st.session_state.submission_times if t > one_hour_ago])
    daily_count = len(st.session_state.submission_times)
    
    return f"📊 Usage: {hourly_count}/{MAX_SUBMISSIONS_PER_HOUR} this hour • {daily_count}/{MAX_SUBMISSIONS_PER_DAY} today"


def search_external_sources_via_web(
    article_title: str,
    key_claims: list,
    verification_focus: str,
    llm_client: LLMClient,
    num_sources_needed: int = 2
) -> list[tuple[str, int, str]]:
    """
    Search for external sources using LLM with web search capability.
    
    Args:
        article_title: Title of the article being verified
        key_claims: List of key claims from analysis
        verification_focus: User's specified focus areas
        llm_client: LLM client with web search capability
        num_sources_needed: Number of external sources to find
        
    Returns:
        List of tuples: (url, score, source_type)
        where source_type is 'external'
    """
    external_sources = []
    
    try:
        # Build search query based on verification focus or claims
        if verification_focus and verification_focus.strip():
            base_query = verification_focus[:80]
            context = f"focusing on: {verification_focus}"
        elif key_claims and len(key_claims) > 0:
            first_claim = key_claims[0] if isinstance(key_claims[0], str) else str(key_claims[0])
            base_query = first_claim[:80]
            context = f"related to claim: {first_claim[:60]}"
        else:
            base_query = article_title[:80] if article_title else "fact check"
            context = f"about: {article_title[:60]}"
        
        st.caption(f"🔍 Searching for external sources {context}...")
        
        # Create search prompt for LLM
        search_prompt = f"""Find {num_sources_needed} high-quality, authoritative sources to verify claims about: {base_query}

Priority:
1. Academic papers, research studies
2. Reputable news organizations
3. Government/official statistics
4. Industry reports from established firms

Return ONLY a JSON array of URLs, like:
["https://example.com/source1", "https://example.com/source2"]"""

        # Call LLM with web search enabled (if using Claude/Anthropic this works automatically)
        try:
            # Make a simple call - Claude will use web_search tool if needed
            result = llm_client.call(
                system="You are a research assistant finding authoritative sources. Use web search to find the best sources.",
                user=search_prompt,
                max_tokens=500,
                temperature=0.3
            )
            
            response_text = result.get("text", "")
            
            # Try to parse URLs from response
            import re
            url_pattern = r'https?://[^\s\"\'\)]+(?:[^\s\"\'\)])'
            found_urls = re.findall(url_pattern, response_text)
            
            # Clean and validate URLs
            for url in found_urls[:num_sources_needed * 2]:
                url = url.rstrip('.,;:)')
                if url.startswith('http'):
                    # Score external sources at 75 (decent but below cited)
                    external_sources.append((url, 75, 'external'))
            
            if external_sources:
                st.caption(f"✅ Found {len(external_sources)} external sources via search")
            else:
                st.caption("⚠️ No external sources found - using cited sources only")
                
        except Exception as e:
            st.caption(f"⚠️ Search unavailable: {str(e)[:50]}")
            
    except Exception as e:
        st.caption(f"⚠️ External search error: {str(e)[:50]}")
    
    return external_sources[:num_sources_needed]


def validate_api_key(provider: str, api_key: str) -> tuple[bool, str]:
    """
    Validate an API key by making a minimal test call.
    
    Args:
        provider: 'openai' or 'anthropic'
        api_key: API key to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        # Try to create client with user key
        test_client = LLMClient(provider=provider, user_api_key=api_key)
        
        # Make minimal test call (shortest possible)
        test_response = test_client.call(
            system="You are a helpful assistant.",
            user="Say 'OK' if you can read this.",
            max_tokens=10,
            temperature=0
        )
        
        if test_response and test_response.get("text"):
            return True, ""
        else:
            return False, "API key validation failed - no response received"
            
    except Exception as e:
        return False, f"API key validation error: {str(e)}"


def load_prompt(name: str) -> str:
    """Load prompt from file."""
    path = Path(__file__).parent / "prompts" / name
    if not path.exists():
        path = Path(name)
    if not path.exists():
        raise FileNotFoundError(f"Prompt not found: {name}")
    return path.read_text(encoding="utf-8")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def cached_extract_article(url: str) -> dict:
    return extract_article(url)


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def cached_gather_sources(
    article_url: str, 
    article_html: str, 
    max_sources: int, 
    max_chars_each: int,
    max_attempts: int = 15,
) -> dict:
    return gather_cited_sources(
        article_url=article_url,
        article_html=article_html,
        max_sources=max_sources,
        max_chars_each=max_chars_each,
        parallel=True,
        max_attempts=max_attempts,
    )


def build_editor_packet(metadata: dict, analysis: dict, verification: dict) -> dict:
    """Build editor-friendly summary packet."""
    key_claims = analysis.get("key_claims", []) or []
    top_bullets = []
    for c in key_claims:
        if isinstance(c, dict) and c.get("claim"):
            importance = c.get("importance", "medium")
            claim_text = c["claim"].strip()
            if importance == "high":
                top_bullets.append(f"🔥 {claim_text}")
            else:
                top_bullets.append(claim_text)
    top_bullets = top_bullets[:3]
    
    confidence_support = verification.get("confidence_support", []) or []
    editor_cautions = verification.get("editor_cautions", []) or []
    
    confidence = (
        verification.get("final_confidence_level")
        or analysis.get("confidence_level")
        or "medium"
    ).strip().lower()
    
    recommended_section = "Top Stories"
    headline = (metadata.get("title") or "Article Submission").strip()
    why_now = (analysis.get("summary") or "").strip()
    
    return {
        "headline": headline,
        "recommended_section": recommended_section,
        "why_now": why_now,
        "top_bullets": top_bullets,
        "risks_or_cautions": editor_cautions,
        "confidence": confidence,
        "confidence_support": confidence_support,
        "suggested_copy": {
            "blurb_1_2_sentences": why_now,
            "cta_question": "What implications does this have for our community?",
        },
    }


# Streamlit App
st.set_page_config(
    page_title="Nerd Lawyer Article Verifier",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Initialize session state
if "total_tokens" not in st.session_state:
    st.session_state.total_tokens = 0

# Header with SVG
try:
    st.image("header-with-logo.svg", use_container_width=True)
except:
    st.title("🤖 Nerd Lawyer Article Verifier")
    st.caption("Created by ")

# Description
st.markdown("""
<div style='background-color: #f0f9ff; padding: 20px; border-radius: 10px; margin: 20px 0; border-left: 4px solid #2dd4bf;'>
    <h3 style='margin-top: 0; color: #1a1a1a;'>Verify Your Sources</h3>
    <p style='color: #4a5568; line-height: 1.6; margin-bottom: 10px;'>
        This AI-powered verification tool analyzes the factual claims made in an article, examines the sources cited in support of those claims, and evaluates overall credibility. By verifying that sources actually exist, are authoritative, and accurately support the statements attributed to them, the tool helps distinguish well-supported reporting from unsupported or misleading assertions. In an era of rapid information sharing and AI-generated content, verifying sources is essential to maintaining trust, accountability, and accuracy. This tool empowers readers, researchers, and professionals to independently confirm claims and rely on information with greater confidence.
    </p>
</div>
""", unsafe_allow_html=True)

st.divider()

# Load Prompts
try:
    ANALYSIS_PROMPT = load_prompt("improved_analysis.txt")
    VERIFICATION_PROMPT = load_prompt("improved_verification_external.txt")
except FileNotFoundError as e:
    st.error(f"❌ Prompt file not found: {e}")
    st.stop()

# Main UI Layout
col1, col2 = st.columns([2, 1], gap="large")

with col1:
    st.subheader("📝 Submit Article")
    
    # Rate limit info
    st.caption(get_rate_limit_info())
    
    url = st.text_input(
        "Article URL",
        placeholder="https://example.com/article",
        help="Enter the full URL of the article to analyze",
        max_chars=2000,
    )
    
    # Validate URL in real-time
    url_valid = True
    url_error = ""
    if url.strip():
        url_valid, url_error = validate_url(url.strip())
        if not url_valid:
            st.error(f"⚠️ {url_error}")
    
    col_a, col_b = st.columns(2)
    with col_a:
        submitter_name = st.text_input(
            "Your Name (optional)",
            max_chars=100,
            help="Maximum 100 characters"
        )
    with col_b:
        submitter_email = st.text_input(
            "Your Email (optional)",
            max_chars=100,
            help="Maximum 100 characters"
        )
    
    # Validate email in real-time
    email_valid = True
    if submitter_email.strip() and not validate_email(submitter_email.strip()):
        st.error("⚠️ Invalid email format")
        email_valid = False
    
    submitter_notes = st.text_area(
        "Are there specific aspects of the article that you would like to verify? (optional)",
        height=80,
        max_chars=500,
        placeholder="E.g., 'Verify the statistics about AI adoption' or 'Check claims about company valuations'...",
        help="Specify particular claims or topics to focus verification on. This will help find more relevant sources.",
        key="verification_focus"
    )
    
    # LLM Provider (moved to main page)
    llm_provider = st.selectbox(
        "LLM Provider",
        options=["openai", "anthropic"],
        index=0,
        help="Choose which LLM to use for analysis",
    )
    
    # Number of sources slider
    st.markdown("**Verification Depth**")
    num_sources = st.slider(
        "Number of sources to verify",
        min_value=3,
        max_value=10,
        value=5,
        step=1,
        help="More sources = more thorough verification but higher cost. Each source adds ~$0.50-1.00 to the analysis.",
        key="num_sources_slider"
    )
    
    # Show dynamic pricing estimate
    base_cost = 2.00  # Base analysis cost
    per_source_cost = 0.75  # Cost per source
    estimated_cost = base_cost + (num_sources * per_source_cost)
    
    # Apply BYOK discount if active
    if st.session_state.get('user_api_key'):
        estimated_cost = estimated_cost * 0.5
        pricing_text = f"💰 Estimated cost: ~${estimated_cost:.2f} (with your API key - 50% off)"
    else:
        pricing_text = f"💵 Estimated cost: ~${estimated_cost:.2f}"
    
    st.caption(pricing_text)
    
    # Bring Your Own API Key (BYOK) - Optional
    with st.expander("💰 Use Your Own API Key (Get Discounts!)", expanded=False):
        st.markdown("""
        **Save money by using your own API key!**
        
        If you provide your own OpenAI or Anthropic API key:
        - ✅ **50% discount** on all analyses
        - ✅ Pay only for actual API usage (typically $0.10-0.30 per article)
        - ✅ No markup - direct API pricing
        - ✅ Your key, your control
        
        **Without your own key:** Standard pricing applies ($3-5 per article)
        """)
        
        use_own_key = st.checkbox("I want to use my own API key", key="use_own_key")
        
        user_api_key = None
        if use_own_key:
            if llm_provider == "openai":
                st.info("📝 Get your OpenAI API key at: https://platform.openai.com/api-keys")
                user_api_key = st.text_input(
                    "OpenAI API Key",
                    type="password",
                    placeholder="sk-proj-...",
                    help="Your key is never stored - only used for this analysis",
                    key="user_openai_key"
                )
                if user_api_key and not user_api_key.startswith("sk-"):
                    st.warning("⚠️ OpenAI keys typically start with 'sk-'")
                    
            elif llm_provider == "anthropic":
                st.info("📝 Get your Anthropic API key at: https://console.anthropic.com/settings/keys")
                user_api_key = st.text_input(
                    "Anthropic API Key",
                    type="password",
                    placeholder="sk-ant-...",
                    help="Your key is never stored - only used for this analysis",
                    key="user_anthropic_key"
                )
                if user_api_key and not user_api_key.startswith("sk-ant-"):
                    st.warning("⚠️ Anthropic keys typically start with 'sk-ant-'")
            
            # Add validation button
            if user_api_key:
                col_val1, col_val2 = st.columns([1, 3])
                with col_val1:
                    validate_btn = st.button("🔍 Test Key", key="validate_key_btn")
                with col_val2:
                    if validate_btn:
                        with st.spinner("Testing API key..."):
                            is_valid, error_msg = validate_api_key(llm_provider, user_api_key)
                            if is_valid:
                                st.success("✅ API key is valid!")
                                st.session_state.key_validated = True
                            else:
                                st.error(f"❌ Invalid API key: {error_msg}")
                                st.session_state.key_validated = False
                
                # Show status if previously validated
                if st.session_state.get('key_validated'):
                    st.success("✅ Your API key is validated (50% discount applied!)")
                elif user_api_key and not validate_btn:
                    st.info("👆 Click 'Test Key' to validate your API key before running analysis")
            else:
                st.info("👆 Enter your API key above to activate the discount")
    
    # Store user key in session state for use in analysis
    if 'user_api_key' not in st.session_state or not use_own_key:
        st.session_state.user_api_key = user_api_key if use_own_key else None
    else:
        st.session_state.user_api_key = user_api_key
    
    # Check rate limit
    rate_limit_ok, rate_limit_msg, remaining_submissions = check_rate_limit()
    
    # Show rate limit warning if close to limit
    if remaining_submissions <= 2 and remaining_submissions > 0:
        st.warning(f"⚠️ You have {remaining_submissions} submissions remaining in this period")
    
    run_btn = st.button(
        "🚀 Run Analysis",
        type="primary",
        disabled=not bool(url.strip()) or not url_valid or not email_valid or not rate_limit_ok,
        use_container_width=True,
    )
    
    # Show rate limit error if exceeded
    if not rate_limit_ok and url.strip():
        st.error(f"🚫 {rate_limit_msg}")

with col2:
    st.subheader("ℹ️ How It Works")
    st.markdown(f"""
    1. **Extract** article content & metadata
    2. **Analyze** claims & assess evidence
    3. **Verify** against sources ({num_sources} sources: cited + external search)
    4. **Score** confidence with rationale
    5. **Save** results to Airtable
    
    **Current Configuration:**
    - Sources verified: {num_sources} (📄 cited + 🔍 searched)
    - Content per source: 18,000 chars
    - LLM: {llm_provider.upper()}
    
    **💰 Cost Breakdown:**
    - Base analysis: $2.00
    - Per source ({num_sources}): ${num_sources * 0.75:.2f}
    - **Total: ~${2.00 + num_sources * 0.75:.2f}**
    
    With your API key: **50% OFF** (~${(2.00 + num_sources * 0.75) * 0.5:.2f})
    """)
    
    # Cost tracking
    total_tokens = st.session_state.get("total_tokens", 0)
    if total_tokens > 0:
        cost = estimate_cost(total_tokens, provider=llm_provider, model="gpt-4o-mini")
        
        # Apply discount if using user's key
        if st.session_state.get('user_api_key'):
            discounted_cost = cost * 0.5
            st.metric("Session Cost", f"${discounted_cost:.3f}", delta=f"-50% (saved ${cost * 0.5:.3f})")
        else:
            st.metric("Session Cost", f"${cost:.3f}")

# Analysis Pipeline
if run_btn:
    # Double-check rate limit (in case of race condition)
    rate_limit_ok, rate_limit_msg, _ = check_rate_limit()
    if not rate_limit_ok:
        st.error(f"🚫 {rate_limit_msg}")
        st.stop()
    
    # Record this submission for rate limiting
    record_submission()
    
    # Sanitize all text inputs
    sanitized_url = url.strip()
    sanitized_name = sanitize_text(submitter_name.strip(), max_length=100)
    sanitized_email = sanitize_text(submitter_email.strip(), max_length=100)
    sanitized_notes = sanitize_text(submitter_notes.strip(), max_length=500)
    
    article_id = str(uuid.uuid4())
    
    # Initialize card
    card = {
        "card_version": "1.3",  # Updated version
        "article_id": article_id,
        "created_at": now_iso(),
        "metadata": {
            "url": sanitized_url,
            "title": "",
            "author": "",
            "publisher": "",
            "publish_date": "",
            "submitter_name": sanitized_name,
            "submitter_email": sanitized_email,
            "submitter_notes": sanitized_notes,  # Now contains verification focus
            "verification_focus": sanitized_notes,  # Explicit field for focus
        },
        "inputs": {
            "audience_description": AUDIENCE,
            "mission_lens": MISSION,
            "llm_provider": llm_provider,
            "external_verification": {
                "max_sources": num_sources,  # Dynamic based on slider
                "max_chars_each": MAX_CHARS_EACH,
                "verification_focus": sanitized_notes,  # User's focus areas
            },
        },
        "content": {},
        "sources": {},
        "analysis": None,
        "verification": None,
        "editor_packet": None,
    }
    
    st.divider()
    st.subheader("📊 Analysis Progress")
    
    # Create placeholder containers for each step
    step1_container = st.container()
    step2_container = st.container()
    step3_container = st.container()
    step4_container = st.container()
    step5_container = st.container()
    
    try:
        # Step 1: Extract Article
        with step1_container:
            st.markdown("### 1️⃣ Extract article content and metadata")
            with st.spinner("Extracting..."):
                article = cached_extract_article(url.strip())
                
                card["metadata"].update({
                    "title": article.get("title", ""),
                    "author": article.get("author", ""),
                    "publisher": article.get("publisher", ""),
                    "publish_date": article.get("publish_date", ""),
                })
                card["content"].update({
                    "extracted_text": article.get("text", ""),
                    "extraction_notes": article.get("notes", []),
                    "paywall_detected": article.get("paywall_detected", False),
                    "is_fresh": article.get("is_fresh", False),
                })
                
                extracted_text = card["content"]["extracted_text"]
                article_html = article.get("html", "")
                
                # Display results
                st.success("✅ Extraction complete")
                
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    st.metric("Characters", f"{len(extracted_text):,}")
                with col_b:
                    st.metric("Publisher", article.get("publisher", "Unknown"))
                with col_c:
                    paywall_status = "⚠️ Yes" if card["content"]["paywall_detected"] else "✅ No"
                    st.metric("Paywall", paywall_status)
                
                # Show article summary info
                with st.expander("📄 Article Metadata", expanded=False):
                    st.write(f"**Title:** {card['metadata']['title']}")
                    st.write(f"**Author:** {card['metadata']['author']}")
                    st.write(f"**Publisher:** {card['metadata']['publisher']}")
                    st.write(f"**Published:** {card['metadata']['publish_date']}")
                    st.write(f"**Fresh:** {'Yes' if card['content']['is_fresh'] else 'No (>90 days old)'}")
                
                if len(extracted_text) < 1000:
                    st.error("❌ Extraction too short – may be paywall or JS-heavy page")
                    st.stop()
        
        # Step 2: LLM Analysis
        with step2_container:
            st.markdown("### 2️⃣ Analyze claims and assess evidence quality")
            with st.spinner("Analyzing..."):
                # Use user's API key if provided, otherwise use system key
                user_key = st.session_state.get('user_api_key')
                llm = LLMClient(provider=llm_provider, user_api_key=user_key)
                
                # Show discount message if using own key
                if user_key:
                    st.info("💰 Using your API key - 50% discount applied!")
                
                analysis_user = f"""
Audience: {AUDIENCE}

Mission: {MISSION}

ARTICLE TEXT:
{extracted_text[:20000]}
""".strip()
                
                analysis = llm.call(ANALYSIS_PROMPT, analysis_user, max_tokens=4000)
                card["analysis"] = analysis
                
                # Defensive defaults
                analysis.setdefault("key_claims", [])
                analysis.setdefault("claim_assessments", [])
                analysis.setdefault("uncertainties", [])
                analysis.setdefault("confidence_level", "medium")
                analysis.setdefault("reasoning", "")
                
                st.success("✅ Analysis complete")
                
                # Display claims
                key_claims = analysis.get("key_claims", [])
                st.write(f"**Extracted {len(key_claims)} key claims:**")
                
                for i, claim in enumerate(key_claims, 1):
                    claim_text = claim.get("claim", "")
                    claim_type = claim.get("type", "")
                    importance = claim.get("importance", "")
                    
                    # Importance emoji
                    importance_emoji = {
                        "high": "🔥",
                        "medium": "📌",
                        "low": "📎"
                    }.get(importance, "📌")
                    
                    st.markdown(f"{i}. {importance_emoji} **{claim_text}** *({claim_type})*")
                
                # Show confidence and summary in expander
                with st.expander("📊 Analysis Details", expanded=False):
                    st.write(f"**Summary:** {analysis.get('summary', '')}")
                    st.write(f"**Initial Confidence:** {analysis.get('confidence_level', 'medium').upper()}")
                    st.write(f"**Reasoning:** {analysis.get('reasoning', '')}")
                    
                    uncertainties = analysis.get("uncertainties", [])
                    if uncertainties:
                        st.write("**Uncertainties:**")
                        for unc in uncertainties:
                            st.write(f"- {unc}")
        
        # Step 3: Gather Cited Sources
        with step3_container:
            st.markdown("### 3️⃣ Gather cited sources and search for external verification")
            with st.spinner("Fetching cited sources..."):
                sources_bundle = cached_gather_sources(
                    article_url=url.strip(),
                    article_html=article_html,
                    max_sources=num_sources,  # Use slider value
                    max_chars_each=MAX_CHARS_EACH,
                )
                
                card["sources"] = sources_bundle
                
                all_links = sources_bundle.get("all_links_count", 0)
                selected = sources_bundle.get("selected_links_with_scores", [])
                packets = sources_bundle.get("source_packets", [])
                
                # Track source types
                for packet in packets:
                    if 'source_type' not in packet:
                        packet['source_type'] = 'cited'  # Mark existing as cited
                
                # New statistics
                successful_cited = sources_bundle.get("successful_sources", 0)
                paywalled = sources_bundle.get("paywalled_sources", 0)
                failed = sources_bundle.get("failed_sources", 0)
                attempted = sources_bundle.get("attempted_count", len(selected))
                paywall_pct = sources_bundle.get("paywall_percentage", 0)
                
                st.success(f"✅ Found {successful_cited} cited sources")
                
                # Search for external sources if we need more
                external_packets = []
                if successful_cited < num_sources:
                    num_external_needed = min(num_sources - successful_cited, 3)  # Cap at 3 external
                    
                    with st.spinner(f"🔍 Searching for {num_external_needed} external sources..."):
                        # Get article metadata for search context
                        article_title = extracted_metadata.get("title", "")
                        key_claims = analysis.get("key_claims", [])
                        
                        # Search for external sources
                        external_urls = search_external_sources_via_web(
                            article_title=article_title,
                            key_claims=key_claims,
                            verification_focus=sanitized_notes,
                            llm_client=llm,
                            num_sources_needed=num_external_needed
                        )
                        
                        # Fetch external sources
                        if external_urls:
                            from improved_extraction import fetch_source_text
                            
                            for ext_url, score, source_type in external_urls:
                                packet = fetch_source_text(ext_url, MAX_CHARS_EACH)
                                packet['source_type'] = source_type  # Mark as 'external'
                                packet['search_score'] = score
                                
                                if packet.get("ok"):
                                    external_packets.append(packet)
                                    selected.append((ext_url, score))  # Add to selected list
                            
                            st.success(f"✅ Found {len(external_packets)} external sources")
                        
                        # Combine all packets
                        packets.extend(external_packets)
                
                # Update statistics
                successful = successful_cited + len(external_packets)
                
                # Display metrics
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    st.metric("Links Found", all_links)
                with col_b:
                    st.metric("Sources Verified", f"{successful}/{num_sources}")
                with col_c:
                    paywall_color = "🔴" if paywall_pct > 50 else "🟡" if paywall_pct > 20 else "🟢"
                    st.metric("Paywall Rate", f"{paywall_color} {paywall_pct}%")
                
                # Show breakdown if there were paywalls or failures
                if paywalled > 0 or failed > 0:
                    st.caption(f"📊 Breakdown: {successful} successful, {paywalled} paywalled, {failed} failed")
                
                # List identified sources
                # Count source types
                cited_count = len([p for p in successful_packets if p.get('source_type') == 'cited'])
                external_count = len([p for p in successful_packets if p.get('source_type') == 'external'])
                
                st.write(f"**Identified sources ({successful}/{num_sources} verified):**")
                if external_count > 0:
                    st.caption(f"📄 {cited_count} cited in article  •  🔍 {external_count} found via search")
                else:
                    st.caption("📄 = Cited in article  •  🔍 = Found via search")
                
                # Show successful sources first
                successful_packets = [p for p in packets if p.get("ok")]
                paywalled_packets = [p for p in packets if p.get("paywall_detected") or "paywall" in p.get("reason", "").lower()]
                failed_packets = [p for p in packets if not p.get("ok") and not (p.get("paywall_detected") or "paywall" in p.get("reason", "").lower())]
                
                count = 1
                for packet in successful_packets[:num_sources]:  # Use slider value
                    src_url = packet["url"]
                    display_url = src_url[:60] + "..." if len(src_url) > 60 else src_url
                    
                    # Get source type and appropriate icon
                    source_type = packet.get('source_type', 'cited')
                    icon = "🔍" if source_type == 'external' else "📄"
                    
                    # Find score
                    score = next((s for u, s in selected if u == src_url), 0)
                    st.markdown(f"{count}. {icon} [{display_url}]({src_url}) *[score: {score}]*")
                    count += 1
                
                # Show paywalled sources if any
                if paywalled_packets:
                    with st.expander(f"⚠️ {len(paywalled_packets)} Paywalled Sources", expanded=False):
                        for packet in paywalled_packets:
                            src_url = packet["url"]
                            display_url = src_url[:60] + "..." if len(src_url) > 60 else src_url
                            reason = packet.get("reason", "paywall")
                            st.markdown(f"- [{display_url}]({src_url}) *[{reason}]*")
                
                # Show failed sources if any
                if failed_packets:
                    with st.expander(f"❌ {len(failed_packets)} Failed Sources", expanded=False):
                        for packet in failed_packets:
                            src_url = packet["url"]
                            display_url = src_url[:60] + "..." if len(src_url) > 60 else src_url
                            reason = packet.get("reason", "unknown")
                            st.markdown(f"- [{display_url}]({src_url}) *[{reason}]*")
        
        # Step 4: External Verification
        with step4_container:
            st.markdown("### 4️⃣ Verify claims against sources")
            with st.spinner("Verifying..."):
                # Build verification prompt with optional focus
                verify_user_parts = [
                    "ARTICLE TEXT:",
                    extracted_text[:20000],
                    "",
                    "EXTRACTED CLAIMS:",
                    json.dumps(analysis.get("key_claims", []), ensure_ascii=False, indent=2),
                    "",
                    "CLAIM ASSESSMENTS:",
                    json.dumps(analysis.get("claim_assessments", []), ensure_ascii=False, indent=2),
                ]
                
                # Add verification focus if provided
                if sanitized_notes.strip():
                    verify_user_parts.extend([
                        "",
                        "USER'S VERIFICATION FOCUS:",
                        f"The user specifically wants to verify: {sanitized_notes}",
                        "Pay special attention to sources and claims related to these aspects.",
                    ])
                
                verify_user_parts.extend([
                    "",
                    "RETRIEVED SOURCE PACKETS:",
                    json.dumps(packets, ensure_ascii=False, indent=2)
                ])
                
                verify_user = "\n".join(verify_user_parts).strip()
                
                verification = llm.call(VERIFICATION_PROMPT, verify_user, max_tokens=4000)
                card["verification"] = verification
                
                # Defensive defaults
                verification.setdefault("per_claim_check", [])
                verification.setdefault("confidence_support", [])
                verification.setdefault("editor_cautions", [])
                verification.setdefault("final_confidence_level", "medium")
                verification.setdefault("verification_summary", "")
                
                st.success("✅ Verification complete")
                
                # Show verification summary
                final_confidence = verification.get("final_confidence_level", "medium")
                confidence_emoji = {
                    "high": "🟢",
                    "medium": "🟡",
                    "low": "🔴",
                }.get(final_confidence, "⚪")
                
                st.metric("Final Confidence", f"{confidence_emoji} {final_confidence.upper()}")
                
                # Per-claim status summary
                per_claim = verification.get("per_claim_check", [])
                if per_claim:
                    status_counts = {}
                    for item in per_claim:
                        status = item.get("status", "unclear")
                        status_counts[status] = status_counts.get(status, 0) + 1
                    
                    st.write("**Claim verification results:**")
                    col_a, col_b, col_c, col_d = st.columns(4)
                    with col_a:
                        st.metric("Corroborated", status_counts.get("corroborated", 0))
                    with col_b:
                        st.metric("Partial", status_counts.get("partial", 0))
                    with col_c:
                        st.metric("Contradicted", status_counts.get("contradicted", 0))
                    with col_d:
                        st.metric("Unclear", status_counts.get("unclear", 0))
                
                # Show detailed verification in expander
                with st.expander("🔍 Detailed Verification", expanded=False):
                    for i, item in enumerate(per_claim, 1):
                        claim = item.get("claim", "")
                        status = item.get("status", "unclear")
                        
                        status_config = {
                            "corroborated": ("🟢", "Corroborated"),
                            "contradicted": ("🔴", "Contradicted"),
                            "partial": ("🟡", "Partial"),
                            "unclear": ("⚪", "Unclear"),
                        }
                        emoji, label = status_config.get(status, ("⚪", "Unknown"))
                        
                        st.markdown(f"**{i}. {emoji} {label}:** {claim}")
                        
                        evidence = item.get("evidence", [])
                        if evidence:
                            for ev in evidence[:2]:
                                snippet = ev.get("snippet", "")
                                st.caption(f"   → {snippet}")
        
        # Step 5: Save to Airtable
        with step5_container:
            st.markdown("### 5️⃣ Save results to Airtable")
            with st.spinner("Saving..."):
                # Build editor packet
                card["editor_packet"] = build_editor_packet(
                    card["metadata"],
                    analysis,
                    verification,
                )
                
                try:
                    storage = AirtableStorage(
                        token=get_secret("AIRTABLE_TOKEN"),
                        base_id=get_secret("AIRTABLE_BASE_ID"),
                        table_name=get_secret("AIRTABLE_TABLE_NAME"),
                    )
                    saved = storage.upsert_by_article_id(card)
                    st.success(f"✅ Saved to Airtable (Record: {saved.get('id', 'unknown')})")
                except Exception as e:
                    st.warning(f"⚠️ Airtable save failed: {e}")
        
        # Final results section
        st.divider()
        st.subheader("📋 Final Results")
        
        # Confidence rationale
        col_a, col_b = st.columns(2)
        
        with col_a:
            st.markdown("**✅ What Supports Confidence**")
            support = card["editor_packet"].get("confidence_support", [])
            if support:
                for item in support:
                    st.markdown(f"- {item}")
            else:
                st.info("No supporting factors identified.")
        
        with col_b:
            st.markdown("**⚠️ Cautions & Risks**")
            cautions = card["editor_packet"].get("risks_or_cautions", [])
            if cautions:
                for item in cautions:
                    st.markdown(f"- {item}")
            else:
                st.info("No major concerns identified.")
        
        # Download button
        st.divider()
        st.download_button(
            "⬇️ Download Full Analysis (JSON)",
            data=json.dumps(card, ensure_ascii=False, indent=2),
            file_name=f"article_analysis_{article_id}.json",
            mime="application/json",
            use_container_width=True,
        )
        
    except Exception as e:
        st.error(f"❌ Analysis failed: {e}")
        import traceback
        st.code(traceback.format_exc())
