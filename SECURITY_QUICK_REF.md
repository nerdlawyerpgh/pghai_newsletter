# Security Quick Reference

## Rate Limits

```
5 submissions per hour
20 submissions per day
```

**To change:** Edit constants in `improved_app.py`:
```python
MAX_SUBMISSIONS_PER_HOUR = 5
MAX_SUBMISSIONS_PER_DAY = 20
```

---

## URL Validation

### ✅ Allowed:
- `https://example.com/article`
- `http://news.site.com/story`
- Any HTTP/HTTPS URL to public domain

### 🚫 Blocked:
- `localhost` or `127.0.0.1`
- Private IPs (`192.168.x.x`, `10.x.x.x`)
- `file://` protocol
- URLs without protocol
- URLs longer than 2000 chars

---

## Input Limits

| Field | Max Length | Validation |
|-------|------------|------------|
| **URL** | 2000 chars | Protocol, hostname, IP check |
| **Name** | 100 chars | HTML removed, special chars sanitized |
| **Email** | 100 chars | Regex format validation |
| **Notes** | 500 chars | HTML removed, special chars sanitized |

---

## Validation Rules

### Text Sanitization
- Removes: `< > " '` and HTML tags
- Keeps: Letters, numbers, basic punctuation
- Trims: Leading/trailing whitespace

### Email Pattern
```regex
^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$
```

---

## User Experience

### Normal Usage
```
📊 Usage: 2/5 this hour • 8/20 today
[URL input field]
[🚀 Run Analysis] (enabled)
```

### Invalid URL
```
Article URL: http://localhost/test
⚠️ Cannot analyze localhost URLs
[🚀 Run Analysis] (disabled)
```

### Invalid Email
```
Your Email: invalid@
⚠️ Invalid email format
[🚀 Run Analysis] (disabled)
```

### Rate Limit Hit
```
📊 Usage: 5/5 this hour • 15/20 today
[URL input field]
[🚀 Run Analysis] (disabled)
🚫 Rate limit exceeded. You can submit 5 articles per hour. 
Please wait 23 minutes.
```

### Close to Limit
```
⚠️ You have 2 submissions remaining in this period
[🚀 Run Analysis] (enabled)
```

---

## Testing Commands

### Test Rate Limiting
```python
# In Python console or test file
from improved_app import check_rate_limit, record_submission

# Check current status
is_ok, msg, remaining = check_rate_limit()
print(f"Can submit: {is_ok}, Remaining: {remaining}")

# Record 5 submissions
for i in range(5):
    record_submission()

# Check again - should be blocked
is_ok, msg, remaining = check_rate_limit()
print(f"After 5: {is_ok}, Message: {msg}")
```

### Test URL Validation
```python
from improved_app import validate_url

# Should pass
print(validate_url("https://example.com"))  # (True, "")

# Should fail
print(validate_url("localhost"))  # (False, "URL must start with http:// or https://")
print(validate_url("http://127.0.0.1"))  # (False, "Cannot analyze localhost URLs")
```

### Test Sanitization
```python
from improved_app import sanitize_text

# XSS attempt
result = sanitize_text("<script>alert('xss')</script>")
print(result)  # "scriptalert('xss')/script" (tags removed)

# Length limit
result = sanitize_text("a" * 1000, max_length=100)
print(len(result))  # 100
```

---

## Configuration for Different Environments

### Development (Lenient)
```python
MAX_SUBMISSIONS_PER_HOUR = 20
MAX_SUBMISSIONS_PER_DAY = 100
```

### Beta Testing (Moderate)
```python
MAX_SUBMISSIONS_PER_HOUR = 10
MAX_SUBMISSIONS_PER_DAY = 50
```

### Production (Standard)
```python
MAX_SUBMISSIONS_PER_HOUR = 5
MAX_SUBMISSIONS_PER_DAY = 20
```

### Free Tier (Strict)
```python
MAX_SUBMISSIONS_PER_HOUR = 2
MAX_SUBMISSIONS_PER_DAY = 10
```

---

## Security Checklist

Before launching:

- [ ] Rate limits configured appropriately
- [ ] Tested URL validation with malicious inputs
- [ ] Tested XSS attempts in text fields
- [ ] Verified email validation works
- [ ] Tested rate limit exceeded flow
- [ ] HTTPS enabled (production)
- [ ] Secrets properly configured
- [ ] No sensitive data in logs

---

## Common Issues

### "Rate limit not working after browser refresh"

**Cause:** Session-based tracking resets on refresh

**Solution:** For production, implement IP-based or database-backed rate limiting

### "Can't submit from work VPN"

**Cause:** VPN uses private IP ranges which are blocked

**Solution:** Temporarily allow VPN IP ranges or whitelist specific IPs

### "Users bypassing rate limit"

**Cause:** Session-based tracking can be cleared

**Solution:** Implement IP-based rate limiting with database/Redis

---

## Upgrade Path

### Current (Session-Based)
✅ Good for: MVP, beta testing, low traffic
❌ Limitations: Can be bypassed, doesn't persist

### Next (IP-Based)
✅ Good for: Production, medium traffic
✅ Adds: Persistent tracking, harder to bypass
🔧 Requires: Database or Redis

### Advanced (User-Based)
✅ Good for: Paid service, high traffic
✅ Adds: Per-user quotas, tier-based limits
🔧 Requires: Authentication system, user database

---

## Support

For questions or issues:
1. Check [SECURITY_FEATURES.md](SECURITY_FEATURES.md) for detailed docs
2. Review error messages in UI
3. Check Streamlit logs for debugging
4. Test with examples above

**Emergency:** If under attack, temporarily set:
```python
MAX_SUBMISSIONS_PER_HOUR = 1
MAX_SUBMISSIONS_PER_DAY = 3
```
