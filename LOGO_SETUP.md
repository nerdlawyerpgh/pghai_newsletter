# Logo Setup Instructions

## Overview
The app displays two logos in the header:
- **pgh.ai** logo (left side)
- **Nerd Lawyer** logo (right side)

With attribution text: "Created by Nerd Lawyer for pgh.ai"

## File Placement

Place the logo files in the same directory as your `improved_app.py`:

```
your_project/
├── improved_app.py
├── pgh_ai_logo.png          # pgh.ai logo
├── nerd_lawyer_logo.jpg     # Nerd Lawyer logo
├── improved_llm.py
├── improved_extraction.py
└── ...
```

## Logo Files

**pgh.ai Logo:**
- Filename: `pgh_ai_logo.png`
- Format: PNG with transparent background
- Dimensions: Displays at 180px width (scales proportionally)
- Colors: Teal text on black background with gold geometric shapes

**Nerd Lawyer Logo:**
- Filename: `nerd_lawyer_logo.jpg`
- Format: JPG
- Dimensions: Displays at 180px width (scales proportionally)
- Colors: Red text in oval with white background

## Header Layout

```
┌─────────────────────────────────────────────────────────┐
│  [pgh.ai logo]   AI Newsletter Analysis   [NL logo]    │
│           Intelligent claim extraction                  │
│        Created by Nerd Lawyer for pgh.ai               │
├─────────────────────────────────────────────────────────┤
```

## Fallback Behavior

If logo files are not found, the app will display text instead:
- Left: "**pgh.ai**"
- Right: "**Nerd Lawyer**"

This ensures the app runs even without logo files present.

## Customization

To adjust logo sizes, edit the `width` parameter in `improved_app.py`:

```python
# Current setting: 180px
st.image("pgh_ai_logo.png", width=180)
st.image("nerd_lawyer_logo.jpg", width=180)

# For larger logos:
st.image("pgh_ai_logo.png", width=250)
st.image("nerd_lawyer_logo.jpg", width=250)
```

## Troubleshooting

### Logo not displaying
**Problem:** Logo appears as text instead of image

**Solution:**
1. Verify file is in the correct directory (same as `improved_app.py`)
2. Check filename matches exactly (case-sensitive):
   - `pgh_ai_logo.png` (not `PGH_AI_LOGO.png`)
   - `nerd_lawyer_logo.jpg` (not `nerd_lawyer_logo.JPG`)
3. Restart Streamlit app

### Logo appears distorted
**Problem:** Logo looks stretched or squished

**Solution:** Adjust the `width` parameter to maintain aspect ratio. Streamlit automatically scales height proportionally.

### Logo too large/small
**Problem:** Logo doesn't fit well in header

**Solution:** 
- Reduce width: `width=120`
- Increase width: `width=220`
- Recommended range: 150-200px

## Testing

To test logo display:

```bash
# 1. Ensure logos are in place
ls -lh pgh_ai_logo.png nerd_lawyer_logo.jpg

# 2. Run app
streamlit run improved_app.py

# 3. Check browser - logos should appear in header
```

## Alternative: Using Base64 Embedded Logos

If you prefer to embed logos directly in the code (no separate files needed), you can convert them to base64:

```python
import base64

# Read and encode logo
with open("pgh_ai_logo.png", "rb") as f:
    logo_base64 = base64.b64encode(f.read()).decode()

# Display
st.markdown(
    f'<img src="data:image/png;base64,{logo_base64}" width="180">',
    unsafe_allow_html=True
)
```

This approach bundles logos in the code but increases file size.

## Production Deployment

For production (e.g., Streamlit Cloud, Heroku):

**Option 1: Include in repository**
```bash
git add pgh_ai_logo.png nerd_lawyer_logo.jpg
git commit -m "Add logos"
git push
```

**Option 2: Use hosted URLs**
```python
# Replace file paths with URLs
st.image("https://yourdomain.com/logos/pgh_ai_logo.png", width=180)
st.image("https://yourdomain.com/logos/nerd_lawyer_logo.jpg", width=180)
```

**Option 3: Streamlit Cloud Assets**
Place in `.streamlit/static/` directory if using Streamlit Cloud.

## Branding Consistency

The logos maintain consistent branding:
- **pgh.ai**: Modern, tech-focused aesthetic
- **Nerd Lawyer**: Professional legal tech branding
- **Attribution**: Clear credit to both organizations

The layout ensures both logos are equally prominent while maintaining a clean, professional appearance.
