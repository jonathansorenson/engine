# CRE Lytic — Deal Underwriting Engine (Frontend)

A professional, institutional-grade single-file React application for commercial real estate deal underwriting. Built with React 18, Chart.js, and inline CSS for instant deployment.

## Features

### 📋 Deal List View
- Browse all underwriting deals in a sortable table
- Key metrics at a glance: Asking Price, Cap Rate, NOI, Status
- Upload new deals directly from the interface
- Click any deal to open the full dashboard

### 📤 Upload View
- Drag-and-drop or click to upload PDF and Excel files
- Supports offering memoranda and financial statements
- Real-time parsing with progress indication
- Automatic redirect to dashboard after analysis

### 📊 Deal Dashboard (Main Product)
The comprehensive underwriting interface with:

#### KPI Cards
- Asking Price, Cap Rate, NOI, Price/SF, DSCR, LTV
- Formatted for institutional presentations
- Real-time updates as assumptions change

#### Assumption Sliders
Interactive controls for:
- **Exit Cap Rate**: 4.0% - 9.0%
- **NOI Growth**: -5% to +15%
- **Hold Period**: 1 - 15 years
- **LTV**: 0% - 80%
- **Interest Rate**: 3% - 8%

All sliders trigger instant recalculation of financial metrics.

#### Sensitivity Analysis
- Property value heat map (Cap Rate × NOI Growth)
- Green highlights values above asking price
- Red highlights values below asking price
- 11 cap rate scenarios × 7 NOI growth scenarios

#### 10-Year Cash Flow Projection
- Year-by-year NOI with assumed growth
- Constant debt service (P&I)
- Capital reserves ($0.40/SF annually)
- Net cash flow and remaining loan balance

#### IRR Sensitivity Matrix
- Exit cap rate (columns) × hold period (rows)
- Calculates levered IRR for each scenario
- Color-coded performance indicators

#### Rent Roll Table
- Sortable tenant roster with:
  - Unit identifier and tenant name
  - Rentable square footage
  - Annual rent and $/SF rates
  - Lease expiration dates

#### Deal Insights Chat
- Right sidebar chat widget with AI analysis
- Pre-loaded greeting with deal insights
- Send questions about financials, risk, comparables, scenarios
- Streaming response display (when backend available)

## API Integration

The app communicates with the FastAPI backend at:
```
http://localhost:8000/api/v1
```

### Endpoints Used
```
GET  /api/v1/deals                    # List all deals
POST /api/v1/deals                    # Upload and analyze new deal
GET  /api/v1/deals/{deal_id}          # Fetch single deal details
POST /api/v1/deals/{deal_id}/chat     # Chat with AI (SSE streaming)
```

## Setup & Deployment

### Option 1: Local Development
```bash
# Open the file in any modern browser
open index.html

# Or serve via simple HTTP server
python -m http.server 8080
# Navigate to http://localhost:8080
```

### Option 2: Demo Mode
The app includes **DEMO_MODE** flag (line 47 in the script):
- When `DEMO_MODE = true`: Shows sample data without backend
- When `DEMO_MODE = false`: Fetches from real API

To connect to your backend:
1. Set `DEMO_MODE = false` in the HTML
2. Ensure FastAPI server is running on `http://localhost:8000`
3. Refresh the browser

## Technical Stack

- **React 18** (via CDN)
- **React DOM 18** (via CDN)
- **Chart.js 4** (via CDN for future enhancements)
- **Babel Standalone** (for JSX transformation)
- **Vanilla CSS** (no build step required)
- **All inline** (~1,650 lines, self-contained)

## Financial Calculations

### Core Formulas Implemented

**Monthly Payment (P&I):**
```javascript
P = Principal × [r(1+r)^n] / [(1+r)^n - 1]
where r = annual rate / 12, n = years × 12
```

**Debt Service:** Monthly payment × 12

**Loan Balance at Year N:** Remaining principal after N years of payments

**IRR (Newton-Raphson method):** Iterative NPV calculation to find rate of return

**Property Value (Sensitivity Grid):**
```
Exit Year NOI = Current NOI × (1 + growth)^hold_years
Property Value = Exit Year NOI / Exit Cap Rate
```

## Design System

### Colors
- **Navy** (#1e3a5f): Headers, primary text
- **Blue** (#2563eb): Primary actions, highlights
- **Green** (#10b981): Positive values, above-asking scenarios
- **Red** (#ef4444): Negative values, below-asking scenarios
- **Amber** (#f59e0b): Warnings, alerts
- **Slate** (#64748b): Secondary text
- **Light Gray** (#f8fafc): Background
- **White** (#ffffff): Cards, form backgrounds

### Typography
- **System font stack**: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto
- **Monospace**: 'Courier New' for financial figures
- **Weight scale**: 400 (normal), 500 (semi-bold), 600 (bold), 700 (extra-bold)

### Responsive Breakpoints
- Desktop: 1400px max-width
- Tablet: 1024px (grid → 1 column)
- Mobile: 768px (compact sizing)

## Key Components

### Header
Logo, breadcrumb navigation, demo mode indicator

### KPI Cards
6-column grid of key financial metrics with trend indicators

### Assumption Sliders
Gradient sliders with real-time value display and range labels

### Sensitivity Tables
Color-coded grids for value and IRR analysis

### Chat Widget
Fixed right sidebar (sticky on desktop, bottom sheet on mobile)

### Rent Roll
Sortable tenant list with detailed lease information

## Data Format

### Deal Object
```json
{
  "id": "string",
  "property_name": "string",
  "address": "string",
  "property_type": "string",
  "asking_price": number,
  "noi": number,
  "rentable_sf": number,
  "cap_rate": number,
  "dscr": number,
  "ltv": number,
  "status": "active|draft|completed",
  "created_at": "ISO date",
  "assumptions": {
    "exit_cap_rate": number,
    "noi_growth": number,
    "hold_period": number,
    "ltv": number,
    "interest_rate": number,
    "amortization_years": number
  },
  "rent_roll": [
    {
      "unit": "string",
      "tenant": "string",
      "sf": number,
      "rent_psf": number,
      "annual_rent": number,
      "expiry": "string"
    }
  ]
}
```

## Number Formatting

- **Currency**: `$45.0M`, `$24.5K`, `$15,000` (1 decimal for millions/thousands)
- **Percentages**: `6.20%` (2 decimals)
- **Per SF**: `$12.50/SF` (2 decimals)
- **Square Footage**: `320,000 SF` (comma-separated)
- **Ratios**: `1.32x` (2 decimals)

## Browser Support

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

Requires ES6+ support and Fetch API.

## Performance Notes

- All financial calculations run client-side for instant slider feedback
- Sensitivity grids compute on every assumption change
- No debouncing (intentionally responsive for professional use)
- Cache dashboard state in localStorage for future enhancement

## Future Enhancements

- Chart visualization of cash flows (Chart.js integration)
- Comparable sales analysis
- Multi-deal comparison dashboard
- PDF export of underwriting summary
- User authentication and deal permissions
- Historical scenario tracking
- Integration with lease management systems

## License

Copyright © 2025 CRE Lytic. All rights reserved.
