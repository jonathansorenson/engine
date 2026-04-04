# CRE Lytic Engine — Marketing Context Document

> Use this document as context in other sessions to build marketing materials, landing pages, ad copy, sales decks, and content strategy for the CRE Lytic underwriting engine.

---

## Company

**Rising Tide Property Group** builds AI-powered tools for commercial real estate professionals.

- Website: risingtidepg.com / crelytic.ai
- Engine URL: engine.crelytic.ai
- Target market: CRE investors, acquisitions analysts, fund managers, brokers, syndicators
- Founded by Jonathan Sorenson

---

## Product Overview

**CRE Lytic Engine** is an AI-powered commercial real estate deal underwriting platform. Users upload an Offering Memorandum (PDF) or financial Excel files and the engine automatically extracts property data, builds a full DCF model, runs sensitivity analysis, generates LP/GP waterfall distributions, and produces institutional-quality investment memos — in minutes instead of hours.

### One-Liner Options
- "AI-powered CRE deal underwriting in minutes, not hours."
- "Upload an OM. Get a full DCF, waterfall, and investment memo — instantly."
- "The underwriting engine built for CRE deal speed."

### Elevator Pitch (30 seconds)
CRE Lytic Engine lets acquisitions teams upload an Offering Memorandum and get a complete underwriting package — DCF projections, sensitivity analysis, LP/GP waterfall, and a polished investment memo — all generated automatically by AI. What used to take an analyst 4-6 hours now takes 5 minutes. It works with PDFs, Excel rent rolls, ARGUS exports, and T12 statements out of the box.

---

## Target Personas

### 1. Acquisitions Analyst (Primary)
- Drowning in deal flow, needs to screen OMs fast
- Currently builds models manually in Excel for each deal
- Pain: 4-6 hours per deal underwrite, repetitive setup
- Value: Instant first-pass underwriting, focus time on deals that matter

### 2. Fund Manager / Principal
- Needs consistent underwriting standards across the team
- Wants quick deal screening before committing analyst time
- Pain: Inconsistent modeling, slow turnaround, missed deals
- Value: Standardized output, compare deals apples-to-apples

### 3. CRE Broker / Advisor
- Needs to evaluate listing pricing and prepare marketing packages
- Pain: Limited modeling capability, relies on external analysts
- Value: Self-serve underwriting without Excel expertise

### 4. Syndicator / Sponsor
- Packages deals for LP investors
- Needs professional memos and waterfall analysis
- Pain: Expensive consultants, manual memo preparation
- Value: Instant LP-ready materials with waterfall splits

---

## Pricing

| Plan | Monthly Price | Monthly Uploads | Total Deals Stored |
|---|---|---|---|
| Starter | $6.99/mo | 5 deals/month | 50 deals |
| Pro | $11.99/mo | 25 deals/month | 200 deals |
| Unlimited | $20/mo | Unlimited | Unlimited |
| Enterprise | Custom | Unlimited | Unlimited |

- Self-service signup with Stripe checkout
- 14-day billing cycle reset
- Upgrade/downgrade anytime via Stripe portal

---

## Complete Feature List

### Document Parsing (AI-Powered)
- **PDF Offering Memorandum parsing** — Upload a PDF OM and the AI extracts property name, address, type, square footage, financials, rent roll, and investment assumptions automatically
- **Excel rent roll parsing** — Handles 40+ header variations with fuzzy matching. Supports multi-row headers, merged cells, varied date formats
- **ARGUS Enterprise import** — Parses multi-sheet ARGUS exports including Executive Summary, Cash Flow projections, Lease Summary, Market Leasing, and OpEx Detail
- **T12 operating statement parsing** — Extracts monthly and annualized income/expense breakdowns from trailing 12-month statements
- **Multi-file upload** — Upload PDF + Excel simultaneously for richer data extraction
- **Parse quality scoring** — Auto-grades extraction confidence (0-100) with warnings for missing fields

### DCF Financial Modeling
- **Fully-built DCF** — Multi-year Net Operating Income projections with rent escalations, expense growth, and lease turnover modeling
- **Customizable assumptions** — Going-in cap rate, exit cap rate, NOI growth, hold period (1-15 years), closing costs — all editable with instant model recalculation
- **Debt modeling** — LTV-based or fixed loan amount, configurable interest rate, amortization period, and interest-only terms
- **Annual cash flow projections** — Rental income, operating expenses, NOI, debt service, levered cash flow, unlevered cash flow — year by year
- **Exit reversion** — Terminal value based on exit cap rate applied to forward NOI, net of disposition costs and loan payoff

### Investment Returns
- **Levered IRR** — Return on equity including leverage effects
- **Unlevered IRR** — Return on total asset value without debt
- **Cash-on-Cash yield** — Annual levered cash flow as % of equity invested
- **Equity Multiple** — Total distributions divided by total equity
- **DSCR** — Debt Service Coverage Ratio for loan risk assessment
- **Debt Yield** — NOI as % of loan amount
- **Yield on Cost** — Stabilized NOI / total project cost
- **Return attribution** — Breaks down returns into cash flow, appreciation, and principal paydown components

### LP/GP Waterfall Analysis
- **Syndication structure** — Configure LP/GP split (50-99% LP), preferred return, catch-up provision
- **3-tier promote** — Configurable IRR hurdles with GP promote at each tier (e.g., <15% IRR, 15-20%, >20%)
- **Year-by-year waterfall table** — Shows annual distributions to LP and GP with preferred return accrual
- **Terminal distribution** — Exit proceeds split through waterfall tiers
- **Direct investor mode** — Simplified view for non-syndicated deals
- **GO/NO-GO indicator** — Automated investment recommendation based on target returns

### Sensitivity Analysis
- **Purchase Price vs Exit Cap Rate matrix** — 2D table showing IRR, equity multiple, or cash-on-cash across scenarios
- **LTV vs Interest Rate matrix** — Stress test leverage scenarios
- **Color-coded cells** — Green (above target), amber (marginal), red (below target)
- **Metric toggle** — Switch between IRR, Equity Multiple, or Cash-on-Cash in any table
- **Real-time recalculation** — Tables update instantly as assumptions change

### Rent Roll Management
- **Full tenant table** — Suite/unit, tenant name, SF, rent PSF, annual rent, CAM, lease start/end, type, escalation %, TI, LC
- **Lease type support** — NNN, Gross, Modified Gross, NN, N
- **Lease expiration schedule** — Visualize roll-over risk by year
- **WALT calculation** — Weighted Average Lease Term
- **Occupancy tracking** — Total occupied vs available SF
- **Inline editing** — Modify any tenant field, model updates instantly
- **Add/remove tenants** — Manual entry for custom scenarios

### Value-Add & Capex Modeling
- **Income events** — Model rent increases, ancillary income, NOI uplift by year
- **Expense events** — Model cost reductions, efficiency gains
- **Capital expenditures** — Line-item capex by year with category labels
- **Cash flow impact** — All events flow through to DCF and return calculations

### Charts & Visualizations
- **NOI vs Debt Service vs Net Cash Flow** — Multi-year bar/line chart
- **Equity build & cumulative cash flow** — Stacked return visualization
- **Loan balance progression** — Principal paydown over hold period
- **Lease expiration chart** — Tenant roll-over by year
- **All charts update in real-time** as assumptions change

### Export & Reporting
- **Excel workbook export** — Multi-sheet .xlsx with Deal Summary, Rent Roll, 10-Year Pro Forma, Debt Schedule, Sensitivity Tables, and Waterfall distributions. Professional formatting with color-coded metrics
- **Word investment memo** — Institutional-quality .docx with executive summary, property description, financial KPIs, rent roll table, waterfall summary, returns analysis, and risk factors
- **PDF memo** — Print-ready format via browser
- **One-click generation** — Full package ready for IC review in seconds

### AI Chat Assistant
- **Deal-aware Q&A** — Ask questions about any deal and get instant answers grounded in the actual numbers
- **Streaming responses** — Real-time text generation powered by Claude
- **Conversation history** — Chat context preserved per deal
- **Example questions**: "Is this deal above our hurdle rate?", "What's the lease expiry risk?", "Explain the waterfall splits", "What's the DSCR?"

### Deal Comparison
- **Side-by-side metrics** — Compare all deals in your portfolio on capital metrics, returns, and risk
- **Best-performer highlighting** — Top deal per metric visually marked
- **Sortable & filterable** — Rank deals by any return metric

### Administration
- **User management** — Create, edit, disable, delete users
- **Role-based access** — Admin (full access), Analyst (standard), Viewer (read-only)
- **Subscription tier control** — Assign Free, Starter, Pro, or Admin tiers
- **Fund-level data isolation** — Each user's deals are private to their account
- **Stripe billing integration** — Self-service upgrade, downgrade, cancel

---

## Technical Differentiators

- **No Excel required** — Entire underwriting workflow happens in-browser
- **AI extraction, not templates** — Works with any OM format, not rigid templates
- **Instant modeling** — Changes to assumptions recalculate the entire model in real-time
- **ARGUS-compatible** — Import directly from ARGUS Enterprise exports
- **Institutional output** — Memo and Excel quality matches what top funds produce manually
- **Cloud-native** — Access from anywhere, no software install, data persists across sessions
- **Multi-tenant** — Built for teams with per-user data isolation

---

## Competitive Positioning

### vs. Excel Spreadsheets
- 50x faster first-pass underwriting
- No formula errors or broken links
- Consistent output across team members
- Instant sensitivity analysis (no manual scenario tables)

### vs. ARGUS Enterprise
- Fraction of the cost ($6.99/mo vs $10K+/year)
- AI-powered document parsing (no manual data entry)
- Built for acquisitions screening (fast in/out), not asset management
- Modern web UI, not legacy desktop software

### vs. Other CRE Tech (Dealpath, Reonomy, etc.)
- Full underwriting engine, not just deal tracking or data
- Generates institutional-quality financial models, not just dashboards
- AI chat assistant for deal Q&A
- LP/GP waterfall built in (most competitors don't model distributions)

---

## Key Stats & Proof Points

- Full OM-to-investment-memo in under 5 minutes
- Supports 40+ rent roll header variations automatically
- 10-year DCF with waterfall in one click
- Export to Excel, Word, or PDF with one button
- AI-powered — uses Claude for document parsing and deal Q&A
- Monthly upload limits reset automatically (subscription-based)

---

## Brand Voice & Messaging Guidelines

### Tone
- **Professional but approachable** — We're talking to finance professionals, not developers
- **Confident, not salesy** — Let the product speak. No "revolutionary" or "game-changing"
- **Speed-focused** — Always emphasize time savings and workflow efficiency
- **Institutional credibility** — Output quality matters. Emphasize IC-ready, LP-ready materials

### Key Messages (ranked by importance)
1. **Speed**: "Upload an OM, get a full underwriting package in minutes"
2. **Quality**: "Institutional-grade DCF, waterfall, and memos — automatically"
3. **Simplicity**: "No Excel. No templates. Just upload and go."
4. **AI-Powered**: "AI extracts the data, builds the model, answers your questions"
5. **Affordable**: "Full underwriting capability starting at $6.99/month — unlimited at $20/month"

### Words to Use
- Underwriting, deal screening, acquisitions, DCF, waterfall, sensitivity analysis
- Upload, extract, parse, model, project, export
- Institutional-grade, IC-ready, LP-ready, investment memo
- AI-powered, automated, instant, real-time

### Words to Avoid
- Revolutionary, game-changing, disruptive (overused)
- Simple/easy (CRE people want powerful, not simple)
- Cheap (use "affordable" or "fraction of the cost")
- Bot, chatbot (use "AI assistant" or "deal chat")

---

## URLs & Assets

- **Marketing site**: crelytic.ai
- **Engine app**: engine.crelytic.ai
- **Signup page**: engine.crelytic.ai/engine/signup
- **Login page**: engine.crelytic.ai/engine/login
- **Company site**: risingtidepg.com
- **GitHub**: github.com/jonathansorenson/engine (private)

---

## Tech Stack (for technical marketing / integrations page)

- **AI**: Anthropic Claude (document parsing + deal chat)
- **Backend**: Python / FastAPI
- **Frontend**: React (single-page application)
- **Database**: PostgreSQL on Supabase
- **Hosting**: Render (Docker)
- **Payments**: Stripe (subscriptions + customer portal)
- **Charts**: Chart.js
- **Exports**: OpenPyXL (Excel), python-docx (Word)
