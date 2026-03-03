"""Excel export endpoint — generates comprehensive .xlsx from deal data sent by frontend."""

import io
import math
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel as PydanticBaseModel
from typing import Optional, List, Dict, Any
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

router = APIRouter(prefix="/api/v1/export", tags=["export"])


# ═══════════════════════════════════════════════════════════
# REQUEST MODEL
# ═══════════════════════════════════════════════════════════

class ExportRequest(PydanticBaseModel):
    """Deal data sent from the frontend for Excel export."""
    property_name: str = "Untitled Deal"
    address: Optional[str] = None
    property_type: Optional[str] = None
    asking_price: Optional[float] = None
    noi: Optional[float] = None
    cap_rate: Optional[float] = None
    rentable_sf: Optional[float] = None
    occupancy_rate: Optional[float] = None
    operating_expenses: Optional[float] = None
    annual_revenue: Optional[float] = None
    year_built: Optional[int] = None
    assumptions: Optional[Dict[str, Any]] = None
    rent_roll: Optional[List[Dict[str, Any]]] = None
    source: Optional[str] = None
    argus_detail: Optional[Dict[str, Any]] = None


# ═══════════════════════════════════════════════════════════
# FINANCIAL HELPERS — mirror frontend JS calculations
# ═══════════════════════════════════════════════════════════

def _monthly_payment(principal: float, annual_rate: float, amort_years: int) -> float:
    r = annual_rate / 12
    n = amort_years * 12
    if r == 0:
        return principal / n if n > 0 else 0
    return principal * (r * (1 + r) ** n) / ((1 + r) ** n - 1)


def _annual_debt_service(principal: float, annual_rate: float, amort_years: int) -> float:
    return _monthly_payment(principal, annual_rate, amort_years) * 12


def _annual_debt_service_io(principal: float, annual_rate: float) -> float:
    return principal * annual_rate


def _loan_balance_at_year(principal: float, annual_rate: float, amort_years: int, year_n: int) -> float:
    r = annual_rate / 12
    n = amort_years * 12
    p = year_n * 12
    pmt = _monthly_payment(principal, annual_rate, amort_years)
    if r == 0:
        return principal - (pmt * p)
    return principal * (1 + r) ** p - pmt * ((1 + r) ** p - 1) / r


def _calculate_irr(cash_flows: list, guess: float = 0.10) -> Optional[float]:
    rate = guess
    for _ in range(200):
        npv = 0.0
        dnpv = 0.0
        for t, cf in enumerate(cash_flows):
            denom = (1 + rate) ** t
            if denom == 0:
                break
            npv += cf / denom
            dnpv -= t * cf / ((1 + rate) ** (t + 1))
        if abs(dnpv) < 1e-12:
            break
        new_rate = rate - npv / dnpv
        if abs(new_rate - rate) < 1e-8:
            return new_rate
        rate = new_rate
    return rate if abs(rate) < 10 else None


def _safe_pct(val, default=0):
    """Normalize a percentage value — if >1 treat as already ×100."""
    if val is None:
        return default
    return val / 100 if val > 1 else val


# ═══════════════════════════════════════════════════════════
# STYLES
# ═══════════════════════════════════════════════════════════

HEADER_FONT = Font(name="Calibri", bold=True, color="FFFFFF", size=11)
HEADER_FILL = PatternFill(start_color="0A1628", end_color="0A1628", fill_type="solid")
SUBHEADER_FILL = PatternFill(start_color="132A42", end_color="132A42", fill_type="solid")
SUBHEADER_FONT = Font(name="Calibri", bold=True, size=11, color="E8EDF2")
LABEL_FONT = Font(name="Calibri", bold=True, size=10, color="8A9BB0")
VALUE_FONT = Font(name="Calibri", size=10)
TITLE_FONT = Font(name="Calibri", bold=True, size=14, color="0A1628")
GREEN_FILL = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")
RED_FILL = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")
AMBER_FILL = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid")
GREEN_FONT = Font(name="Calibri", size=10, color="166534")
RED_FONT = Font(name="Calibri", size=10, color="991B1B")

CURRENCY_FMT = '#,##0'
CURRENCY_CENTS_FMT = '#,##0.00'
PERCENT_FMT = '0.00%'
NUMBER_FMT = '#,##0'
RATIO_FMT = '0.00"x"'
THIN_BORDER = Border(
    left=Side(style="thin", color="D0D0D0"),
    right=Side(style="thin", color="D0D0D0"),
    top=Side(style="thin", color="D0D0D0"),
    bottom=Side(style="thin", color="D0D0D0"),
)


def _style_header_row(ws, row, num_cols):
    for col in range(1, num_cols + 1):
        cell = ws.cell(row=row, column=col)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center")
        cell.border = THIN_BORDER


def _add_kv_row(ws, row, label, value, value_fmt=None):
    lc = ws.cell(row=row, column=1, value=label)
    lc.font = LABEL_FONT
    lc.border = THIN_BORDER
    vc = ws.cell(row=row, column=2, value=value)
    vc.font = VALUE_FONT
    vc.border = THIN_BORDER
    if value_fmt:
        vc.number_format = value_fmt
    return row + 1


def _section_header(ws, row, title, cols=2):
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=cols)
    cell = ws.cell(row=row, column=1, value=title)
    cell.font = SUBHEADER_FONT
    cell.fill = SUBHEADER_FILL
    for c in range(1, cols + 1):
        ws.cell(row=row, column=c).fill = SUBHEADER_FILL
        ws.cell(row=row, column=c).border = THIN_BORDER
    return row + 1


# ═══════════════════════════════════════════════════════════
# EXPORT ENDPOINT
# ═══════════════════════════════════════════════════════════

@router.post("")
async def export_deal_to_excel(data: ExportRequest):
    """Generate comprehensive Excel workbook from deal data."""
    wb = Workbook()

    # Parse assumptions
    a = data.assumptions or {}
    ltv = _safe_pct(a.get("ltv"), 0.65)
    interest_rate = _safe_pct(a.get("interest_rate"), 0.055)
    exit_cap = _safe_pct(a.get("exit_cap_rate"), 0.065)
    noi_growth = _safe_pct(a.get("noi_growth"), 0.02)
    hold_period = int(a.get("hold_period", 5))
    amort_years = int(a.get("amortization_years", 25))
    is_io = bool(a.get("interest_only", False))
    io_term = int(a.get("io_term", 5))

    asking_price = data.asking_price or 0
    noi = data.noi or 0
    cap_rate = _safe_pct(data.cap_rate, 0)
    rentable_sf = data.rentable_sf or 0
    debt = asking_price * ltv
    equity = asking_price * (1 - ltv)

    # Debt service
    if debt > 0:
        if is_io:
            ads = _annual_debt_service_io(debt, interest_rate)
        else:
            ads = _annual_debt_service(debt, interest_rate, amort_years)
    else:
        ads = 0

    hold_years = io_term if is_io else hold_period
    dscr = noi / ads if ads > 0 else 0
    coc = (noi - ads) / equity if equity > 0 else 0
    price_per_sf = asking_price / rentable_sf if rentable_sf > 0 else 0
    debt_per_foot = debt / rentable_sf if rentable_sf > 0 else 0
    debt_yield = noi / debt if debt > 0 else 0
    debt_constant = ads / debt if debt > 0 else 0
    leverage_spread = cap_rate - debt_constant

    # ══════════════════════════════════════════
    # Sheet 1: Executive Summary
    # ══════════════════════════════════════════
    ws = wb.active
    ws.title = "Executive Summary"
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 22

    ws.merge_cells("A1:B1")
    ws.cell(row=1, column=1, value=data.property_name).font = TITLE_FONT

    row = 3
    row = _section_header(ws, row, "Property Details")
    if data.address:
        row = _add_kv_row(ws, row, "Address", data.address)
    if data.property_type:
        row = _add_kv_row(ws, row, "Property Type", data.property_type)
    if rentable_sf > 0:
        row = _add_kv_row(ws, row, "Rentable SF", rentable_sf, NUMBER_FMT)
    if data.source:
        row = _add_kv_row(ws, row, "Data Source", data.source.upper())

    row += 1
    row = _section_header(ws, row, "Financial KPIs")
    row = _add_kv_row(ws, row, "Asking Price", asking_price, CURRENCY_FMT)
    row = _add_kv_row(ws, row, "Net Operating Income (NOI)", noi, CURRENCY_FMT)
    row = _add_kv_row(ws, row, "Going-In Cap Rate", cap_rate, PERCENT_FMT)
    if rentable_sf > 0:
        row = _add_kv_row(ws, row, "Price / SF", price_per_sf, CURRENCY_CENTS_FMT)
    row = _add_kv_row(ws, row, "Equity Required", equity, CURRENCY_FMT)
    row = _add_kv_row(ws, row, "Cash-on-Cash (Year 1)", coc, PERCENT_FMT)
    row = _add_kv_row(ws, row, "DSCR", dscr, RATIO_FMT)
    row = _add_kv_row(ws, row, "LTV", ltv, PERCENT_FMT)

    row += 1
    row = _section_header(ws, row, "Debt Metrics")
    row = _add_kv_row(ws, row, "Loan Amount", debt, CURRENCY_FMT)
    if rentable_sf > 0:
        row = _add_kv_row(ws, row, "Debt / Foot", debt_per_foot, CURRENCY_CENTS_FMT)
    row = _add_kv_row(ws, row, "Annual Debt Service", ads, CURRENCY_FMT)
    row = _add_kv_row(ws, row, "Debt Yield", debt_yield, PERCENT_FMT)
    row = _add_kv_row(ws, row, "Debt Constant", debt_constant, PERCENT_FMT)
    row = _add_kv_row(ws, row, "Leverage Spread (Cap - DC)", leverage_spread, PERCENT_FMT)
    if is_io:
        row = _add_kv_row(ws, row, "Interest Only", f"Yes — {io_term} year term")
    else:
        row = _add_kv_row(ws, row, "Interest Only", "No — Amortizing")

    row += 1
    row = _section_header(ws, row, "Underwriting Assumptions")
    row = _add_kv_row(ws, row, "Exit Cap Rate", exit_cap, PERCENT_FMT)
    row = _add_kv_row(ws, row, "NOI Growth Rate", noi_growth, PERCENT_FMT)
    row = _add_kv_row(ws, row, "Hold Period", f"{hold_years} years")
    row = _add_kv_row(ws, row, "Interest Rate", interest_rate, PERCENT_FMT)
    row = _add_kv_row(ws, row, "Amortization", f"{amort_years} years")

    # ══════════════════════════════════════════
    # Sheet 2: Cash Flow Projections
    # ══════════════════════════════════════════
    ws2 = wb.create_sheet("Cash Flow Projections")
    headers = ["Year", "NOI", "Debt Service", "Cap Reserves", "Cash Flow", "Loan Balance", "Cash-on-Cash"]
    col_widths = [8, 16, 16, 16, 16, 18, 14]
    for i, w in enumerate(col_widths):
        ws2.column_dimensions[chr(65 + i)].width = w

    ws2.merge_cells("A1:G1")
    title = f"Cash Flow Projection — {'Interest Only' if is_io else 'Amortizing'}"
    ws2.cell(row=1, column=1, value=title).font = TITLE_FONT

    row = 3
    for ci, h in enumerate(headers, 1):
        cell = ws2.cell(row=row, column=ci, value=h)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center")
        cell.border = THIN_BORDER
    row += 1

    cap_reserve_psf = 0.40
    total_noi = total_ds = total_cf = 0

    for yr in range(1, hold_years + 1):
        yr_noi = noi * (1 + noi_growth) ** (yr - 1)
        yr_ds = ads
        yr_cap = rentable_sf * cap_reserve_psf
        yr_cf = yr_noi - yr_ds - yr_cap
        if is_io:
            yr_bal = debt
        else:
            yr_bal = _loan_balance_at_year(debt, interest_rate, amort_years, yr) if debt > 0 else 0
        yr_coc = (yr_noi - yr_ds) / equity if equity > 0 else 0

        total_noi += yr_noi
        total_ds += yr_ds
        total_cf += yr_cf

        ws2.cell(row=row, column=1, value=yr).border = THIN_BORDER
        ws2.cell(row=row, column=2, value=yr_noi).number_format = CURRENCY_FMT
        ws2.cell(row=row, column=2).border = THIN_BORDER
        ws2.cell(row=row, column=3, value=yr_ds).number_format = CURRENCY_FMT
        ws2.cell(row=row, column=3).border = THIN_BORDER
        ws2.cell(row=row, column=4, value=yr_cap).number_format = CURRENCY_FMT
        ws2.cell(row=row, column=4).border = THIN_BORDER

        cf_cell = ws2.cell(row=row, column=5, value=yr_cf)
        cf_cell.number_format = CURRENCY_FMT
        cf_cell.border = THIN_BORDER
        cf_cell.font = Font(name="Calibri", bold=True, color="166534" if yr_cf > 0 else "991B1B")

        ws2.cell(row=row, column=6, value=yr_bal).number_format = CURRENCY_FMT
        ws2.cell(row=row, column=6).border = THIN_BORDER

        coc_cell = ws2.cell(row=row, column=7, value=yr_coc)
        coc_cell.number_format = PERCENT_FMT
        coc_cell.border = THIN_BORDER
        if yr_coc > 0.08:
            coc_cell.fill = GREEN_FILL
        elif yr_coc < 0:
            coc_cell.fill = RED_FILL

        row += 1

    # Totals
    for ci in range(1, 8):
        ws2.cell(row=row, column=ci).border = THIN_BORDER
        ws2.cell(row=row, column=ci).font = Font(name="Calibri", bold=True, size=10)
    ws2.cell(row=row, column=1, value="TOTAL")
    ws2.cell(row=row, column=2, value=total_noi).number_format = CURRENCY_FMT
    ws2.cell(row=row, column=3, value=total_ds).number_format = CURRENCY_FMT
    ws2.cell(row=row, column=4, value=rentable_sf * cap_reserve_psf * hold_years).number_format = CURRENCY_FMT
    ws2.cell(row=row, column=5, value=total_cf).number_format = CURRENCY_FMT

    # ══════════════════════════════════════════
    # Sheet 3: IRR Sensitivity Matrix
    # ══════════════════════════════════════════
    ws3 = wb.create_sheet("IRR Sensitivity")
    exit_caps = [0.055, 0.060, 0.065, 0.070, 0.075, 0.080]
    hold_periods = [3, 5, 7, 10]

    ws3.merge_cells("A1:E1")
    ws3.cell(row=1, column=1, value="Levered IRR Sensitivity — Exit Cap × Hold Period").font = TITLE_FONT
    ws3.column_dimensions["A"].width = 16

    row = 3
    # Header
    ws3.cell(row=row, column=1, value="Exit Cap ↓ / Hold →").font = HEADER_FONT
    ws3.cell(row=row, column=1).fill = HEADER_FILL
    ws3.cell(row=row, column=1).border = THIN_BORDER
    for ci, hp in enumerate(hold_periods, 2):
        cell = ws3.cell(row=row, column=ci, value=f"{hp} Years")
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center")
        cell.border = THIN_BORDER
        ws3.column_dimensions[chr(64 + ci)].width = 14
    row += 1

    for ec in exit_caps:
        ws3.cell(row=row, column=1, value=ec).number_format = PERCENT_FMT
        ws3.cell(row=row, column=1).font = Font(name="Calibri", bold=True, size=10)
        ws3.cell(row=row, column=1).border = THIN_BORDER

        for ci, hp in enumerate(hold_periods, 2):
            # Build IRR cash flows
            flows = [-equity] if equity > 0 else [0]
            for yr in range(1, hp + 1):
                yr_noi = noi * (1 + noi_growth) ** (yr - 1)
                yr_ds = ads
                yr_cap = rentable_sf * cap_reserve_psf
                yr_cf = yr_noi - yr_ds - yr_cap
                flows.append(yr_cf)

            # Exit proceeds
            exit_noi = noi * (1 + noi_growth) ** hp
            sale_price = exit_noi / ec if ec > 0 else 0
            if is_io:
                exit_balance = debt
            else:
                exit_balance = _loan_balance_at_year(debt, interest_rate, amort_years, hp) if debt > 0 else 0
            sale_proceeds = sale_price - exit_balance
            flows[-1] += sale_proceeds

            irr = _calculate_irr(flows)
            cell = ws3.cell(row=row, column=ci)
            cell.border = THIN_BORDER
            cell.alignment = Alignment(horizontal="center")
            if irr is not None and abs(irr) < 5:
                cell.value = irr
                cell.number_format = PERCENT_FMT
                if irr > 0.15:
                    cell.fill = GREEN_FILL
                    cell.font = GREEN_FONT
                elif irr < 0:
                    cell.fill = RED_FILL
                    cell.font = RED_FONT
            else:
                cell.value = "N/A"

        row += 1

    # ══════════════════════════════════════════
    # Sheet 4: Property Value Sensitivity
    # ══════════════════════════════════════════
    ws4 = wb.create_sheet("Value Sensitivity")
    growth_rates = [-0.05, -0.025, 0, 0.025, 0.05, 0.075, 0.10]
    exit_cap_rates = [0.050, 0.055, 0.060, 0.065, 0.070, 0.075, 0.080]

    ws4.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(exit_cap_rates) + 1)
    ws4.cell(row=1, column=1, value=f"Property Value at Exit (Year {hold_years}) — NOI Growth × Exit Cap").font = TITLE_FONT
    ws4.column_dimensions["A"].width = 18

    row = 3
    ws4.cell(row=row, column=1, value="Growth ↓ / Cap →").font = HEADER_FONT
    ws4.cell(row=row, column=1).fill = HEADER_FILL
    ws4.cell(row=row, column=1).border = THIN_BORDER
    for ci, ecr in enumerate(exit_cap_rates, 2):
        cell = ws4.cell(row=row, column=ci, value=ecr)
        cell.number_format = PERCENT_FMT
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center")
        cell.border = THIN_BORDER
        ws4.column_dimensions[chr(64 + ci)].width = 16
    row += 1

    for gr in growth_rates:
        ws4.cell(row=row, column=1, value=gr).number_format = PERCENT_FMT
        ws4.cell(row=row, column=1).font = Font(name="Calibri", bold=True, size=10)
        ws4.cell(row=row, column=1).border = THIN_BORDER

        for ci, ecr in enumerate(exit_cap_rates, 2):
            exit_noi = noi * (1 + gr) ** hold_years
            exit_val = exit_noi / ecr if ecr > 0 else 0
            cell = ws4.cell(row=row, column=ci, value=exit_val)
            cell.number_format = CURRENCY_FMT
            cell.border = THIN_BORDER
            cell.alignment = Alignment(horizontal="center")
            if exit_val > asking_price and asking_price > 0:
                cell.fill = GREEN_FILL
                cell.font = GREEN_FONT
            elif asking_price > 0:
                cell.fill = RED_FILL
                cell.font = RED_FONT
        row += 1

    # ══════════════════════════════════════════
    # Sheet 5: Debt Analysis
    # ══════════════════════════════════════════
    ws5 = wb.create_sheet("Debt Analysis")
    ws5.column_dimensions["A"].width = 22
    ws5.column_dimensions["B"].width = 16
    ws5.column_dimensions["C"].width = 16
    ws5.column_dimensions["D"].width = 16
    ws5.column_dimensions["E"].width = 12

    ws5.merge_cells("A1:E1")
    ws5.cell(row=1, column=1, value="Debt Analysis & Leverage Assessment").font = TITLE_FONT

    row = 3
    row = _section_header(ws5, row, "Leverage Analysis", 2)
    row = _add_kv_row(ws5, row, "Going-In Cap Rate", cap_rate, PERCENT_FMT)
    row = _add_kv_row(ws5, row, "Debt Constant", debt_constant, PERCENT_FMT)
    row = _add_kv_row(ws5, row, "Leverage Spread", leverage_spread, PERCENT_FMT)
    if leverage_spread > 0.005:
        row = _add_kv_row(ws5, row, "Leverage Status", "✓ Positive — Favorable")
    elif leverage_spread > -0.005:
        row = _add_kv_row(ws5, row, "Leverage Status", "◐ Neutral")
    else:
        row = _add_kv_row(ws5, row, "Leverage Status", "✗ Negative — Unfavorable")

    # NOI vs Debt Service Table
    row += 1
    row = _section_header(ws5, row, "NOI vs Debt Service Projection", 5)
    headers5 = ["Year", "NOI", "Debt Service", "Free Cash Flow", "DSCR"]
    for ci, h in enumerate(headers5, 1):
        cell = ws5.cell(row=row, column=ci, value=h)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center")
        cell.border = THIN_BORDER
    row += 1

    t_noi = t_fcf = 0
    for yr in range(1, hold_years + 1):
        yr_noi = noi * (1 + noi_growth) ** (yr - 1)
        fcf = yr_noi - ads
        yr_dscr = yr_noi / ads if ads > 0 else 0
        t_noi += yr_noi
        t_fcf += fcf

        ws5.cell(row=row, column=1, value=yr).border = THIN_BORDER
        ws5.cell(row=row, column=2, value=yr_noi).number_format = CURRENCY_FMT
        ws5.cell(row=row, column=2).border = THIN_BORDER
        ws5.cell(row=row, column=3, value=ads).number_format = CURRENCY_FMT
        ws5.cell(row=row, column=3).border = THIN_BORDER
        ws5.cell(row=row, column=4, value=fcf).number_format = CURRENCY_FMT
        ws5.cell(row=row, column=4).border = THIN_BORDER
        ws5.cell(row=row, column=4).font = Font(name="Calibri", color="166534" if fcf > 0 else "991B1B")
        dscr_cell = ws5.cell(row=row, column=5, value=yr_dscr)
        dscr_cell.number_format = RATIO_FMT
        dscr_cell.border = THIN_BORDER
        if yr_dscr >= 1.25:
            dscr_cell.font = GREEN_FONT
        elif yr_dscr < 1.0:
            dscr_cell.font = RED_FONT
        row += 1

    # Totals
    for ci in range(1, 6):
        ws5.cell(row=row, column=ci).border = THIN_BORDER
        ws5.cell(row=row, column=ci).font = Font(name="Calibri", bold=True, size=10)
    ws5.cell(row=row, column=1, value="TOTAL")
    ws5.cell(row=row, column=2, value=t_noi).number_format = CURRENCY_FMT
    ws5.cell(row=row, column=3, value=ads * hold_years).number_format = CURRENCY_FMT
    ws5.cell(row=row, column=4, value=t_fcf).number_format = CURRENCY_FMT

    # Debt Constant Reference Grid
    row += 2
    ref_rates = [3.0, 4.0, 5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0]
    ref_amorts = [15, 20, 25, 30]

    row = _section_header(ws5, row, "Debt Constant Reference (Rate × Amortization)", 1 + len(ref_amorts))
    ws5.cell(row=row, column=1, value="Rate ↓ / Amort →").font = HEADER_FONT
    ws5.cell(row=row, column=1).fill = HEADER_FILL
    ws5.cell(row=row, column=1).border = THIN_BORDER
    for ci, am in enumerate(ref_amorts, 2):
        cell = ws5.cell(row=row, column=ci, value=f"{am} yr")
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center")
        cell.border = THIN_BORDER
    row += 1

    for rate in ref_rates:
        ws5.cell(row=row, column=1, value=f"{rate:.1f}%").border = THIN_BORDER
        ws5.cell(row=row, column=1).font = Font(name="Calibri", bold=True, size=10)
        for ci, am in enumerate(ref_amorts, 2):
            if rate > 0:
                dc = _annual_debt_service(1.0, rate / 100, am)
            else:
                dc = 0
            cell = ws5.cell(row=row, column=ci, value=dc)
            cell.number_format = PERCENT_FMT
            cell.border = THIN_BORDER
            cell.alignment = Alignment(horizontal="center")
            # Highlight current selection
            if abs(rate - interest_rate * 100) < 0.2 and am == amort_years:
                cell.fill = PatternFill(start_color="DBEAFE", end_color="DBEAFE", fill_type="solid")
                cell.font = Font(name="Calibri", bold=True, size=10, color="1E40AF")
        row += 1

    # ══════════════════════════════════════════
    # Sheet 6: Rent Roll
    # ══════════════════════════════════════════
    if data.rent_roll:
        ws6 = wb.create_sheet("Rent Roll")
        rr_headers = ["Unit", "Tenant", "SF", "Rent PSF", "Annual Rent", "Monthly Rent", "Lease End"]
        rr_keys = ["unit", "tenant", "sf", "rent_psf", "annual_rent", "monthly_rent", "expiry"]
        col_widths6 = [14, 30, 12, 12, 16, 16, 14]

        for i, w in enumerate(col_widths6):
            ws6.column_dimensions[chr(65 + i)].width = w

        for ci, h in enumerate(rr_headers, 1):
            cell = ws6.cell(row=1, column=ci, value=h)
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL
            cell.alignment = Alignment(horizontal="center")
            cell.border = THIN_BORDER

        for ri, entry in enumerate(data.rent_roll, 2):
            for ci, key in enumerate(rr_keys, 1):
                val = entry.get(key, "")
                # Fallback for lease_end / expiry naming
                if key == "expiry" and not val:
                    val = entry.get("lease_end", "")
                if key == "monthly_rent" and not val:
                    annual = entry.get("annual_rent", 0) or 0
                    val = annual / 12 if annual > 0 else 0
                cell = ws6.cell(row=ri, column=ci, value=val)
                cell.border = THIN_BORDER
                if key == "sf":
                    cell.number_format = NUMBER_FMT
                elif key == "rent_psf":
                    cell.number_format = CURRENCY_CENTS_FMT
                elif key in ("annual_rent", "monthly_rent"):
                    cell.number_format = CURRENCY_FMT

        # Summary row
        total_row = len(data.rent_roll) + 2
        ws6.cell(row=total_row, column=1, value="TOTAL").font = Font(name="Calibri", bold=True, size=10)
        ws6.cell(row=total_row, column=1).border = THIN_BORDER

        total_sf = sum(e.get("sf", 0) or 0 for e in data.rent_roll)
        total_annual = sum(e.get("annual_rent", 0) or 0 for e in data.rent_roll)
        total_monthly = sum((e.get("monthly_rent") or (e.get("annual_rent", 0) or 0) / 12) for e in data.rent_roll)
        wa_rent = total_annual / total_sf if total_sf > 0 else 0

        ws6.cell(row=total_row, column=3, value=total_sf).number_format = NUMBER_FMT
        ws6.cell(row=total_row, column=3).font = Font(name="Calibri", bold=True)
        ws6.cell(row=total_row, column=3).border = THIN_BORDER
        ws6.cell(row=total_row, column=4, value=wa_rent).number_format = CURRENCY_CENTS_FMT
        ws6.cell(row=total_row, column=4).font = Font(name="Calibri", bold=True)
        ws6.cell(row=total_row, column=4).border = THIN_BORDER
        ws6.cell(row=total_row, column=5, value=total_annual).number_format = CURRENCY_FMT
        ws6.cell(row=total_row, column=5).font = Font(name="Calibri", bold=True)
        ws6.cell(row=total_row, column=5).border = THIN_BORDER
        ws6.cell(row=total_row, column=6, value=total_monthly).number_format = CURRENCY_FMT
        ws6.cell(row=total_row, column=6).font = Font(name="Calibri", bold=True)
        ws6.cell(row=total_row, column=6).border = THIN_BORDER

        # Occupancy summary
        occupied_sf = sum(e.get("sf", 0) or 0 for e in data.rent_roll if (e.get("tenant", "") or "").lower() != "vacant" and (e.get("annual_rent", 0) or 0) > 0)
        occ_pct = occupied_sf / total_sf if total_sf > 0 else 0

        sr = total_row + 2
        ws6.cell(row=sr, column=1, value="Occupied SF").font = LABEL_FONT
        ws6.cell(row=sr, column=2, value=occupied_sf).number_format = NUMBER_FMT
        ws6.cell(row=sr + 1, column=1, value="Vacant SF").font = LABEL_FONT
        ws6.cell(row=sr + 1, column=2, value=total_sf - occupied_sf).number_format = NUMBER_FMT
        ws6.cell(row=sr + 2, column=1, value="Occupancy Rate").font = LABEL_FONT
        ws6.cell(row=sr + 2, column=2, value=occ_pct).number_format = PERCENT_FMT
        ws6.cell(row=sr + 3, column=1, value="Weighted Avg Rent/SF").font = LABEL_FONT
        ws6.cell(row=sr + 3, column=2, value=wa_rent).number_format = CURRENCY_CENTS_FMT

    # ── Write to buffer ──
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    # Sanitize filename for HTTP headers (latin-1 safe)
    safe_name = data.property_name.replace(" ", "_").replace("/", "-")
    safe_name = safe_name.encode("ascii", "ignore").decode("ascii")[:40]
    filename = f"{safe_name}_Analysis.xlsx"

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
