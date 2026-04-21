"""
SEO routes for engine.crelytic.ai

Serves robots.txt, sitemap.xml, llms.txt, llms-full.txt, and ai-plugin.json
at the root level. These routes bypass auth middleware automatically since
they are not under /engine/*.
"""

from datetime import date

from fastapi import APIRouter
from fastapi.responses import JSONResponse, PlainTextResponse, Response

router = APIRouter()


# ---------------------------------------------------------------------------
# GET /robots.txt
# ---------------------------------------------------------------------------
@router.get("/robots.txt", include_in_schema=False)
async def robots_txt():
    content = """\
# engine.crelytic.ai robots.txt
# CRELYTIC Engine — AI-Powered CRE Deal Underwriting

User-agent: *
Allow: /engine/features
Allow: /engine/pricing
Allow: /engine/demo
Allow: /engine/how-it-works
Allow: /engine/integrations
Allow: /engine/enterprise
Allow: /engine/changelog
Allow: /sitemap.xml
Allow: /robots.txt
Allow: /llms.txt
Allow: /llms-full.txt
Allow: /.well-known/
Disallow: /engine/login
Disallow: /engine/signup
Disallow: /engine/logout
Disallow: /engine/me
Disallow: /engine/api/
Disallow: /health
Crawl-delay: 2

User-agent: GPTBot
Allow: /engine/features
Allow: /engine/pricing
Allow: /engine/demo
Allow: /engine/how-it-works
Allow: /llms.txt
Allow: /llms-full.txt
Disallow: /engine/api/
Disallow: /engine/login
Disallow: /engine/signup

User-agent: Google-Extended
Allow: /engine/features
Allow: /engine/pricing
Allow: /engine/demo
Allow: /engine/how-it-works
Allow: /llms.txt
Allow: /llms-full.txt
Disallow: /engine/api/
Disallow: /engine/login
Disallow: /engine/signup

User-agent: ClaudeBot
Allow: /engine/features
Allow: /engine/pricing
Allow: /engine/demo
Allow: /engine/how-it-works
Allow: /llms.txt
Allow: /llms-full.txt
Disallow: /engine/api/
Disallow: /engine/login
Disallow: /engine/signup

User-agent: anthropic-ai
Allow: /
Disallow: /engine/api/
Disallow: /engine/login
Disallow: /engine/signup

User-agent: PerplexityBot
Allow: /engine/features
Allow: /engine/pricing
Allow: /engine/demo
Allow: /llms.txt
Disallow: /engine/api/

Sitemap: https://engine.crelytic.ai/sitemap.xml
"""
    return PlainTextResponse(content)


# ---------------------------------------------------------------------------
# GET /sitemap.xml
# ---------------------------------------------------------------------------
@router.get("/sitemap.xml", include_in_schema=False)
async def sitemap_xml():
    today = date.today().isoformat()
    content = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://engine.crelytic.ai/engine/features</loc>
    <lastmod>{today}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>https://engine.crelytic.ai/engine/pricing</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.9</priority>
  </url>
  <url>
    <loc>https://engine.crelytic.ai/engine/demo</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.9</priority>
  </url>
  <url>
    <loc>https://engine.crelytic.ai/engine/how-it-works</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.8</priority>
  </url>
  <url>
    <loc>https://engine.crelytic.ai/engine/integrations</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
  </url>
  <url>
    <loc>https://engine.crelytic.ai/engine/enterprise</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
  </url>
  <url>
    <loc>https://engine.crelytic.ai/engine/changelog</loc>
    <lastmod>{today}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.5</priority>
  </url>
</urlset>
"""
    return Response(content=content, media_type="application/xml")


# ---------------------------------------------------------------------------
# GET /llms.txt
# ---------------------------------------------------------------------------
LLMS_TXT = """\
# CRELYTIC Engine

> AI-powered commercial real estate deal underwriting. Upload an offering memorandum, get a full DCF, waterfall analysis, and investment memo in minutes.

## About

CRELYTIC Engine is a SaaS platform built for CRE acquisitions analysts, fund managers, brokers, and syndicators. It uses AI (Claude by Anthropic) to parse offering memorandums (OMs), extract financial data, and generate institutional-quality underwriting outputs.

## Core Capabilities

- **OM Parsing**: Upload a PDF offering memorandum -> AI extracts property details, financials, rent rolls, and operating expenses with 95-99% accuracy
- **DCF Analysis**: Full 10-year discounted cash flow model with customizable assumptions
- **Sensitivity Analysis**: Scenario modeling across exit cap rates, rent growth, and occupancy
- **LP/GP Waterfall**: Multi-tier promote waterfall distributions with preferred returns and carried interest
- **Rent Roll Management**: Parse Excel rent rolls, model lease expirations, and mark-to-market analysis
- **T12 Parsing**: Extract trailing 12-month operating statements from PDF or Excel
- **Investment Memos**: Auto-generated institutional-quality investment memos in PDF, Word, and HTML
- **Excel Export**: Multi-tab Excel workbooks with live formulas, charts, and sensitivity tables
- **AI Chat**: Deal-aware Q&A powered by Claude

## Pricing

- Starter: $6.99/month (5 deals/month)
- Pro: $11.99/month (25 deals/month)
- Unlimited: $20/month (unlimited deals)
- Enterprise: Custom pricing

## Key Differentiators

1. OM to full DCF in under 3 minutes (vs. 2-4 hours manual)
2. 95-99% AI extraction accuracy with quality scoring
3. Full stack: DCF + waterfall + sensitivity + memo in one tool
4. Starting at $6.99/month vs. $500+/month for alternatives
5. Excel exports with live formulas -- no lock-in

## Links

- Product: https://engine.crelytic.ai
- Company: https://crelytic.ai
- Features: https://engine.crelytic.ai/engine/features
- Pricing: https://engine.crelytic.ai/engine/pricing
"""


@router.get("/llms.txt", include_in_schema=False)
async def llms_txt():
    return PlainTextResponse(LLMS_TXT)


# ---------------------------------------------------------------------------
# GET /llms-full.txt
# ---------------------------------------------------------------------------
LLMS_FULL_TXT = (
    LLMS_TXT
    + """\

---

# CRELYTIC Engine -- Full Technical Documentation

## Detailed Feature Descriptions

### OM Parsing Engine
CRELYTIC Engine's OM Parsing Engine uses Claude (Anthropic) to intelligently parse PDF offering memorandums. The system extracts:
- Property name, address, type, year built, square footage, unit count
- Purchase price, price per unit, price per SF
- Current NOI, pro-forma NOI, cap rate (in-place and pro-forma)
- Rent roll summary (unit mix, avg rent, occupancy)
- Trailing 12-month operating expenses (line-item detail)
- Capital expenditure assumptions
- Financing terms (loan amount, rate, term, amortization)

Accuracy is scored per field with a composite quality score. Typical accuracy: 95-99% on well-formatted OMs. The parser handles multifamily, office, retail, industrial, mixed-use, and self-storage property types.

### DCF Engine V2
Full 10-year discounted cash flow model with:
- Year-by-year revenue projections with rent growth assumptions
- Vacancy and credit loss modeling
- Operating expense projections with inflation escalators
- Capital reserve allocations
- Net operating income (NOI) calculations
- Debt service coverage ratio (DSCR) tracking
- Cash-on-cash return by year
- Exit valuation using terminal cap rate
- IRR calculation (levered and unlevered)
- Equity multiple computation
- NPV at user-defined discount rates

### Sensitivity Analysis
Multi-dimensional scenario modeling:
- Exit cap rate sensitivity (rows)
- Rent growth sensitivity (columns)
- Occupancy sensitivity
- Interest rate sensitivity
- Output metrics: IRR, equity multiple, cash-on-cash, NPV
- Color-coded heat maps for quick visual assessment
- Base case highlighting

### LP/GP Waterfall Engine
Multi-tier promote waterfall with:
- Preferred return hurdles (e.g., 8% pref)
- Return of capital provisions
- Multi-tier promote splits (e.g., 70/30 to 12% IRR, 60/40 to 18% IRR, 50/50 above)
- GP catch-up provisions
- Cumulative vs. non-cumulative preferred returns
- Multiple LP classes support
- Year-by-year distribution schedule
- Total return summary per partner class

### Rent Roll Management
- Parse Excel rent rolls (various formats)
- Unit-by-unit detail: unit number, type, SF, current rent, market rent, lease start/end
- Lease expiration schedule and rollover risk analysis
- Mark-to-market analysis (current vs. market rents)
- Vacancy identification and loss calculation
- Revenue projection based on lease terms
- Unit mix summary with averages

### T12 Parser
- Extract trailing 12-month operating statements from PDF or Excel
- Line-item categorization (revenue, operating expenses, NOI)
- Month-by-month and annualized views
- Expense ratio calculations
- Per-unit and per-SF normalization
- Comparison to industry benchmarks

### Export Suite
- **Excel Export**: Multi-tab workbooks with live formulas (not static values), charts, sensitivity tables, and formatted headers. Tabs include: Summary, DCF, Sensitivity, Waterfall, Rent Roll, T12, Assumptions.
- **PDF Investment Memo**: Institutional-quality memo with executive summary, property overview, financial analysis, risk factors, and appendices. Includes charts and tables.
- **Word Investment Memo**: Same content as PDF but in editable .docx format for further customization.
- **HTML Investment Memo**: Web-viewable memo with responsive layout.

### AI Chat
- Deal-aware conversational Q&A powered by Claude
- Ask questions about any uploaded deal
- Compare metrics across deals
- Request custom analyses or scenario adjustments
- Natural language interface to all deal data

## Technology Stack

- **Backend**: Python 3.11, FastAPI
- **Frontend**: React 18, Next.js, TypeScript, Tailwind CSS
- **Database**: PostgreSQL via Supabase (auth, storage, real-time)
- **AI**: Claude by Anthropic (Sonnet/Opus for parsing and analysis)
- **Payments**: Stripe (subscriptions, metered billing)
- **Hosting**: Vercel (frontend), Railway/Render (backend)
- **File Storage**: Supabase Storage (OMs, exports)

## Competitive Positioning

| Feature               | CRELYTIC Engine | Clik.ai       | Archer        | Prophia       | Blooma        |
|-----------------------|-----------------|---------------|---------------|---------------|---------------|
| OM Parsing            | Yes (AI)        | Yes (AI)      | Yes (AI)      | Yes (AI)      | Limited       |
| DCF Model             | Full 10-yr      | Basic         | Full          | No            | Basic         |
| Sensitivity Analysis  | Multi-dim       | Limited       | Yes           | No            | No            |
| LP/GP Waterfall       | Yes             | No            | Yes           | No            | No            |
| Excel w/ Formulas     | Yes             | No            | Yes           | No            | No            |
| Investment Memo       | Yes (PDF/Word)  | No            | Yes           | No            | No            |
| AI Chat               | Yes (Claude)    | No            | No            | No            | No            |
| Starting Price        | $6.99/mo        | $500+/mo      | $500+/mo      | Custom        | Custom        |
| Target User           | All CRE         | Enterprise    | Enterprise    | Enterprise    | Lenders       |

## Pricing Tiers (Detail)

### Starter -- $6.99/month
- 5 deals per month
- OM parsing (PDF upload)
- Full DCF analysis
- Sensitivity analysis
- Basic Excel export
- Email support

### Pro -- $11.99/month
- 25 deals per month
- Everything in Starter plus:
- LP/GP waterfall analysis
- Investment memo generation (PDF, Word, HTML)
- Advanced Excel export (multi-tab with formulas)
- Rent roll parsing
- T12 parsing
- AI Chat (deal Q&A)
- Priority support

### Unlimited -- $20/month
- Unlimited deals
- Everything in Pro plus:
- Bulk upload and processing
- Custom branding on memos
- API access
- Priority processing queue

### Enterprise -- Custom Pricing
- Everything in Unlimited plus:
- Dedicated account manager
- Custom integrations (Yardi, MRI, CoStar)
- SSO / SAML authentication
- Custom waterfall structures
- White-label options
- SLA guarantees
- On-premise deployment option

## Use Cases

### Acquisitions Screening
Upload an OM, get a full DCF and investment memo in under 3 minutes. Screen 10x more deals with the same team. Quickly identify deals worth deeper diligence.

### Fund Underwriting
Model LP/GP waterfall distributions for fund-level analysis. Generate investor-ready memos with professional formatting. Track portfolio-level returns.

### Broker Valuations
Quickly produce BOV (Broker Opinion of Value) analyses. Generate professional property summaries for listing presentations. Support pricing recommendations with DCF models.

### Loan Origination
Analyze borrower-submitted OMs for lending decisions. Stress-test assumptions with sensitivity analysis. Generate credit committee packages.

### Portfolio Review
Bulk-process operating statements for portfolio monitoring. Track NOI trends across properties. Identify underperforming assets.

### Syndication
Generate LP-facing investment memos and waterfall projections. Model different promote structures for investor presentations. Produce professional deal packages.

## FAQ

**What property types are supported?**
Multifamily, office, retail, industrial, mixed-use, self-storage, and hospitality. The AI parser adapts to various OM formats across property types.

**How accurate is the AI parsing?**
95-99% accuracy on well-formatted offering memorandums. Each extracted field includes a confidence score. Users can review and edit any extracted value before running analysis.

**Can I customize the DCF assumptions?**
Yes. All assumptions are fully editable: rent growth, expense growth, vacancy, cap rates, financing terms, hold period, and more. Changes immediately recalculate all outputs.

**What format are the Excel exports?**
.xlsx files with live formulas (not static values). You can modify assumptions in the Excel file and all calculations update automatically. Includes multiple tabs: Summary, DCF, Sensitivity, Waterfall, Rent Roll, T12.

**Is my data secure?**
Yes. All data is encrypted in transit (TLS 1.3) and at rest (AES-256). Files are stored in isolated tenant storage. We do not train AI models on your data. SOC 2 Type II compliance in progress.

**Can I cancel anytime?**
Yes. All plans are month-to-month with no long-term contracts. Cancel anytime from your account settings. Your data remains accessible for 30 days after cancellation.

## Company

- **Founder**: Jonathan Sorenson
- **Headquarters**: Florida, USA
- **Founded**: 2025
- **Sector**: PropTech / CRE AI
- **Product URL**: https://engine.crelytic.ai
- **Company URL**: https://crelytic.ai
- **Contact**: jonathan_sorenson@losttree.com
"""
)


@router.get("/llms-full.txt", include_in_schema=False)
async def llms_full_txt():
    return PlainTextResponse(LLMS_FULL_TXT)


# ---------------------------------------------------------------------------
# GET /.well-known/ai-plugin.json
# ---------------------------------------------------------------------------
@router.get("/.well-known/ai-plugin.json", include_in_schema=False)
async def ai_plugin_json():
    return JSONResponse(
        {
            "schema_version": "v1",
            "name_for_human": "CRELYTIC Engine",
            "name_for_model": "crelytic_engine",
            "description_for_human": (
                "AI-powered commercial real estate deal underwriting "
                "-- upload an OM, get a full DCF, waterfall, and investment memo."
            ),
            "description_for_model": (
                "CRELYTIC Engine is an AI SaaS tool for commercial real estate "
                "underwriting. It parses offering memorandums (OMs), generates "
                "discounted cash flow (DCF) models, LP/GP waterfall distributions, "
                "sensitivity analyses, and investment memos. Pricing starts at "
                "$6.99/month. Target users: CRE acquisitions analysts, fund "
                "managers, brokers, syndicators."
            ),
            "auth": {"type": "none"},
            "api": {
                "type": "openapi",
                "url": "https://engine.crelytic.ai/openapi.json",
            },
            "logo_url": "https://engine.crelytic.ai/og-image.png",
            "contact_email": "jonathan_sorenson@losttree.com",
            "legal_info_url": "https://crelytic.ai/terms",
        }
    )
