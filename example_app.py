"""
Example: Complete Newsletter Verifier App with Authentication
This shows how to integrate auth with your existing app
"""

import streamlit as st
from auth_ui import (
    show_login_page, 
    show_user_profile_sidebar, 
    show_welcome_message,
    initialize_session_state
)
from auth import check_authentication, get_user_id, get_user_email
from database import (
    get_credit_balance,
    check_sufficient_credits,
    deduct_credits,
    log_usage,
    get_user_usage_history,
    get_user_usage_stats
)

# ============================================================================
# PAGE CONFIGURATION
# ============================================================================

st.set_page_config(
    page_title="Newsletter Verifier",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# AUTHENTICATION WALL
# ============================================================================

initialize_session_state()

if not check_authentication():
    show_login_page()
    st.stop()

# User is authenticated beyond this point
show_user_profile_sidebar()

# ============================================================================
# MAIN APP
# ============================================================================

st.title("📰 Newsletter Source Verifier")
show_welcome_message()

# Get user info
user_id = get_user_id()
user_email = get_user_email()

# ============================================================================
# SIDEBAR - CREDIT BALANCE
# ============================================================================

st.sidebar.markdown("---")
st.sidebar.markdown("### 💳 Credits")

# Get credit balance
credits = get_credit_balance(user_id)

# Display balance with color coding
if credits == 0:
    st.sidebar.error(f"**Balance:** {credits} credits")
    st.sidebar.warning("⚠️ You need credits to verify sources")
elif credits < 10:
    st.sidebar.warning(f"**Balance:** {credits} credits")
    st.sidebar.info("💡 Running low! Consider purchasing more.")
else:
    st.sidebar.success(f"**Balance:** {credits} credits")

# Purchase button (placeholder for Week 2)
if st.sidebar.button("💳 Purchase Credits", use_container_width=True):
    st.sidebar.info("💡 Credit purchases will be enabled in Week 2!")

# ============================================================================
# TABS
# ============================================================================

tab1, tab2, tab3 = st.tabs(["Verify Article", "Usage History", "Account Stats"])

# ============================================================================
# TAB 1: VERIFY ARTICLE
# ============================================================================

with tab1:
    st.markdown("### Verify Newsletter Sources")
    
    # URL input
    article_url = st.text_input(
        "Article URL",
        placeholder="https://example.com/article",
        help="Enter the URL of the article you want to verify"
    )
    
    # Show estimated cost
    estimated_sources = 5  # Average article has 5 sources
    st.info(f"ℹ️ Estimated cost: **{estimated_sources} credits** (1 credit per source)")
    
    # Check button
    if st.button("🔍 Verify Sources", type="primary"):
        
        if not article_url:
            st.error("Please enter an article URL")
        
        else:
            # Check if user has sufficient credits
            credit_check = check_sufficient_credits(user_id, estimated_sources)
            
            if not credit_check['sufficient']:
                st.error(f"❌ Insufficient credits!")
                st.warning(f"You have {credit_check['balance']} credits but need {estimated_sources}.")
                st.info("💡 Purchase more credits to continue.")
            
            else:
                # User has enough credits - proceed with analysis
                with st.spinner("Analyzing article and verifying sources..."):
                    
                    # ========================================================
                    # THIS IS WHERE YOUR EXISTING ANALYSIS CODE GOES
                    # For now, we'll simulate it
                    # ========================================================
                    
                    import time
                    time.sleep(2)  # Simulate processing
                    
                    # Simulated results
                    sources_verified = 5
                    results = {
                        "article_title": "Example Article Title",
                        "claims_verified": 8,
                        "sources_found": 5,
                        "confidence_score": 0.85
                    }
                    
                    # ========================================================
                    # AFTER ANALYSIS: DEDUCT CREDITS AND LOG USAGE
                    # ========================================================
                    
                    # Deduct credits
                    deduction = deduct_credits(user_id, sources_verified)
                    
                    if deduction['success']:
                        # Log the usage
                        log_usage(
                            user_id=user_id,
                            article_url=article_url,
                            sources_verified=sources_verified,
                            cost_credits=sources_verified,
                            article_title=results['article_title'],
                            metadata=results
                        )
                        
                        # Show success message
                        st.success("✅ Analysis complete!")
                        
                        # Show results
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            st.metric("Sources Verified", results['sources_found'])
                        
                        with col2:
                            st.metric("Claims Checked", results['claims_verified'])
                        
                        with col3:
                            st.metric("Confidence Score", f"{results['confidence_score']:.0%}")
                        
                        # Show credit usage
                        st.info(f"💳 Used {sources_verified} credits | Remaining: {deduction['new_balance']} credits")
                        
                        # Show detailed results (your existing visualization code goes here)
                        with st.expander("📊 View Detailed Results"):
                            st.json(results)
                    
                    else:
                        st.error(f"❌ Error: {deduction['message']}")

# ============================================================================
# TAB 2: USAGE HISTORY
# ============================================================================

with tab2:
    st.markdown("### Your Usage History")
    
    # Get recent usage
    history = get_user_usage_history(user_id, limit=20)
    
    if not history:
        st.info("No usage history yet. Verify your first article to get started!")
    else:
        # Display as table
        import pandas as pd
        
        df = pd.DataFrame(history)
        
        # Format columns
        display_df = pd.DataFrame({
            'Date': pd.to_datetime(df['created_at']).dt.strftime('%Y-%m-%d %H:%M'),
            'Article Title': df['article_title'].fillna('Untitled'),
            'Sources': df['sources_verified'],
            'Credits Used': df['cost_credits'],
            'URL': df['article_url']
        })
        
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True
        )
        
        # Download option
        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Download History (CSV)",
            data=csv,
            file_name="usage_history.csv",
            mime="text/csv"
        )

# ============================================================================
# TAB 3: ACCOUNT STATS
# ============================================================================

with tab3:
    st.markdown("### Account Statistics")
    
    # Get stats
    stats = get_user_usage_stats(user_id)
    
    # Display metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Articles Verified",
            stats['total_articles']
        )
    
    with col2:
        st.metric(
            "Total Sources",
            stats['total_sources']
        )
    
    with col3:
        st.metric(
            "Credits Used",
            stats['total_credits_used']
        )
    
    with col4:
        st.metric(
            "Avg Sources/Article",
            stats['avg_sources_per_article']
        )
    
    # Account info
    st.markdown("---")
    st.markdown("### Account Information")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write(f"**Email:** {user_email}")
        st.write(f"**User ID:** `{user_id[:8]}...`")
    
    with col2:
        st.write(f"**Current Balance:** {credits} credits")
        
        lifetime_spent = stats['total_credits_used'] * 0.75  # $0.75 per credit
        st.write(f"**Lifetime Spent:** ${lifetime_spent:.2f}")

# ============================================================================
# FOOTER
# ============================================================================

st.markdown("---")
st.markdown(
    "<p style='text-align: center; color: gray;'>"
    "Need help? Contact support@example.com"
    "</p>",
    unsafe_allow_html=True
)
