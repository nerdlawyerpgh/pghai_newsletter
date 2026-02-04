"""
Authentication Module for Newsletter Verifier
Handles user signup, login, logout, and session management using Supabase
"""

import streamlit as st
from supabase import create_client, Client
from typing import Optional, Dict, Any
import os
from datetime import datetime

# Initialize Supabase client
def get_supabase_client() -> Client:
    """Get Supabase client using credentials from secrets or environment"""
    try:
        # Try Streamlit secrets first (for deployment)
        supabase_url = st.secrets.get("SUPABASE_URL")
        supabase_key = st.secrets.get("SUPABASE_ANON_KEY")
    except:
        # Fall back to environment variables (for local development)
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_ANON_KEY")
    
    if not supabase_url or not supabase_key:
        st.error("⚠️ Supabase credentials not found. Please configure SUPABASE_URL and SUPABASE_ANON_KEY")
        st.stop()
    
    return create_client(supabase_url, supabase_key)


def initialize_session_state():
    """Initialize session state variables for authentication"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user' not in st.session_state:
        st.session_state.user = None
    if 'user_id' not in st.session_state:
        st.session_state.user_id = None
    if 'user_email' not in st.session_state:
        st.session_state.user_email = None


def signup_user(email: str, password: str, name: Optional[str] = None) -> Dict[str, Any]:
    """
    Sign up a new user
    
    Args:
        email: User's email address
        password: User's password (min 6 characters)
        name: Optional user's full name
    
    Returns:
        Dict with 'success' (bool) and 'message' (str) or 'user' (dict)
    """
    supabase = get_supabase_client()
    
    try:
        # Sign up user with Supabase Auth
        response = supabase.auth.sign_up({
            "email": email,
            "password": password,
            "options": {
                "data": {
                    "name": name
                }
            }
        })
        
        if response.user:
            return {
                "success": True,
                "user": response.user,
                "message": "Account created! Please check your email to verify your account."
            }
        else:
            return {
                "success": False,
                "message": "Signup failed. Please try again."
            }
            
    except Exception as e:
        error_msg = str(e)
        
        # Handle common errors
        if "already registered" in error_msg.lower():
            return {
                "success": False,
                "message": "This email is already registered. Please log in instead."
            }
        elif "password" in error_msg.lower():
            return {
                "success": False,
                "message": "Password must be at least 6 characters."
            }
        else:
            return {
                "success": False,
                "message": f"Signup error: {error_msg}"
            }


def login_user(email: str, password: str) -> Dict[str, Any]:
    """
    Log in an existing user
    
    Args:
        email: User's email address
        password: User's password
    
    Returns:
        Dict with 'success' (bool) and 'message' (str) or 'user' (dict)
    """
    supabase = get_supabase_client()
    
    try:
        response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        
        if response.user:
            # Update session state
            st.session_state.authenticated = True
            st.session_state.user = response.user
            st.session_state.user_id = response.user.id
            st.session_state.user_email = response.user.email
            
            # Update last login time
            try:
                supabase.table('user_profiles').update({
                    'last_login': datetime.now().isoformat()
                }).eq('user_id', response.user.id).execute()
            except:
                pass  # Don't fail login if last_login update fails
            
            return {
                "success": True,
                "user": response.user,
                "message": "Login successful!"
            }
        else:
            return {
                "success": False,
                "message": "Login failed. Please check your credentials."
            }
            
    except Exception as e:
        error_msg = str(e)
        
        # Handle common errors
        if "invalid" in error_msg.lower() or "credentials" in error_msg.lower():
            return {
                "success": False,
                "message": "Invalid email or password."
            }
        elif "email not confirmed" in error_msg.lower():
            return {
                "success": False,
                "message": "Please verify your email before logging in. Check your inbox for a verification link."
            }
        else:
            return {
                "success": False,
                "message": f"Login error: {error_msg}"
            }


def logout_user():
    """Log out the current user and clear session state"""
    supabase = get_supabase_client()
    
    try:
        supabase.auth.sign_out()
    except:
        pass  # Ignore errors on logout
    
    # Clear session state
    st.session_state.authenticated = False
    st.session_state.user = None
    st.session_state.user_id = None
    st.session_state.user_email = None


def reset_password(email: str) -> Dict[str, Any]:
    """
    Send password reset email
    
    Args:
        email: User's email address
    
    Returns:
        Dict with 'success' (bool) and 'message' (str)
    """
    supabase = get_supabase_client()
    
    try:
        supabase.auth.reset_password_email(email)
        return {
            "success": True,
            "message": "Password reset email sent! Check your inbox."
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error sending reset email: {str(e)}"
        }


def check_authentication() -> bool:
    """
    Check if user is authenticated
    
    Returns:
        bool: True if authenticated, False otherwise
    """
    initialize_session_state()
    
    # Check session state first
    if st.session_state.authenticated and st.session_state.user:
        return True
    
    # Try to get session from Supabase
    supabase = get_supabase_client()
    try:
        session = supabase.auth.get_session()
        if session and session.user:
            # Update session state
            st.session_state.authenticated = True
            st.session_state.user = session.user
            st.session_state.user_id = session.user.id
            st.session_state.user_email = session.user.email
            return True
    except:
        pass
    
    return False


def get_current_user() -> Optional[Dict[str, Any]]:
    """
    Get current authenticated user
    
    Returns:
        User dict or None if not authenticated
    """
    if check_authentication():
        return st.session_state.user
    return None


def get_user_id() -> Optional[str]:
    """
    Get current user's ID
    
    Returns:
        User ID string or None if not authenticated
    """
    if check_authentication():
        return st.session_state.user_id
    return None


def get_user_email() -> Optional[str]:
    """
    Get current user's email
    
    Returns:
        Email string or None if not authenticated
    """
    if check_authentication():
        return st.session_state.user_email
    return None


def require_authentication(redirect: bool = True):
    """
    Decorator/function to require authentication
    If user is not authenticated and redirect=True, show login page and stop execution
    
    Args:
        redirect: If True, show login page. If False, just return False
    
    Returns:
        bool: True if authenticated, False otherwise
    """
    if not check_authentication():
        if redirect:
            show_login_page()
            st.stop()
        return False
    return True
