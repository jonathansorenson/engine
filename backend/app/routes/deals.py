import os
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Deal
from app.schemas.deal import DealResponse, DealListItem, DealAssumptionsUpdate
from app.services.pipeline import parse_offering_memorandum
from app.config import settings

router = APIRouter(prefix="/api/v1/deals", tags=["deals"])


def get_upload_dir():
    """Ensure upload directory exists."""
    os.makedirs(settings.upload_dir, exist_ok=True)
    return settings.upload_dir


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
    """
    if not pdf_file and not excel_file:
        raise HTTPException(status_code=400, detail="At least one file (PDF or Excel) is required")

    fund_id = request.state.fund_id

    # Create deal record with initial status
    deal = Deal(
        id=str(uuid.uuid4()),
        fund_id=fund_id,
        status="uploading",
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
