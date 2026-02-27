"""Excel export endpoint — generates .xlsx from deal data sent by frontend."""

import io
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel as PydanticBaseModel
from typing import Optional, List, Dict, Any
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side, numbers
from openpyxl.utils import get_column_letter

router = APIRouter(prefix="/api/v1/export", tags=["export"])


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


# ── Styles ──
HEADER_FONT = Font(name="Calibri", bold=True, color="FFFFFF", size=11)
HEADER_FILL = PatternFill(start_color="1E3A5F", end_color="1E3A5F", fill_type="solid")
SUBHEADER_FILL = PatternFill(start_color="E8F0FE", end_color="E8F0FE", fill_type="solid")
SUBHEADER_FONT = Font(name="Calibri", bold=True, size=11)
LABEL_FONT = Font(name="Calibri", bold=True, size=10)
VALUE_FONT = Font(name="Calibri", size=10)
CURRENCY_FMT = '#,##0'
CURRENCY_CENTS_FMT = '#,##0.00'
PERCENT_FMT = '0.00%'
NUMBER_FMT = '#,##0'
THIN_BORDER = Border(
    left=Side(style="thin", color="D0D0D0"),
    right=Side(style="thin", color="D0D0D0"),
    top=Side(style="thin", color="D0D0D0"),
    bottom=Side(style="thin", color="D0D0D0"),
)


def _style_header_row(ws, row, num_cols):
    """Apply dark header styling to a row."""
    for col in range(1, num_cols + 1):
        cell = ws.cell(row=row, column=col)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center")
        cell.border = THIN_BORDER


def _add_kv_row(ws, row, label, value, value_fmt=None):
    """Add a label-value row to a worksheet."""
    label_cell = ws.cell(row=row, column=1, value=label)
    label_cell.font = LABEL_FONT
    label_cell.border = THIN_BORDER

    val_cell = ws.cell(row=row, column=2, value=value)
    val_cell.font = VALUE_FONT
    val_cell.border = THIN_BORDER
    if value_fmt:
        val_cell.number_format = value_fmt
    return row + 1


@router.post("")
async def export_deal_to_excel(data: ExportRequest):
    """Generate formatted Excel workbook from deal data."""
    wb = Workbook()

    # ══════════════════════════════════════════
    # Sheet 1: Property Summary
    # ══════════════════════════════════════════
    ws = wb.active
    ws.title = "Property Summary"
    ws.column_dimensions["A"].width = 28
    ws.column_dimensions["B"].width = 35

    # Title
    ws.merge_cells("A1:B1")
    title_cell = ws.cell(row=1, column=1, value=data.property_name)
    title_cell.font = Font(name="Calibri", bold=True, size=14, color="1E3A5F")
    title_cell.alignment = Alignment(horizontal="left")

    row = 3
    # Property Details section
    ws.merge_cells(f"A{row}:B{row}")
    section = ws.cell(row=row, column=1, value="Property Details")
    section.font = SUBHEADER_FONT
    section.fill = SUBHEADER_FILL
    ws.cell(row=row, column=2).fill = SUBHEADER_FILL
    row += 1

    if data.address:
        row = _add_kv_row(ws, row, "Address", data.address)
    if data.property_type:
        row = _add_kv_row(ws, row, "Property Type", data.property_type)
    if data.rentable_sf:
        row = _add_kv_row(ws, row, "Rentable SF", data.rentable_sf, NUMBER_FMT)
    if data.year_built:
        row = _add_kv_row(ws, row, "Year Built", data.year_built)
    if data.occupancy_rate:
        occ = data.occupancy_rate / 100 if data.occupancy_rate > 1 else data.occupancy_rate
        row = _add_kv_row(ws, row, "Occupancy", occ, PERCENT_FMT)

    row += 1
    # Financial Summary section
    ws.merge_cells(f"A{row}:B{row}")
    section = ws.cell(row=row, column=1, value="Financial Summary")
    section.font = SUBHEADER_FONT
    section.fill = SUBHEADER_FILL
    ws.cell(row=row, column=2).fill = SUBHEADER_FILL
    row += 1

    if data.asking_price:
        row = _add_kv_row(ws, row, "Asking Price", data.asking_price, CURRENCY_FMT)
    if data.noi:
        row = _add_kv_row(ws, row, "Net Operating Income (NOI)", data.noi, CURRENCY_FMT)
    if data.cap_rate:
        cap = data.cap_rate if data.cap_rate < 1 else data.cap_rate / 100
        row = _add_kv_row(ws, row, "Cap Rate", cap, PERCENT_FMT)
    if data.asking_price and data.rentable_sf and data.rentable_sf > 0:
        row = _add_kv_row(ws, row, "Price / SF", data.asking_price / data.rentable_sf, CURRENCY_CENTS_FMT)
    if data.operating_expenses:
        row = _add_kv_row(ws, row, "Operating Expenses", data.operating_expenses, CURRENCY_FMT)
    if data.annual_revenue:
        row = _add_kv_row(ws, row, "Annual Revenue", data.annual_revenue, CURRENCY_FMT)

    # ══════════════════════════════════════════
    # Sheet 2: Assumptions & Debt Analysis
    # ══════════════════════════════════════════
    assumptions = data.assumptions or {}
    ws2 = wb.create_sheet("Debt Analysis")
    ws2.column_dimensions["A"].width = 28
    ws2.column_dimensions["B"].width = 20

    row = 1
    ws2.merge_cells("A1:B1")
    ws2.cell(row=1, column=1, value="Underwriting Assumptions").font = Font(name="Calibri", bold=True, size=14, color="1E3A5F")
    row = 3

    ltv = assumptions.get("ltv", 0.65)
    if ltv > 1:
        ltv = ltv / 100
    interest_rate = assumptions.get("interest_rate", 0.055)
    if interest_rate > 1:
        interest_rate = interest_rate / 100
    exit_cap = assumptions.get("exit_cap_rate", 0.065)
    if exit_cap > 1:
        exit_cap = exit_cap / 100
    noi_growth = assumptions.get("noi_growth", 0.02)
    if noi_growth > 1:
        noi_growth = noi_growth / 100
    hold_period = assumptions.get("hold_period", 5)
    amort_years = assumptions.get("amortization_years", 25)

    row = _add_kv_row(ws2, row, "Exit Cap Rate", exit_cap, PERCENT_FMT)
    row = _add_kv_row(ws2, row, "NOI Growth Rate", noi_growth, PERCENT_FMT)
    row = _add_kv_row(ws2, row, "Hold Period (years)", hold_period)
    row = _add_kv_row(ws2, row, "Loan-to-Value (LTV)", ltv, PERCENT_FMT)
    row = _add_kv_row(ws2, row, "Interest Rate", interest_rate, PERCENT_FMT)
    row = _add_kv_row(ws2, row, "Amortization (years)", amort_years)

    # Debt metrics
    if data.asking_price and data.noi:
        row += 1
        ws2.merge_cells(f"A{row}:B{row}")
        ws2.cell(row=row, column=1, value="Debt Metrics").font = SUBHEADER_FONT
        ws2.cell(row=row, column=1).fill = SUBHEADER_FILL
        ws2.cell(row=row, column=2).fill = SUBHEADER_FILL
        row += 1

        loan_amount = data.asking_price * ltv
        row = _add_kv_row(ws2, row, "Loan Amount", loan_amount, CURRENCY_FMT)

        if data.rentable_sf and data.rentable_sf > 0:
            row = _add_kv_row(ws2, row, "Debt / Foot", loan_amount / data.rentable_sf, CURRENCY_CENTS_FMT)

        if loan_amount > 0:
            debt_yield = data.noi / loan_amount
            row = _add_kv_row(ws2, row, "Debt Yield", debt_yield, PERCENT_FMT)

        # Annual debt service
        monthly_rate = interest_rate / 12
        n_payments = amort_years * 12
        if monthly_rate > 0:
            monthly_payment = loan_amount * (monthly_rate * (1 + monthly_rate) ** n_payments) / ((1 + monthly_rate) ** n_payments - 1)
            annual_ds = monthly_payment * 12
            row = _add_kv_row(ws2, row, "Annual Debt Service", annual_ds, CURRENCY_FMT)
            if annual_ds > 0:
                row = _add_kv_row(ws2, row, "DSCR", data.noi / annual_ds, '0.00x')

            # NOI vs Debt Service table
            row += 1
            ws2.merge_cells(f"A{row}:E{row}")
            ws2.cell(row=row, column=1, value="NOI vs Debt Service — Hold Period").font = SUBHEADER_FONT
            ws2.cell(row=row, column=1).fill = SUBHEADER_FILL
            for c in range(1, 6):
                ws2.cell(row=row, column=c).fill = SUBHEADER_FILL
            row += 1

            headers = ["Year", "NOI", "Debt Service", "Free Cash Flow", "DSCR"]
            for ci, h in enumerate(headers, 1):
                cell = ws2.cell(row=row, column=ci, value=h)
                cell.font = HEADER_FONT
                cell.fill = HEADER_FILL
                cell.alignment = Alignment(horizontal="center")
                cell.border = THIN_BORDER
            ws2.column_dimensions["C"].width = 18
            ws2.column_dimensions["D"].width = 18
            ws2.column_dimensions["E"].width = 12
            row += 1

            total_noi = 0
            total_fcf = 0
            for yr in range(1, hold_period + 1):
                yr_noi = data.noi * (1 + noi_growth) ** (yr - 1)
                fcf = yr_noi - annual_ds
                dscr = yr_noi / annual_ds if annual_ds > 0 else 0
                total_noi += yr_noi
                total_fcf += fcf

                ws2.cell(row=row, column=1, value=yr).border = THIN_BORDER
                ws2.cell(row=row, column=2, value=yr_noi).number_format = CURRENCY_FMT
                ws2.cell(row=row, column=2).border = THIN_BORDER
                ws2.cell(row=row, column=3, value=annual_ds).number_format = CURRENCY_FMT
                ws2.cell(row=row, column=3).border = THIN_BORDER
                ws2.cell(row=row, column=4, value=fcf).number_format = CURRENCY_FMT
                ws2.cell(row=row, column=4).border = THIN_BORDER
                ws2.cell(row=row, column=5, value=dscr).number_format = '0.00x'
                ws2.cell(row=row, column=5).border = THIN_BORDER
                row += 1

            # Totals
            ws2.cell(row=row, column=1, value="Total").font = LABEL_FONT
            ws2.cell(row=row, column=1).border = THIN_BORDER
            ws2.cell(row=row, column=2, value=total_noi).number_format = CURRENCY_FMT
            ws2.cell(row=row, column=2).font = LABEL_FONT
            ws2.cell(row=row, column=2).border = THIN_BORDER
            ws2.cell(row=row, column=3, value=annual_ds * hold_period).number_format = CURRENCY_FMT
            ws2.cell(row=row, column=3).font = LABEL_FONT
            ws2.cell(row=row, column=3).border = THIN_BORDER
            ws2.cell(row=row, column=4, value=total_fcf).number_format = CURRENCY_FMT
            ws2.cell(row=row, column=4).font = LABEL_FONT
            ws2.cell(row=row, column=4).border = THIN_BORDER

    # ══════════════════════════════════════════
    # Sheet 3: Rent Roll
    # ══════════════════════════════════════════
    if data.rent_roll:
        ws3 = wb.create_sheet("Rent Roll")
        headers = ["Unit", "Tenant", "SF", "Rent PSF", "Annual Rent", "Monthly Rent", "Lease End"]
        field_keys = ["unit", "tenant", "sf", "rent_psf", "annual_rent", "monthly_rent", "lease_end"]

        for ci, h in enumerate(headers, 1):
            cell = ws3.cell(row=1, column=ci, value=h)
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL
            cell.alignment = Alignment(horizontal="center")
            cell.border = THIN_BORDER

        ws3.column_dimensions["A"].width = 14
        ws3.column_dimensions["B"].width = 30
        ws3.column_dimensions["C"].width = 12
        ws3.column_dimensions["D"].width = 12
        ws3.column_dimensions["E"].width = 16
        ws3.column_dimensions["F"].width = 16
        ws3.column_dimensions["G"].width = 14

        for ri, entry in enumerate(data.rent_roll, 2):
            for ci, key in enumerate(field_keys, 1):
                val = entry.get(key, "")
                cell = ws3.cell(row=ri, column=ci, value=val)
                cell.border = THIN_BORDER
                if key == "sf":
                    cell.number_format = NUMBER_FMT
                elif key in ("rent_psf",):
                    cell.number_format = CURRENCY_CENTS_FMT
                elif key in ("annual_rent", "monthly_rent"):
                    cell.number_format = CURRENCY_FMT

        # Totals row
        total_row = len(data.rent_roll) + 2
        ws3.cell(row=total_row, column=1, value="TOTAL").font = LABEL_FONT
        ws3.cell(row=total_row, column=1).border = THIN_BORDER
        total_sf = sum(e.get("sf", 0) for e in data.rent_roll)
        total_annual = sum(e.get("annual_rent", 0) for e in data.rent_roll)
        total_monthly = sum(e.get("monthly_rent", 0) or (e.get("annual_rent", 0) / 12) for e in data.rent_roll)
        ws3.cell(row=total_row, column=3, value=total_sf).number_format = NUMBER_FMT
        ws3.cell(row=total_row, column=3).font = LABEL_FONT
        ws3.cell(row=total_row, column=3).border = THIN_BORDER
        ws3.cell(row=total_row, column=5, value=total_annual).number_format = CURRENCY_FMT
        ws3.cell(row=total_row, column=5).font = LABEL_FONT
        ws3.cell(row=total_row, column=5).border = THIN_BORDER
        ws3.cell(row=total_row, column=6, value=total_monthly).number_format = CURRENCY_FMT
        ws3.cell(row=total_row, column=6).font = LABEL_FONT
        ws3.cell(row=total_row, column=6).border = THIN_BORDER

    # ── Write to buffer ──
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    safe_name = data.property_name.replace(" ", "_").replace("/", "-")[:40]
    filename = f"{safe_name}_Analysis.xlsx"

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
