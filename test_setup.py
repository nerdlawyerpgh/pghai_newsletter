"""
Testing Script for Authentication Setup
Run this to verify your Supabase and authentication setup is working correctly
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

print("=" * 70)
print("AUTHENTICATION SETUP TEST")
print("=" * 70)
print()

# ============================================================================
# TEST 1: Environment Variables
# ============================================================================

print("TEST 1: Checking environment variables...")

required_vars = [
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_KEY",
    "ANTHROPIC_API_KEY"
]

missing_vars = []
for var in required_vars:
    value = os.getenv(var)
    if value:
        # Show partial value for security
        display_value = value[:20] + "..." if len(value) > 20 else value
        print(f"  ✓ {var}: {display_value}")
    else:
        print(f"  ✗ {var}: MISSING")
        missing_vars.append(var)

if missing_vars:
    print()
    print(f"❌ Missing variables: {', '.join(missing_vars)}")
    print("   Please add them to your .env file")
    sys.exit(1)
else:
    print()
    print("✅ All environment variables found!")

print()

# ============================================================================
# TEST 2: Supabase Connection
# ============================================================================

print("TEST 2: Testing Supabase connection...")

try:
    from supabase import create_client, Client
    
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_ANON_KEY")
    
    supabase: Client = create_client(supabase_url, supabase_key)
    
    # Try to query a table
    result = supabase.table('credits').select("*").limit(1).execute()
    
    print("  ✓ Connected to Supabase")
    print(f"  ✓ Database accessible")
    print()
    print("✅ Supabase connection working!")
    
except Exception as e:
    print(f"  ✗ Connection failed: {e}")
    print()
    print("❌ Supabase connection failed!")
    print("   Possible issues:")
    print("   - Check your SUPABASE_URL is correct")
    print("   - Check your SUPABASE_ANON_KEY is correct")
    print("   - Make sure you've run the database schema SQL")
    print("   - Check if your Supabase project is paused")
    sys.exit(1)

print()

# ============================================================================
# TEST 3: Database Tables
# ============================================================================

print("TEST 3: Checking database tables...")

tables_to_check = [
    'user_profiles',
    'credits',
    'usage',
    'transactions'
]

missing_tables = []

for table in tables_to_check:
    try:
        result = supabase.table(table).select("*").limit(1).execute()
        print(f"  ✓ Table '{table}' exists")
    except Exception as e:
        print(f"  ✗ Table '{table}' missing or inaccessible")
        missing_tables.append(table)

if missing_tables:
    print()
    print(f"❌ Missing tables: {', '.join(missing_tables)}")
    print("   Please run the database schema SQL in Supabase SQL Editor")
    print("   See WEEK_1_CHECKLIST.md Step 4 for the SQL code")
    sys.exit(1)
else:
    print()
    print("✅ All database tables present!")

print()

# ============================================================================
# TEST 4: Authentication Functions
# ============================================================================

print("TEST 4: Testing authentication functions...")

try:
    # Import auth functions
    from auth import (
        initialize_session_state,
        signup_user,
        login_user,
        check_authentication
    )
    
    print("  ✓ Auth module imported successfully")
    print("  ✓ All auth functions available")
    print()
    print("✅ Authentication functions ready!")
    
except Exception as e:
    print(f"  ✗ Import failed: {e}")
    print()
    print("❌ Authentication functions not available!")
    print("   Make sure auth.py is in your project directory")
    sys.exit(1)

print()

# ============================================================================
# TEST 5: Database Functions
# ============================================================================

print("TEST 5: Testing database functions...")

try:
    from database import (
        get_credit_balance,
        add_credits,
        deduct_credits,
        log_usage
    )
    
    print("  ✓ Database module imported successfully")
    print("  ✓ All database functions available")
    print()
    print("✅ Database functions ready!")
    
except Exception as e:
    print(f"  ✗ Import failed: {e}")
    print()
    print("❌ Database functions not available!")
    print("   Make sure database.py is in your project directory")
    sys.exit(1)

print()

# ============================================================================
# TEST 6: UI Components
# ============================================================================

print("TEST 6: Testing UI components...")

try:
    from auth_ui import (
        show_login_page,
        show_user_profile_sidebar,
        show_welcome_message
    )
    
    print("  ✓ UI module imported successfully")
    print("  ✓ All UI components available")
    print()
    print("✅ UI components ready!")
    
except Exception as e:
    print(f"  ✗ Import failed: {e}")
    print()
    print("❌ UI components not available!")
    print("   Make sure auth_ui.py is in your project directory")
    sys.exit(1)

print()

# ============================================================================
# TEST 7: Stripe (Optional for Week 1)
# ============================================================================

print("TEST 7: Checking Stripe setup (optional for Week 1)...")

stripe_key = os.getenv("STRIPE_SECRET_KEY")

if stripe_key:
    try:
        import stripe
        stripe.api_key = stripe_key
        
        # Try a simple API call
        customers = stripe.Customer.list(limit=1)
        
        print("  ✓ Stripe configured")
        print("  ✓ Stripe API accessible")
        print()
        print("✅ Stripe ready!")
        
    except Exception as e:
        print(f"  ⚠ Stripe error: {e}")
        print()
        print("⚠️  Stripe not fully configured (OK for Week 1)")
else:
    print("  ⚠ STRIPE_SECRET_KEY not found")
    print()
    print("⚠️  Stripe not configured (OK for Week 1)")

print()

# ============================================================================
# SUMMARY
# ============================================================================

print("=" * 70)
print("SUMMARY")
print("=" * 70)
print()
print("✅ Environment variables: OK")
print("✅ Supabase connection: OK")
print("✅ Database tables: OK")
print("✅ Authentication functions: OK")
print("✅ Database functions: OK")
print("✅ UI components: OK")
print()
print("🎉 Your authentication setup is ready!")
print()
print("NEXT STEPS:")
print("1. Run your app: streamlit run example_app.py")
print("2. Try creating a test account")
print("3. Test login/logout")
print("4. Check the sidebar shows your email")
print()
print("If you encounter any issues:")
print("- Check INTEGRATION_GUIDE.md for troubleshooting")
print("- Make sure you verified your email (check inbox)")
print("- Try disabling email confirmation in Supabase for testing")
print()
print("=" * 70)
