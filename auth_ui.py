"""
Authentication UI Components for Streamlit
Beautiful, user-friendly login, signup, and password reset interfaces
"""

import streamlit as st
from auth import (
    signup_user, 
    login_user, 
    logout_user, 
    reset_password,
    initialize_session_state
)
import re


def validate_email(email: str) -> bool:
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_password(password: str) -> tuple[bool, str]:
    """
    Validate password strength
    Returns: (is_valid, error_message)
    """
    if len(password) < 6:
        return False, "Password must be at least 6 characters"
    if len(password) > 72:
        return False, "Password must be less than 72 characters"
    return True, ""


def show_login_page():
    """Display the main login page with tabs for login, signup, and password reset"""
    
    initialize_session_state()
    
    # Center the content
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("# 🔐 Newsletter Verifier")
        st.markdown("### AI-Powered Source Verification")
        st.markdown("---")
        
        # Create tabs for different auth actions
        tab1, tab2, tab3 = st.tabs(["Login", "Sign Up", "Reset Password"])
        
        # Login Tab
        with tab1:
            st.markdown("#### Welcome Back!")
            
            with st.form("login_form"):
                email = st.text_input("Email", placeholder="you@example.com")
                password = st.text_input("Password", type="password", placeholder="Enter your password")
                
                submit = st.form_submit_button("Login", use_container_width=True, type="primary")
                
                if submit:
                    # Validation
                    if not email or not password:
                        st.error("Please enter both email and password")
                    elif not validate_email(email):
                        st.error("Please enter a valid email address")
                    else:
                        # Attempt login
                        with st.spinner("Logging in..."):
                            result = login_user(email, password)
                        
                        if result["success"]:
                            st.success(result["message"])
                            st.balloons()
                            st.rerun()  # Reload the app
                        else:
                            st.error(result["message"])
        
        # Signup Tab
        with tab2:
            st.markdown("#### Create Your Account")
            st.markdown("Start verifying sources in seconds!")
            
            with st.form("signup_form"):
                name = st.text_input("Full Name (Optional)", placeholder="John Doe")
                email = st.text_input("Email", placeholder="you@example.com", key="signup_email")
                password = st.text_input(
                    "Password", 
                    type="password", 
                    placeholder="At least 6 characters",
                    key="signup_password",
                    help="Use a strong password with letters, numbers, and symbols"
                )
                password_confirm = st.text_input(
                    "Confirm Password", 
                    type="password", 
                    placeholder="Re-enter your password",
                    key="signup_password_confirm"
                )
                
                terms = st.checkbox("I agree to the Terms of Service and Privacy Policy")
                
                submit = st.form_submit_button("Create Account", use_container_width=True, type="primary")
                
                if submit:
                    # Validation
                    if not email or not password:
                        st.error("Please enter both email and password")
                    elif not validate_email(email):
                        st.error("Please enter a valid email address")
                    elif password != password_confirm:
                        st.error("Passwords do not match")
                    else:
                        is_valid, error_msg = validate_password(password)
                        if not is_valid:
                            st.error(error_msg)
                        elif not terms:
                            st.error("Please accept the Terms of Service")
                        else:
                            # Attempt signup
                            with st.spinner("Creating your account..."):
                                result = signup_user(email, password, name)
                            
                            if result["success"]:
                                st.success(result["message"])
                                st.info("💡 After verifying your email, return to the Login tab.")
                            else:
                                st.error(result["message"])
        
        # Password Reset Tab
        with tab3:
            st.markdown("#### Reset Your Password")
            st.markdown("Enter your email to receive a reset link")
            
            with st.form("reset_form"):
                email = st.text_input("Email", placeholder="you@example.com", key="reset_email")
                
                submit = st.form_submit_button("Send Reset Link", use_container_width=True, type="primary")
                
                if submit:
                    if not email:
                        st.error("Please enter your email address")
                    elif not validate_email(email):
                        st.error("Please enter a valid email address")
                    else:
                        with st.spinner("Sending reset email..."):
                            result = reset_password(email)
                        
                        if result["success"]:
                            st.success(result["message"])
                        else:
                            st.error(result["message"])
        
        # Footer
        st.markdown("---")
        st.markdown(
            "<p style='text-align: center; color: gray; font-size: 0.9em;'>"
            "Secure authentication powered by Supabase"
            "</p>",
            unsafe_allow_html=True
        )


def show_user_profile_sidebar():
    """Display user profile information in sidebar"""
    
    if st.session_state.authenticated and st.session_state.user:
        with st.sidebar:
            st.markdown("---")
            st.markdown("### 👤 Account")
            
            # Get user info
            user = st.session_state.user
            email = user.email
            
            # Display user info
            st.markdown(f"**Email:** {email}")
            
            # User name if available
            if hasattr(user, 'user_metadata') and user.user_metadata.get('name'):
                st.markdown(f"**Name:** {user.user_metadata['name']}")
            
            # Logout button
            if st.button("🚪 Logout", use_container_width=True):
                logout_user()
                st.success("Logged out successfully!")
                st.rerun()


def show_mini_login_prompt():
    """Show a minimal login prompt for embedded use"""
    
    st.warning("🔒 Please log in to access this feature")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Login", use_container_width=True, type="primary"):
            st.session_state.show_login = True
            st.rerun()
    
    with col2:
        if st.button("Sign Up", use_container_width=True):
            st.session_state.show_login = True
            st.rerun()


def show_welcome_message():
    """Show welcome message after successful login"""
    
    if st.session_state.authenticated and st.session_state.user:
        user = st.session_state.user
        name = "there"
        
        # Try to get name from user metadata
        if hasattr(user, 'user_metadata') and user.user_metadata.get('name'):
            name = user.user_metadata['name'].split()[0]  # First name only
        
        st.success(f"👋 Welcome back, {name}!")


def protected_page(page_function):
    """
    Decorator to protect a page/function with authentication
    
    Usage:
        @protected_page
        def my_app():
            st.write("This is protected content")
    """
    def wrapper(*args, **kwargs):
        initialize_session_state()
        
        if not st.session_state.authenticated:
            show_login_page()
            st.stop()
        else:
            return page_function(*args, **kwargs)
    
    return wrapper


# Example usage in main app
if __name__ == "__main__":
    st.set_page_config(
        page_title="Newsletter Verifier",
        page_icon="🔐",
        layout="wide"
    )
    
    initialize_session_state()
    
    if not st.session_state.authenticated:
        show_login_page()
    else:
        show_user_profile_sidebar()
        show_welcome_message()
        
        st.title("🎉 You're Logged In!")
        st.write("This is where your app content goes.")
        st.write(f"User ID: {st.session_state.user_id}")
        st.write(f"Email: {st.session_state.user_email}")
