import os
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import Deal
from app.schemas.deal import (
    DealResponse,
    DealListItem,
    DealAssumptionsUpdate,
    V2StateUpdate,
    DealCountResponse,
)
from app.services.pipeline import parse_offering_memorandum
from app.services.argus_parser import is_argus_file, parse_argus_file
from app.config import settings

router = APIRouter(prefix="/api/v1/deals", tags=["deals"])

DEAL_LIMIT = 10


def get_upload_dir():
    """Ensure upload directory exists."""
    os.makedirs(settings.upload_dir, exist_ok=True)
    return settings.upload_dir


def _get_deal_count(db: Session, fund_id: str) -> int:
    """Get number of deals for a fund."""
    return db.query(func.count(Deal.id)).filter(Deal.fund_id == fund_id).scalar() or 0


@router.get("/count", response_model=DealCountResponse)
async def get_deal_count(
    request: Request,
    db: Session = Depends(get_db),
):
    """Get the current deal count and limit for the user's fund."""
    fund_id = request.state.fund_id
    count = _get_deal_count(db, fund_id)
    return DealCountResponse(count=count, limit=DEAL_LIMIT, can_upload=count < DEAL_LIMIT)


@router.post("", response_model=DealResponse)
async def upload_and_parse_deal(
    request: Request,
    db: Session = Depends(get_db),
    pdf_file: Optional[UploadFile] = File(None),
    excel_file: Optional[UploadFile] = File(None),
):
    """
    Upload offering memorandum (PDF and/or Excel) and parse it.

    At least one file (PDF or Excel) is required.
    Enforces a per-fund deal limit.
    """
    if not pdf_file and not excel_file:
        raise HTTPException(status_code=400, detail="At least one file (PDF or Excel) is required")

    fund_id = request.state.fund_id

    # Enforce deal limit
    count = _get_deal_count(db, fund_id)
    if count >= DEAL_LIMIT:
        raise HTTPException(
            status_code=403,
            detail=f"Deal limit reached ({DEAL_LIMIT} deals max). Delete an existing deal to upload a new one.",
        )

    # Create deal record with initial status
    deal = Deal(
        id=str(uuid.uuid4()),
        fund_id=fund_id,
        status="uploading",
        version="2",
    )
    db.add(deal)
    db.commit()
    db.refresh(deal)

    upload_dir = get_upload_dir()
    pdf_path = None
    excel_path = None

    try:
        # Save PDF file
        if pdf_file:
            pdf_filename = f"{deal.id}_{pdf_file.filename}"
            pdf_path = os.path.join(upload_dir, pdf_filename)
            with open(pdf_path, "wb") as f:
                f.write(await pdf_file.read())
            deal.original_filename = pdf_file.filename

        # Save Excel file
        if excel_file:
            excel_filename = f"{deal.id}_{excel_file.filename}"
            excel_path = os.path.join(upload_dir, excel_filename)
            with open(excel_path, "wb") as f:
                f.write(await excel_file.read())
            if not deal.original_filename:
                deal.original_filename = excel_file.filename

        # Parse the documents
        deal.status = "parsing"
        db.commit()

        # Detect ARGUS Excel exports and route to specialized parser
        if excel_path and is_argus_file(excel_path):
            parse_result = parse_argus_file(excel_path)
        else:
            parse_result = parse_offering_memorandum(pdf_path=pdf_path, excel_path=excel_path)

        # Update deal with parsed data
        deal.parsed_data = parse_result["parsed_data"]
        deal.parsing_report = parse_result["parsing_report"]
        deal.assumptions = parse_result["parsed_data"].get("assumptions", {})
        deal.name = parse_result["parsed_data"].get("property", {}).get("name", "Untitled Deal")
        deal.status = "parsed"

        db.commit()
        db.refresh(deal)

        # Clean up temp files
        if pdf_path and os.path.exists(pdf_path):
            os.remove(pdf_path)
        if excel_path and os.path.exists(excel_path):
            os.remove(excel_path)

        return DealResponse.model_validate(deal)

    except Exception as e:
        deal.status = "error"
        deal.error_message = str(e)
        db.commit()

        # Clean up files
        if pdf_path and os.path.exists(pdf_path):
            os.remove(pdf_path)
        if excel_path and os.path.exists(excel_path):
            os.remove(excel_path)

        raise HTTPException(status_code=500, detail=f"Error parsing documents: {str(e)}")


@router.get("", response_model=List[DealListItem])
async def list_deals(
    request: Request,
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 50,
):
    """List all deals for the fund."""
    fund_id = request.state.fund_id

    deals = (
        db.query(Deal)
        .filter(Deal.fund_id == fund_id)
        .order_by(Deal.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    result = []
    for deal in deals:
        item = DealListItem(
            id=str(deal.id),
            name=deal.name,
            status=deal.status,
            version=deal.version or "1",
            created_at=deal.created_at,
        )

        # Extract summary fields from parsed_data
        if deal.parsed_data:
            parsed = deal.parsed_data
            item.property_type = parsed.get("property", {}).get("property_type")
            item.asking_price = parsed.get("property", {}).get("asking_price")
            item.noi = parsed.get("financials", {}).get("noi")
            item.cap_rate = parsed.get("financials", {}).get("cap_rate")

        result.append(item)

    return result


@router.get("/{deal_id}", response_model=DealResponse)
async def get_deal(
    deal_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Get a specific deal by ID."""
    fund_id = request.state.fund_id

    deal = (
        db.query(Deal)
        .filter(Deal.id == deal_id, Deal.fund_id == fund_id)
        .first()
    )

    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    return DealResponse.model_validate(deal)


@router.put("/{deal_id}/v2-state", response_model=DealResponse)
async def save_v2_state(
    deal_id: str,
    state: V2StateUpdate,
    request: Request,
    db: Session = Depends(get_db),
):
    """Save the full V2 modeling state (assumptions, waterfall, tenants, events, capex)."""
    fund_id = request.state.fund_id

    deal = (
        db.query(Deal)
        .filter(Deal.id == deal_id, Deal.fund_id == fund_id)
        .first()
    )

    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    # Save entire V2 state as JSON
    deal.v2_state = state.model_dump(exclude_none=False)
    if not deal.version or deal.version == "1":
        deal.version = "2"

    db.commit()
    db.refresh(deal)

    return DealResponse.model_validate(deal)


@router.post("/extract-om")
async def extract_om_from_file(
    request: Request,
    file: UploadFile = File(...),
):
    """
    Extract offering memorandum fields from a PDF or image using Claude.
    Returns extracted deal data (not saved to a deal — frontend merges into state).
    """
    if not settings.anthropic_api_key:
        raise HTTPException(status_code=500, detail="Anthropic API key not configured")

    content = await file.read()
    media_type = file.content_type or "application/pdf"

    from app.services.claude_ai import extract_om_fields
    try:
        result = extract_om_fields(content, media_type)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OM extraction failed: {str(e)}")


@router.post("/extract-debt")
async def extract_debt_from_file(
    request: Request,
    file: UploadFile = File(...),
):
    """
    Extract debt/loan term sheet fields from a PDF or image using Claude.
    Returns extracted loan terms (not saved — frontend merges into state).
    """
    if not settings.anthropic_api_key:
        raise HTTPException(status_code=500, detail="Anthropic API key not configured")

    content = await file.read()
    media_type = file.content_type or "application/pdf"

    from app.services.claude_ai import extract_debt_terms
    try:
        result = extract_debt_terms(content, media_type)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Debt term extraction failed: {str(e)}")


@router.post("/{deal_id}/rent-roll", response_model=DealResponse)
async def attach_rent_roll(
    deal_id: str,
    request: Request,
    db: Session = Depends(get_db),
    excel_file: UploadFile = File(...),
):
    """
    Attach an Excel rent roll to an existing deal.
    Parses the Excel and merges the rent roll into the deal's parsed_data.
    """
    fund_id = request.state.fund_id

    deal = (
        db.query(Deal)
        .filter(Deal.id == deal_id, Deal.fund_id == fund_id)
        .first()
    )

    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    upload_dir = get_upload_dir()
    excel_path = None

    try:
        excel_filename = f"{deal.id}_rentroll_{excel_file.filename}"
        excel_path = os.path.join(upload_dir, excel_filename)
        with open(excel_path, "wb") as f:
            f.write(await excel_file.read())

        from app.services.pipeline import extract_excel_rent_roll
        rent_roll = extract_excel_rent_roll(excel_path)

        if not rent_roll:
            raise HTTPException(status_code=400, detail="No rent roll data found in the Excel file. Ensure the file has columns like Unit, Tenant, SF, Rent, Lease dates.")

        # Merge into existing parsed_data
        if not deal.parsed_data:
            deal.parsed_data = {}

        # SQLAlchemy needs a new dict reference to detect JSON changes
        updated_data = dict(deal.parsed_data)
        updated_data["rent_roll"] = rent_roll
        deal.parsed_data = updated_data

        # Update parsing report
        if not deal.parsing_report:
            deal.parsing_report = {"errors": [], "warnings": []}
        updated_report = dict(deal.parsing_report)
        updated_report.setdefault("warnings", [])
        updated_report["warnings"].append(f"Rent roll attached from: {excel_file.filename} ({len(rent_roll)} units)")
        deal.parsing_report = updated_report

        db.commit()
        db.refresh(deal)

        # Clean up
        if excel_path and os.path.exists(excel_path):
            os.remove(excel_path)

        return DealResponse.model_validate(deal)

    except HTTPException:
        raise
    except Exception as e:
        if excel_path and os.path.exists(excel_path):
            os.remove(excel_path)
        raise HTTPException(status_code=500, detail=f"Error processing rent roll: {str(e)}")


@router.post("/parse-rent-roll")
async def parse_rent_roll_v2(
    request: Request,
    excel_file: UploadFile = File(...),
):
    """
    Parse an Excel rent roll and return V2-formatted tenant data.
    Stateless — does not require a deal ID. Returns JSON array of tenants.
    """
    upload_dir = get_upload_dir()
    excel_path = None

    try:
        import uuid as _uuid
        excel_filename = f"rr_parse_{_uuid.uuid4().hex[:8]}_{excel_file.filename}"
        excel_path = os.path.join(upload_dir, excel_filename)
        with open(excel_path, "wb") as f:
            f.write(await excel_file.read())

        from app.services.pipeline import extract_excel_rent_roll
        rent_roll = extract_excel_rent_roll(excel_path)

        if not rent_roll:
            raise HTTPException(
                status_code=400,
                detail="No rent roll data found. Ensure columns like Unit/Suite, Tenant, SF, Rent, and Lease dates exist."
            )

        # Map to V2 tenant schema
        v2_tenants = []
        for i, r in enumerate(rent_roll):
            rent_psf = r.get("rent_psf") or 0
            if not rent_psf and r.get("annual_rent") and r.get("sf"):
                rent_psf = r["annual_rent"] / r["sf"]

            cam_psf = r.get("cam_psf") or 0
            if not cam_psf and r.get("cam_annual") and r.get("sf") and r["sf"] > 0:
                cam_psf = r["cam_annual"] / r["sf"]

            v2_tenants.append({
                "id": i + 1,
                "name": r.get("tenant") or r.get("name") or f"Tenant {i + 1}",
                "suite": r.get("unit") or r.get("suite") or "",
                "sf": r.get("sf") or 0,
                "rentPSF": rent_psf,
                "camPSF": cam_psf,
                "type": "NNN",
                "escalPct": 3,
                "start": r.get("lease_start") or "",
                "end": r.get("lease_end") or r.get("expiry") or "",
                "tiPSF": 0,
                "lcPct": 5,
                "recoveryRatio": 100,
            })

        return {"tenants": v2_tenants, "count": len(v2_tenants)}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error parsing rent roll: {str(e)}")
    finally:
        if excel_path and os.path.exists(excel_path):
            try:
                os.remove(excel_path)
            except Exception:
                pass


@router.put("/{deal_id}/assumptions", response_model=DealResponse)
async def update_assumptions(
    deal_id: str,
    assumptions_update: DealAssumptionsUpdate,
    request: Request,
    db: Session = Depends(get_db),
):
    """Update deal assumptions."""
    fund_id = request.state.fund_id

    deal = (
        db.query(Deal)
        .filter(Deal.id == deal_id, Deal.fund_id == fund_id)
        .first()
    )

    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    # Merge updates into existing assumptions
    if not deal.assumptions:
        deal.assumptions = {}

    for field, value in assumptions_update.model_dump(exclude_unset=True).items():
        if value is not None:
            deal.assumptions[field] = value

    db.commit()
    db.refresh(deal)

    return DealResponse.model_validate(deal)


@router.delete("/{deal_id}")
async def delete_deal(
    deal_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Permanently delete a deal."""
    fund_id = request.state.fund_id

    deal = (
        db.query(Deal)
        .filter(Deal.id == deal_id, Deal.fund_id == fund_id)
        .first()
    )

    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    db.delete(deal)
    db.commit()

    return {"message": "Deal deleted permanently"}
