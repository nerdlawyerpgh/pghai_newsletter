# improved_app.py
"""
Streamlined AI Newsletter Article Analysis
- No sidebar, cleaner UI
- Progressive inline results display
- Step-by-step highlighting
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional

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
    page_title="AI Newsletter Article Analysis",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Initialize session state
if "total_tokens" not in st.session_state:
    st.session_state.total_tokens = 0

# Header with SVG
try:
    st.image("newsletter_header.svg", use_container_width=True)
except:
    st.title("🤖 Newsletter Submission Engine")
    st.caption("Created by Nerd Lawyer for pgh.ai")

# Description
st.markdown("""
<div style='background-color: #f0f9ff; padding: 20px; border-radius: 10px; margin: 20px 0; border-left: 4px solid #2dd4bf;'>
    <p style='color: #4a5568; line-height: 1.6; margin-bottom: 10px;'>
        This AI-powered verification tool analyzes article claims, verifies cited sources, and assesses credibility 
        to ensure the highest quality content for pgh.ai's AI newsletter readers.
    </p>
    <p style='color: #4a5568; line-height: 1.6; margin-bottom: 0;'>
        <strong>Want to use system to verify other publications?</strong> A standalone version will be available soon. Contact <a href="mailto:curt@nerdlawyer.ai">Nerd Lawyer</a> 
        for more information.
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
    
    url = st.text_input(
        "Article URL",
        placeholder="https://example.com/article",
        help="Enter the full URL of the article to analyze",
    )
    
    col_a, col_b = st.columns(2)
    with col_a:
        submitter_name = st.text_input("Your Name (optional)")
    with col_b:
        submitter_email = st.text_input("Your Email (optional)")
    
    submitter_notes = st.text_area(
        "Why are you sharing this? (optional)",
        height=80,
        placeholder="Context, relevance, or questions you have...",
    )
    
    # LLM Provider (moved to main page)
    llm_provider = st.selectbox(
        "LLM Provider",
        options=["openai", "anthropic"],
        index=0,
        help="Choose which LLM to use for analysis",
    )
    
    run_btn = st.button(
        "🚀 Run Analysis",
        type="primary",
        disabled=not bool(url.strip()),
        use_container_width=True,
    )

with col2:
    st.subheader("ℹ️ How It Works")
    st.markdown("""
    1. **Extract** article content & metadata
    2. **Analyze** claims & assess evidence
    3. **Verify** against cited sources (5 sources, 18k chars each)
    4. **Score** confidence with rationale
    5. **Save** results to Airtable
    
    **Current Configuration:**
    - Sources verified: 5
    - Content per source: 18,000 chars
    - LLM: Select below
    """)
    
    # Cost tracking
    total_tokens = st.session_state.get("total_tokens", 0)
    if total_tokens > 0:
        cost = estimate_cost(total_tokens, provider=llm_provider, model="gpt-4o-mini")
        st.metric("Session Cost", f"${cost:.3f}")

# Analysis Pipeline
if run_btn:
    article_id = str(uuid.uuid4())
    
    # Initialize card
    card = {
        "card_version": "1.2",
        "article_id": article_id,
        "created_at": now_iso(),
        "metadata": {
            "url": url.strip(),
            "title": "",
            "author": "",
            "publisher": "",
            "publish_date": "",
            "submitter_name": submitter_name.strip(),
            "submitter_email": submitter_email.strip(),
            "submitter_notes": submitter_notes.strip(),
        },
        "inputs": {
            "audience_description": AUDIENCE,
            "mission_lens": MISSION,
            "llm_provider": llm_provider,
            "external_verification": {
                "max_sources": MAX_SOURCES,
                "max_chars_each": MAX_CHARS_EACH,
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
                llm = LLMClient(provider=llm_provider)
                
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
            st.markdown("### 3️⃣ Gather and verify cited sources")
            with st.spinner("Fetching sources..."):
                sources_bundle = cached_gather_sources(
                    article_url=url.strip(),
                    article_html=article_html,
                    max_sources=MAX_SOURCES,
                    max_chars_each=MAX_CHARS_EACH,
                )
                
                card["sources"] = sources_bundle
                
                all_links = sources_bundle.get("all_links_count", 0)
                selected = sources_bundle.get("selected_links_with_scores", [])
                packets = sources_bundle.get("source_packets", [])
                
                # New statistics
                successful = sources_bundle.get("successful_sources", 0)
                paywalled = sources_bundle.get("paywalled_sources", 0)
                failed = sources_bundle.get("failed_sources", 0)
                attempted = sources_bundle.get("attempted_count", len(selected))
                paywall_pct = sources_bundle.get("paywall_percentage", 0)
                
                st.success("✅ Source gathering complete")
                
                # Display metrics
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    st.metric("Links Found", all_links)
                with col_b:
                    st.metric("Sources Verified", f"{successful}/{attempted}")
                with col_c:
                    paywall_color = "🔴" if paywall_pct > 50 else "🟡" if paywall_pct > 20 else "🟢"
                    st.metric("Paywall Rate", f"{paywall_color} {paywall_pct}%")
                
                # Show breakdown if there were paywalls or failures
                if paywalled > 0 or failed > 0:
                    st.caption(f"📊 Breakdown: {successful} successful, {paywalled} paywalled, {failed} failed")
                
                # List identified sources
                st.write("**Identified secondary sources:**")
                
                # Show successful sources first
                successful_packets = [p for p in packets if p.get("ok")]
                paywalled_packets = [p for p in packets if p.get("paywall_detected") or "paywall" in p.get("reason", "").lower()]
                failed_packets = [p for p in packets if not p.get("ok") and not (p.get("paywall_detected") or "paywall" in p.get("reason", "").lower())]
                
                count = 1
                for packet in successful_packets[:MAX_SOURCES]:
                    src_url = packet["url"]
                    display_url = src_url[:60] + "..." if len(src_url) > 60 else src_url
                    
                    # Find score
                    score = next((s for u, s in selected if u == src_url), 0)
                    st.markdown(f"{count}. ✅ [{display_url}]({src_url}) *[score: {score}]*")
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
                verify_user = f"""
ARTICLE TEXT:
{extracted_text[:20000]}

EXTRACTED CLAIMS:
{json.dumps(analysis.get("key_claims", []), ensure_ascii=False, indent=2)}

CLAIM ASSESSMENTS:
{json.dumps(analysis.get("claim_assessments", []), ensure_ascii=False, indent=2)}

RETRIEVED SOURCE PACKETS:
{json.dumps(packets, ensure_ascii=False, indent=2)}
""".strip()
                
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
                        token=st.secrets["AIRTABLE_TOKEN"],
                        base_id=st.secrets["AIRTABLE_BASE_ID"],
                        table_name=st.secrets["AIRTABLE_TABLE_NAME"],
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
