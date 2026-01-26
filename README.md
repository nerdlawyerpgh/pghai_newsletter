# AI Newsletter Article Verification System (Improved)

A sophisticated AI-powered system for analyzing, verifying, and curating articles for an AI-focused newsletter. This system uses LLMs to extract claims, verify them against cited sources, and provide confidence scores with detailed rationale.

## 🎯 What This System Does

1. **Extracts** article content with metadata and paywall detection
2. **Analyzes** claims and assesses evidence quality
3. **Verifies** claims against external cited sources
4. **Scores** confidence based on verification results
5. **Stores** results in Airtable for editorial review

## ✨ Key Features

### Intelligent Analysis
- **Claim Extraction**: Identifies specific, verifiable assertions
- **Evidence Assessment**: Evaluates how well the article supports its claims
- **Uncertainty Flagging**: Highlights missing data, unclear methodology, conflicts of interest

### External Verification
- **Source Discovery**: Extracts and ranks cited sources from article
- **Intelligent Fetching**: Keeps fetching until 5 usable sources found (adaptive strategy)
- **Parallel Fetching**: Retrieves multiple sources simultaneously (4x faster)
- **PDF Support**: Automatically extracts text from PDF research papers and reports
- **Cross-Referencing**: Verifies claims against retrieved sources
- **Paywall Detection**: Flags when sources are inaccessible
- **Paywall Statistics**: Reports percentage of sources blocked by paywalls

### Smart Confidence Scoring
- **Multi-Level**: High/Medium/Low with detailed rationale
- **Evidence-Based**: Adjusts based on verification results
- **Transparent**: Shows what supports and what weakens confidence

### Production-Ready
- **Multi-Provider LLM**: OpenAI (GPT-4o-mini) or Anthropic (Claude Sonnet 4)
- **Error Handling**: Automatic retries, graceful failures
- **Cost Tracking**: Real-time token usage and cost estimation
- **Caching**: 24-hour cache for expensive operations

## 📋 Requirements

```bash
pip install -r requirements.txt
```

**Dependencies:**
- streamlit>=1.28.0
- requests>=2.31.0
- trafilatura>=1.6.0
- beautifulsoup4>=4.12.0
- pypdf>=3.17.0
- anthropic>=0.34.0
- openai>=1.0.0
- readability-lxml>=0.8.1
- python-dateutil>=2.8.2

## 🚀 Quick Start

### 1. Setup Header

Place the SVG header file in your project directory:
```bash
# Copy header SVG to project directory
cp newsletter_header.svg your_project/
```

The SVG header includes both pgh.ai and Nerd Lawyer branding.

### 2. Setup Secrets

Create `.streamlit/secrets.toml`:

```toml
# LLM API Keys (choose one or both)
OPENAI_API_KEY = "sk-..."
OPENAI_MODEL = "gpt-4o-mini"

ANTHROPIC_API_KEY = "sk-ant-..."
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"

# Airtable Configuration
AIRTABLE_TOKEN = "pat..."
AIRTABLE_BASE_ID = "app..."
AIRTABLE_TABLE_NAME = "Articles"  # or tbl...
```

### 3. Setup Prompts Directory

```
your_project/
├── prompts/
│   ├── improved_analysis.txt
│   ├── improved_verification_external.txt
│   └── __init__.py
```

The `__init__.py` should contain:
```python
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent

def load_prompt(name: str) -> str:
    path = PROMPTS_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Prompt not found: {path}")
    return path.read_text(encoding="utf-8")
```

### 4. Run the App

```bash
streamlit run improved_app.py
```

## 📊 Airtable Schema

The system expects these fields in your Airtable table:

### Required Fields:
- **Article ID** (Single line text) - Unique identifier
- **Title** (Single line text)
- **URL** (URL)
- **Status** (Single select: New, Reviewing, Approved, Rejected, Published)

### Recommended Fields:
- **Publisher** (Single line text)
- **Author** (Single line text)
- **Publish Date** (Date)
- **Submitter** (Single line text)
- **Submitter Notes** (Long text)
- **Section** (Single select: Top Stories, Research, Policy, Tools, etc.)
- **Confidence** (Single select: High, Medium, Low)
- **Why Now** (Long text)
- **Top Bullets** (Long text)
- **Cautions** (Long text)
- **Full Card JSON** (Long text)

## 🎨 UI Overview

### Streamlined Interface (No Sidebar)
- **Submit Article**: URL input, submitter info, LLM provider selection
- **About This Tool**: Configuration display (5 sources, 18k chars per source)
- **Progressive Results**: Each step highlights and shows results inline as processing occurs

### Step-by-Step Display
As analysis runs, each step shows:
1. **Extract Article**: Characters, publisher, paywall status
2. **Analyze Claims**: Numbered claims with importance indicators
3. **Gather Sources**: Links found, sources verified with rankings
4. **Verify Claims**: Corroboration status (corroborated/partial/contradicted/unclear)
5. **Save Results**: Airtable confirmation

### Final Results
- **Confidence Rationale**: Side-by-side view of supporting factors vs. cautions
- **Download**: Full analysis as JSON

## 🔧 Configuration

### Fixed Settings
The following are hardcoded for consistency:
- **Max sources**: 5 cited sources to fetch and verify
- **Max chars per source**: 18,000 characters to extract
- **Audience**: "Nonprofit AI community: engineers, founders, policy experts, and researchers"
- **Mission**: "Accuracy-first AI literacy. Avoid hype. Prioritize evidence and transparency."

### LLM Provider Selection

Choose between OpenAI or Anthropic in the main interface:

**OpenAI (GPT-4o-mini):**
- Faster responses
- Lower cost (~$0.10 per article)
- Good for high-volume processing

**Anthropic (Claude Sonnet 4):**
- Better reasoning
- More thorough verification
- Higher cost (~$0.20 per article)

## 📈 Cost Estimates

Based on typical usage:

| LLM Provider | Per Article | 20 Articles/Week | Annual |
|--------------|-------------|------------------|--------|
| GPT-4o-mini  | $0.08-0.12  | $1.60-2.40      | $83-125 |
| Claude Sonnet 4 | $0.15-0.25 | $3.00-5.00    | $156-260 |

Costs include:
- Article analysis (~8k tokens input, 2k output)
- Source verification (~10k tokens input, 2k output)

## 🏗️ Architecture

### Pipeline Flow

```
User submits URL
    ↓
Extract article (trafilatura + readability)
    ↓
LLM Analysis (extract claims + assess evidence)
    ↓
Gather cited sources (extract links, rank by quality, fetch content)
    ↓
LLM Verification (verify claims against sources)
    ↓
Build editor packet (summary + confidence rationale)
    ↓
Save to Airtable
```

### Key Components

1. **improved_llm.py**: Multi-provider LLM client with retries and cost tracking
2. **improved_extraction.py**: Web scraping, link ranking, parallel fetching
3. **improved_app.py**: Streamlit UI and orchestration
4. **improved_analysis.txt**: Prompt for claim extraction
5. **improved_verification_external.txt**: Prompt for source verification
6. **airtable_storage.py**: Airtable integration (from original)

## 🎯 Use Cases

### Newsletter Curation
- Submit candidate articles
- Get AI-powered analysis with confidence scores
- Review verification results
- Approve for publication

### Fact-Checking
- Verify claims in AI news articles
- Cross-reference with cited sources
- Identify speculative vs. supported claims

### Research Assistance
- Extract key findings from papers
- Verify against primary sources
- Track evidence quality

## 🔍 How Verification Works

### Link Ranking
The system ranks cited sources using heuristics:

**High Value (+50-80 points):**
- Academic publishers (Nature, Science, ACM, IEEE)
- Government sources (.gov, .edu)
- Official AI lab sites (OpenAI, Anthropic, DeepMind)
- DOI/arXiv links

**Medium Value (+30-40 points):**
- Reputable news (NYT, WSJ, Reuters, Bloomberg)
- Research institutions

**Low Value (-50+ points):**
- Social media
- Personal blogs
- Tracking links

### Verification Process

For each claim:
1. **Extract** from article analysis
2. **Search** in retrieved source content
3. **Match** claim against source evidence
4. **Classify** as corroborated/contradicted/partial/unclear
5. **Document** with snippets and limitations

### Confidence Scoring

**High Confidence:**
- Multiple independent sources corroborate
- Primary sources confirm methodology
- Transparent data and methods
- Few limitations

**Medium Confidence:**
- Single credible source OR
- Good evidence with some gaps OR
- Mixed verification results

**Low Confidence:**
- Key claims contradicted OR
- Mostly unverified OR
- Serious methodological concerns OR
- Significant conflicts of interest

## 🚨 Known Limitations

### Paywalls
- Many academic sources are paywalled
- Extraction may be incomplete
- System flags paywall detection

### Source Quality
- Heuristic ranking may miss niche sources
- Some reputable sources not in high-value list
- Self-published work harder to verify

### LLM Limitations
- May miss subtle contradictions
- Confidence calibration imperfect
- JSON parsing occasionally fails (retries help)

## 🔐 Security & Privacy

### Data Handling
- Article content sent to LLM providers (OpenAI/Anthropic)
- No storage beyond Airtable and caching
- Submitter info stored in Airtable

### API Keys
- Stored in Streamlit secrets (not in code)
- Never logged or exposed in UI
- Use environment-specific secrets

## 📚 Additional Documentation

- **IMPROVEMENTS_SUMMARY.md**: Detailed comparison with original system
- **Prompt Engineering Guide**: See prompt files for best practices
- **Airtable Setup Guide**: Field configuration and views

## 🤝 Contributing

### Areas for Enhancement

**High Priority:**
1. PostgreSQL integration for better querying
2. Batch processing for multiple articles
3. Webhook integration for automated analysis

**Medium Priority:**
4. Author credibility scoring
5. Circular citation detection
6. Topic trend analysis over time

**Low Priority:**
7. Direct PDF support
8. Multi-language support
9. RSS feed integration

## 📞 Support

For issues or questions:
1. Check IMPROVEMENTS_SUMMARY.md for troubleshooting
2. Review prompt files for configuration
3. Verify Airtable schema matches requirements

## 📄 License

[Your license here]

## 🙏 Acknowledgments

Built on:
- Trafilatura for content extraction
- Streamlit for UI
- OpenAI GPT-4o-mini & Anthropic Claude Sonnet 4 for analysis
- Airtable for storage

---

**Version:** 1.2  
**Last Updated:** January 2025  
**Status:** Production Ready
