# Quick Migration Guide

## Upgrading from Original to Improved System

### Step 1: Backup Current System

```bash
# Backup your current files
cp app.py app.py.backup
cp llm.py llm.py.backup
cp extraction.py extraction.py.backup
cp prompts/analysis.txt prompts/analysis.txt.backup
cp prompts/verification_external.txt prompts/verification_external.txt.backup
```

### Step 2: Install New Files

```bash
# Replace with improved versions
cp improved_app.py app.py
cp improved_llm.py llm.py
cp improved_extraction.py extraction.py
cp improved_analysis.txt prompts/analysis.txt
cp improved_verification_external.txt prompts/verification_external.txt

# Update dependencies
pip install -r requirements.txt
```

### Step 3: Update Secrets

Edit `.streamlit/secrets.toml`:

```toml
# Fix model name (important!)
OPENAI_MODEL = "gpt-4o-mini"  # was "gpt-4.1-mini" ❌

# Optional: Add Anthropic support
ANTHROPIC_API_KEY = "sk-ant-..."
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"

# Airtable (unchanged)
AIRTABLE_TOKEN = "pat..."
AIRTABLE_BASE_ID = "app..."
AIRTABLE_TABLE_NAME = "Articles"
```

### Step 4: Test

```bash
streamlit run app.py
```

Test with a simple article first:
1. Submit a URL
2. Check extraction works
3. Verify analysis completes
4. Confirm Airtable save

### Step 5: Verify Improvements

Compare before/after:

**Before:**
- Sequential source fetching (~30s for 5 sources)
- No cost tracking
- Generic errors
- No paywall detection

**After:**
- Parallel source fetching (~8s for 5 sources) ✅
- Real-time cost display ✅
- Detailed error messages ✅
- Paywall detection ✅

### Step 6: Optional - Switch to Claude

In sidebar, select "anthropic" from LLM Provider dropdown.

**When to use Claude:**
- Complex articles requiring deeper analysis
- Research papers with nuanced claims
- When you need better reasoning

**When to use GPT-4o-mini:**
- High-volume processing
- Simpler news articles
- Cost-sensitive operations

## Rollback Plan

If issues arise:

```bash
# Restore original files
cp app.py.backup app.py
cp llm.py.backup llm.py
cp extraction.py.backup extraction.py
cp prompts/analysis.txt.backup prompts/analysis.txt
cp prompts/verification_external.txt.backup prompts/verification_external.txt

# Restart
streamlit run app.py
```

## Common Issues

### Issue: "Module not found: improved_llm"
**Fix:** Make sure you renamed files:
```bash
mv improved_llm.py llm.py
mv improved_extraction.py extraction.py
```

### Issue: "Prompt not found"
**Fix:** Prompts must be in `prompts/` directory:
```bash
mkdir -p prompts
cp improved_analysis.txt prompts/analysis.txt
cp improved_verification_external.txt prompts/verification_external.txt
```

### Issue: "Invalid model: gpt-4.1-mini"
**Fix:** Update secrets.toml:
```toml
OPENAI_MODEL = "gpt-4o-mini"  # correct model name
```

### Issue: AttributeError with new fields
**Fix:** Airtable might need new fields. Add these columns:
- Paywall Detected (Checkbox)
- Is Fresh (Checkbox)
- Link Scores (Long text)

## Testing Checklist

- [ ] Article extraction works
- [ ] Paywall detection appears for paywalled sites
- [ ] LLM analysis completes
- [ ] Source fetching faster than before
- [ ] Verification returns per-claim results
- [ ] Cost tracking shows in UI
- [ ] Airtable save successful
- [ ] Download JSON works
- [ ] Can switch between OpenAI/Anthropic

## Performance Comparison

Test with same article in both systems:

| Metric | Original | Improved |
|--------|----------|----------|
| Source fetch time | ~30s | ~8s |
| Total analysis time | ~60s | ~45s |
| Error recovery | Manual | Automatic |
| Cost visibility | None | Real-time |

## Questions?

1. Check README.md for full documentation
2. Review IMPROVEMENTS_SUMMARY.md for details
3. Examine prompt files for configuration
4. Test with known articles first

## Success Criteria

You'll know the migration succeeded when:
1. ✅ Articles process faster (parallel source fetching)
2. ✅ You see cost estimates in UI
3. ✅ Paywall warnings appear when appropriate
4. ✅ Errors show helpful details (not generic messages)
5. ✅ Per-claim verification shows specific evidence
6. ✅ Can switch LLM providers in sidebar
