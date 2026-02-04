"""
Database Helper Functions
Utilities for managing credits, usage tracking, and transactions
"""

import streamlit as st
from supabase import create_client, Client
from typing import Optional, Dict, List, Any
from datetime import datetime
import os


def get_supabase_client() -> Client:
    """Get Supabase client using credentials from secrets or environment"""
    try:
        supabase_url = st.secrets.get("SUPABASE_URL")
        supabase_key = st.secrets.get("SUPABASE_SERVICE_KEY")  # Use service key for admin operations
    except:
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
    
    if not supabase_url or not supabase_key:
        st.error("⚠️ Supabase credentials not found")
        st.stop()
    
    return create_client(supabase_url, supabase_key)


# ============================================================================
# CREDIT MANAGEMENT
# ============================================================================

def get_credit_balance(user_id: str) -> int:
    """
    Get user's current credit balance
    
    Args:
        user_id: User's UUID
    
    Returns:
        int: Current credit balance (0 if user not found)
    """
    supabase = get_supabase_client()
    
    try:
        result = supabase.table('credits').select('balance').eq('user_id', user_id).single().execute()
        return result.data['balance'] if result.data else 0
    except:
        return 0


def add_credits(user_id: str, amount: int, transaction_type: str = 'purchase') -> bool:
    """
    Add credits to user's account
    
    Args:
        user_id: User's UUID
        amount: Number of credits to add
        transaction_type: Type of transaction ('purchase', 'bonus', 'refund')
    
    Returns:
        bool: True if successful, False otherwise
    """
    supabase = get_supabase_client()
    
    try:
        # Get current balance
        current = supabase.table('credits').select('balance').eq('user_id', user_id).single().execute()
        
        if current.data:
            # Update existing balance
            new_balance = current.data['balance'] + amount
            supabase.table('credits').update({
                'balance': new_balance,
                'last_updated': datetime.now().isoformat()
            }).eq('user_id', user_id).execute()
        else:
            # Create new credits record
            supabase.table('credits').insert({
                'user_id': user_id,
                'balance': amount,
                'lifetime_used': 0
            }).execute()
        
        return True
    except Exception as e:
        st.error(f"Error adding credits: {e}")
        return False


def deduct_credits(user_id: str, amount: int) -> Dict[str, Any]:
    """
    Deduct credits from user's account
    
    Args:
        user_id: User's UUID
        amount: Number of credits to deduct
    
    Returns:
        Dict with 'success' (bool), 'message' (str), and 'new_balance' (int)
    """
    supabase = get_supabase_client()
    
    try:
        # Get current balance
        current = supabase.table('credits').select('balance, lifetime_used').eq('user_id', user_id).single().execute()
        
        if not current.data:
            return {
                'success': False,
                'message': 'Credit account not found',
                'new_balance': 0
            }
        
        current_balance = current.data['balance']
        lifetime_used = current.data['lifetime_used'] or 0
        
        # Check if sufficient balance
        if current_balance < amount:
            return {
                'success': False,
                'message': f'Insufficient credits. Need {amount}, have {current_balance}',
                'new_balance': current_balance
            }
        
        # Deduct credits
        new_balance = current_balance - amount
        new_lifetime = lifetime_used + amount
        
        supabase.table('credits').update({
            'balance': new_balance,
            'lifetime_used': new_lifetime,
            'last_updated': datetime.now().isoformat()
        }).eq('user_id', user_id).execute()
        
        return {
            'success': True,
            'message': f'Deducted {amount} credits',
            'new_balance': new_balance
        }
        
    except Exception as e:
        return {
            'success': False,
            'message': f'Error deducting credits: {str(e)}',
            'new_balance': 0
        }


def check_sufficient_credits(user_id: str, required: int) -> Dict[str, Any]:
    """
    Check if user has sufficient credits for an operation
    
    Args:
        user_id: User's UUID
        required: Number of credits required
    
    Returns:
        Dict with 'sufficient' (bool), 'balance' (int), 'needed' (int)
    """
    balance = get_credit_balance(user_id)
    
    return {
        'sufficient': balance >= required,
        'balance': balance,
        'needed': max(0, required - balance)
    }


# ============================================================================
# USAGE TRACKING
# ============================================================================

def log_usage(
    user_id: str,
    article_url: str,
    sources_verified: int,
    cost_credits: int,
    article_title: Optional[str] = None,
    metadata: Optional[Dict] = None
) -> bool:
    """
    Log usage of the service
    
    Args:
        user_id: User's UUID
        article_url: URL of the analyzed article
        sources_verified: Number of sources verified
        cost_credits: Number of credits charged
        article_title: Optional article title
        metadata: Optional additional metadata (as dict)
    
    Returns:
        bool: True if successful, False otherwise
    """
    supabase = get_supabase_client()
    
    try:
        supabase.table('usage').insert({
            'user_id': user_id,
            'article_url': article_url,
            'sources_verified': sources_verified,
            'cost_credits': cost_credits,
            'article_title': article_title,
            'metadata': metadata,
            'created_at': datetime.now().isoformat()
        }).execute()
        
        return True
    except Exception as e:
        st.error(f"Error logging usage: {e}")
        return False


def get_user_usage_history(user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get user's usage history
    
    Args:
        user_id: User's UUID
        limit: Maximum number of records to return
    
    Returns:
        List of usage records
    """
    supabase = get_supabase_client()
    
    try:
        result = supabase.table('usage').select('*').eq('user_id', user_id).order('created_at', desc=True).limit(limit).execute()
        return result.data if result.data else []
    except:
        return []


def get_user_usage_stats(user_id: str) -> Dict[str, Any]:
    """
    Get aggregate usage statistics for a user
    
    Args:
        user_id: User's UUID
    
    Returns:
        Dict with usage statistics
    """
    supabase = get_supabase_client()
    
    try:
        # Get all usage records
        result = supabase.table('usage').select('sources_verified, cost_credits').eq('user_id', user_id).execute()
        
        if not result.data:
            return {
                'total_articles': 0,
                'total_sources': 0,
                'total_credits_used': 0,
                'avg_sources_per_article': 0
            }
        
        records = result.data
        total_articles = len(records)
        total_sources = sum(r['sources_verified'] for r in records)
        total_credits = sum(r['cost_credits'] for r in records)
        
        return {
            'total_articles': total_articles,
            'total_sources': total_sources,
            'total_credits_used': total_credits,
            'avg_sources_per_article': round(total_sources / total_articles, 1) if total_articles > 0 else 0
        }
    except:
        return {
            'total_articles': 0,
            'total_sources': 0,
            'total_credits_used': 0,
            'avg_sources_per_article': 0
        }


# ============================================================================
# TRANSACTION MANAGEMENT
# ============================================================================

def record_transaction(
    user_id: str,
    transaction_type: str,
    credits_added: int = 0,
    credits_removed: int = 0,
    amount_usd: Optional[float] = None,
    stripe_payment_id: Optional[str] = None,
    status: str = 'completed'
) -> bool:
    """
    Record a transaction (purchase, refund, bonus, etc.)
    
    Args:
        user_id: User's UUID
        transaction_type: Type of transaction ('purchase', 'refund', 'bonus', 'deduction')
        credits_added: Credits added to account
        credits_removed: Credits removed from account
        amount_usd: USD amount (for purchases/refunds)
        stripe_payment_id: Stripe payment ID
        status: Transaction status ('completed', 'pending', 'failed')
    
    Returns:
        bool: True if successful, False otherwise
    """
    supabase = get_supabase_client()
    
    try:
        supabase.table('transactions').insert({
            'user_id': user_id,
            'type': transaction_type,
            'credits_added': credits_added,
            'credits_removed': credits_removed,
            'amount_usd': amount_usd,
            'stripe_payment_id': stripe_payment_id,
            'status': status,
            'created_at': datetime.now().isoformat()
        }).execute()
        
        return True
    except Exception as e:
        st.error(f"Error recording transaction: {e}")
        return False


def get_user_transactions(user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get user's transaction history
    
    Args:
        user_id: User's UUID
        limit: Maximum number of records to return
    
    Returns:
        List of transaction records
    """
    supabase = get_supabase_client()
    
    try:
        result = supabase.table('transactions').select('*').eq('user_id', user_id).order('created_at', desc=True).limit(limit).execute()
        return result.data if result.data else []
    except:
        return []


# ============================================================================
# STRIPE INTEGRATION HELPERS
# ============================================================================

def get_stripe_customer_id(user_id: str) -> Optional[str]:
    """
    Get Stripe customer ID for a user
    
    Args:
        user_id: User's UUID
    
    Returns:
        Stripe customer ID or None
    """
    supabase = get_supabase_client()
    
    try:
        result = supabase.table('user_profiles').select('stripe_customer_id').eq('user_id', user_id).single().execute()
        return result.data['stripe_customer_id'] if result.data else None
    except:
        return None


def set_stripe_customer_id(user_id: str, stripe_customer_id: str) -> bool:
    """
    Store Stripe customer ID for a user
    
    Args:
        user_id: User's UUID
        stripe_customer_id: Stripe customer ID
    
    Returns:
        bool: True if successful, False otherwise
    """
    supabase = get_supabase_client()
    
    try:
        # Try to update existing profile
        result = supabase.table('user_profiles').update({
            'stripe_customer_id': stripe_customer_id
        }).eq('user_id', user_id).execute()
        
        # If no rows affected, insert new profile
        if not result.data:
            supabase.table('user_profiles').insert({
                'user_id': user_id,
                'stripe_customer_id': stripe_customer_id
            }).execute()
        
        return True
    except Exception as e:
        st.error(f"Error setting Stripe customer ID: {e}")
        return False


# ============================================================================
# ADMIN / ANALYTICS FUNCTIONS
# ============================================================================

def get_total_revenue() -> float:
    """Get total revenue from all completed purchases"""
    supabase = get_supabase_client()
    
    try:
        result = supabase.table('transactions').select('amount_usd').eq('type', 'purchase').eq('status', 'completed').execute()
        
        if result.data:
            return sum(float(r['amount_usd']) for r in result.data if r['amount_usd'])
        return 0.0
    except:
        return 0.0


def get_active_users_count() -> int:
    """Get count of users who have used the service in the last 30 days"""
    supabase = get_supabase_client()
    
    try:
        # Get users with usage in last 30 days
        from datetime import timedelta
        thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()
        
        result = supabase.table('usage').select('user_id').gte('created_at', thirty_days_ago).execute()
        
        if result.data:
            # Count unique user IDs
            unique_users = set(r['user_id'] for r in result.data)
            return len(unique_users)
        return 0
    except:
        return 0


def get_total_credits_sold() -> int:
    """Get total credits sold across all purchases"""
    supabase = get_supabase_client()
    
    try:
        result = supabase.table('transactions').select('credits_added').eq('type', 'purchase').eq('status', 'completed').execute()
        
        if result.data:
            return sum(r['credits_added'] for r in result.data if r['credits_added'])
        return 0
    except:
        return 0
