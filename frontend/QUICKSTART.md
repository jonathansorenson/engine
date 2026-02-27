# Quick Start Guide

## 1. Open the App

Simply open `index.html` in your browser. No build process, no dependencies to install.

```bash
# macOS
open index.html

# Linux
firefox index.html
# or
chromium index.html

# Windows
start index.html
```

Or serve via HTTP:
```bash
# Python 3
python -m http.server 8080

# Python 2
python -m SimpleHTTPServer 8080

# Node.js
npx http-server
```

Then navigate to `http://localhost:8080`

## 2. Demo Mode (Default)

The app ships with **DEMO_MODE enabled**, showing sample deals:
- Westlake Commerce Center (Industrial, Austin)
- Central Plaza Office (Office, Denver)

All features are fully functional in demo mode. Try:
- Click "Westlake Commerce Center" → Opens dashboard
- Adjust any slider → All metrics update instantly
- View sensitivity tables and cash flow projections
- Click "Upload New Deal" → See the upload interface

## 3. Connect to Backend

When your FastAPI backend is running:

**Step 1:** Edit the HTML file
```javascript
// Find line 47
const DEMO_MODE = true;

// Change to
const DEMO_MODE = false;
```

**Step 2:** Ensure API is accessible
```bash
# Backend should be running on
curl http://localhost:8000/api/v1/deals
# Should return valid JSON
```

**Step 3:** Refresh the browser
- The app will now fetch real deals from your backend
- File uploads will analyze documents through FastAPI
- Chat widget will connect to your AI model

## 4. Customize API URL

Default: `http://localhost:8000`

To change (line 48 in the HTML):
```javascript
const API_URL = 'http://your-backend-url.com';
```

## 5. Troubleshooting

### "No deals" message in Demo Mode
- This shouldn't happen. The demo data is hardcoded.
- Check browser console (F12) for JavaScript errors
- Try clearing cache: Ctrl+Shift+Delete

### Backend connection issues
- Verify FastAPI server is running
- Check CORS settings in backend (should allow localhost)
- Open browser DevTools → Network tab → check API calls
- Ensure `DEMO_MODE = false` is set

### Chat widget not responding
- If using demo mode: works instantly
- If using backend: verify `/api/v1/deals/{id}/chat` endpoint
- Response must be `text/event-stream` (SSE)

### Sensitivity tables showing "NaN"
- Check that asking price and NOI are populated
- Verify exit cap rate is not 0%
- Look for calculation errors in browser console

### Sliders not updating values
- Ensure JavaScript is enabled
- Check browser console for errors
- Try refreshing the page

## 6. Features Walkthrough

### Deal List (Home Screen)
```
┌─────────────────────────────────────┐
│ Underwriting Pipeline               │
│                       [Upload New Deal]
├─────────────────────────────────────┤
│ Property Name  | Price | Cap | NOI  │
│ Western...     | $45.0M| 6.0%|2.7M  │
│ Central...     | $32.0M| 6.0%|1.9M  │
└─────────────────────────────────────┘
```

Click any property name or "View" button → Opens dashboard

### Upload Deal
```
┌─────────────────────────────────────┐
│ Drag PDF or Excel files here        │
│                                     │
│          [Click to browse]          │
│                                     │
│ Added files:                        │
│ ✓ offering_memo.pdf (2.3 MB)       │
│ ✓ financials.xlsx (156 KB)         │
│                              [Analyze]
└─────────────────────────────────────┘
```

After clicking "Analyze" → Wait for parsing → Auto-redirects to dashboard

### Dashboard (Main Analysis Screen)

**Top Section:**
- Property name, address, type, square footage
- 6 KPI cards: Price, Cap Rate, NOI, Price/SF, DSCR, LTV

**Middle Section:**
- Left: 5 sliders for assumptions (exit cap, growth, hold, LTV, rate)
- Right: Chat widget with deal insights

**Bottom Section (Full Width):**
1. Sensitivity grid (property value under different scenarios)
2. 10-year cash flow projection
3. IRR sensitivity matrix
4. Rent roll table

**Real-Time Updates:**
- Change any slider → All metrics recalculate instantly
- Sensitivity tables show green (above asking) / red (below asking)
- Cash flow and IRR update dynamically

### Chat Widget
```
┌──────────────────────┐
│ Deal Insights        │
├──────────────────────┤
│ I've analyzed this   │
│ offering. Ask me     │
│ anything...          │
│                      │
│ [Your message...]    │
│             [Send]   │
└──────────────────────┘
```

Type any question about:
- Financial metrics and ratios
- Risk factors and tenant concentration
- Comparable market analysis
- "What if" scenario modeling
- Exit strategies and refinance opportunities

## 7. Understanding the Metrics

### Asking Price
Current market asking price for the property.

### Cap Rate
Cap rate = NOI / Asking Price. Lower cap rates = higher prices / lower yields.

### NOI (Net Operating Income)
Annual net operating income after operating expenses.

### Price / SF
Asking Price ÷ Rentable SF. Comparative metric across properties.

### DSCR (Debt Service Coverage Ratio)
NOI ÷ Annual Debt Service. Lenders typically want DSCR > 1.25x.

### LTV (Loan-to-Value)
Loan amount ÷ Property value. Higher LTV = more leverage, more risk.

### Sensitivity Grid
Shows property value under different exit scenarios:
- **Columns**: Exit cap rate (what you'll achieve at sale)
- **Rows**: NOI growth rate (annual appreciation)
- **Green**: Value above asking price (you profit)
- **Red**: Value below asking price (you lose)

### Cash Flow Projection
Year-by-year breakdown:
- **NOI**: Net operating income (with assumed growth)
- **Debt Service**: P&I payment on loan
- **Cap Reserves**: Annual capital replacement ($0.40/SF)
- **Cash Flow**: Available cash to equity holders
- **Loan Balance**: Outstanding principal remaining

### IRR (Internal Rate of Return)
Annual return to equity investors. Grid shows IRR under different exit cap rates and hold periods.

## 8. Sample Analysis Workflow

### The Deal
- **Property**: Westlake Commerce Center
- **Price**: $45.0M
- **NOI**: $2.7M (6% cap rate)
- **Size**: 320,000 SF
- **Asking**: $140/SF

### Your Assumptions
You believe:
- You'll exit at 6.5% cap rate (slightly higher)
- NOI will grow 2% annually
- You'll hold for 5 years
- Typical deal structure: 65% LTV, 4.5% interest, 25-year amort

### What the Dashboard Tells You
1. **Sensitivity grid**: At 6.5% cap and 2% growth, value = $46.3M → **You profit $1.3M**
2. **Cash flow**: Positive cash flow each year (5-year total $3.2M)
3. **IRR matrix**: 5-year hold at 6.5% exit = 14.2% levered IRR (excellent!)
4. **Rent roll**: Some vacancy risk in Suite D, but strong anchor tenants

### Quick Adjustments
Try these scenarios:
- **Conservative case**: Slide exit cap to 7.5% → Value drops, IRR still 9.8%
- **Optimistic case**: Slide NOI growth to 4% → Value up $8M, IRR 18.3%
- **Long hold**: Extend hold period to 7 years → IRR 16.1%

## 9. Common Questions

**Q: Is my data secure?**
A: All calculations happen in your browser. No data leaves your computer unless you upload files to the backend.

**Q: Can I print or export the analysis?**
A: Use your browser's Print function (Cmd+P or Ctrl+P). PDFs look professional and include all charts/tables.

**Q: How are IRR calculations performed?**
A: Newton-Raphson numerical method. Accounts for levered returns (includes debt impact).

**Q: What if a slider doesn't work?**
A: Refresh the page. Check browser console (F12) for JavaScript errors.

**Q: Can I upload deals offline?**
A: In demo mode, yes—but it just loads sample data. Real uploads require backend connectivity.

## 10. Tips for Institutional Use

- **Scenario Planning**: Use sliders to model bull/base/bear cases
- **Comparables**: Open multiple browser tabs to compare deals side-by-side
- **Presentations**: Screenshot the sensitivity grids for investor decks
- **Deep Dives**: Use chat widget to explore deal-specific questions
- **Rent Roll Review**: Cross-reference with lease abstracts and tenant financials
- **Risk Assessment**: Look for lease expiration clustering and tenant concentration

---

**Support**: Check the backend logs if anything fails. This frontend is stateless—all failures are either browser issues or API connectivity problems.
