import json
import re
import base64
from typing import AsyncGenerator, List, Tuple, Optional
from anthropic import Anthropic, APIError
from app.config import settings
from app.models import Deal


def _extract_json(text: str) -> dict:
    """Robustly extract JSON from Claude's response, handling markdown fences and preamble text."""
    # Strip markdown fences
    cleaned = text.replace("```json", "").replace("```", "").strip()

    # Try direct parse first
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Find the first { and last } to extract JSON object
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError:
            pass

    # Log what we got for debugging
    preview = cleaned[:200] if len(cleaned) > 200 else cleaned
    print(f"[_extract_json] Failed to parse. Preview: {preview!r}")
    raise ValueError(f"Could not extract JSON from Claude response (length={len(cleaned)})")


def build_deal_context(deal: Deal) -> str:
    """Build system prompt with deal data for Claude."""
    if not deal.parsed_data:
        return "No deal data available."

    parsed = deal.parsed_data
    context = f"""You are an expert Commercial Real Estate (CRE) analyst specializing in deal underwriting.

Deal Information:
{json.dumps(parsed, indent=2)}

Current Assumptions:
{json.dumps(deal.assumptions or {}, indent=2)}

Guidelines:
1. Analyze deals thoroughly using cap rate, NOI, price per SF, and rent roll data
2. Identify risks, opportunities, and value creation strategies
3. Use the rent roll to analyze tenant quality, lease expiration clustering, and concentration risk
4. Provide specific, quantified recommendations
5. Flag any missing or unusual data points
6. Consider market context and comparable properties when making recommendations

Be direct, analytical, and data-driven in your responses."""

    return context


def stream_chat_response(
    deal: Deal,
    user_message: str,
    conversation_history: List[Tuple[str, str]],
) -> AsyncGenerator[str, None]:
    """
    Stream chat response from Claude using the Anthropic SDK.

    Yields: Text chunks from Claude's response
    """
    if not settings.anthropic_api_key:
        yield "API Error: Anthropic API key not configured. Please set ANTHROPIC_API_KEY in environment."
        return

    try:
        client = Anthropic(api_key=settings.anthropic_api_key)
    except Exception as e:
        yield f"API Error: Failed to initialize Anthropic client: {str(e)}"
        return

    # Build system prompt
    system_prompt = build_deal_context(deal)

    # Build messages
    messages = []

    # Add conversation history
    for role, content in conversation_history:
        messages.append({"role": role, "content": content})

    # Add current user message
    messages.append({"role": "user", "content": user_message})

    try:
        # Use streaming with the Anthropic SDK
        with client.messages.stream(
            model=settings.anthropic_model,
            max_tokens=2048,
            system=system_prompt,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                yield text

    except APIError as e:
        yield f"API Error: {str(e)}"
    except Exception as e:
        yield f"Error: {str(e)}"


def extract_om_fields(file_bytes: bytes, media_type: str) -> dict:
    """
    Extract offering memorandum deal fields from a PDF or image using Claude.
    Returns a dict of extracted CRE deal fields.
    """
    client = Anthropic(api_key=settings.anthropic_api_key)

    b64 = base64.standard_b64encode(file_bytes).decode("utf-8")

    # Build the content block based on file type
    if media_type.startswith("image/"):
        file_block = {
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": b64},
        }
    else:
        file_block = {
            "type": "document",
            "source": {"type": "base64", "media_type": "application/pdf", "data": b64},
        }

    system_prompt = (
        "Extract CRE deal data from this offering memorandum. "
        "Return ONLY valid JSON with these fields (use null for unknown):\n"
        '{"name":string,"address":string,"assetType":"Office"|"Retail"|"Industrial"|"Multifamily"|"Mixed-Use",'
        '"sf":number,"purchasePrice":number,"closingCosts":number,"year1NOI":number,'
        '"vacancy":number,"rentGrowth":number,"exitCap":number,"holdPeriod":number,"notes":string}'
    )

    response = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=1500,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": [file_block, {"type": "text", "text": "Extract deal data as JSON."}],
            }
        ],
    )

    text = ""
    for block in response.content:
        if block.type == "text":
            text = block.text
            break

    # Parse the JSON from Claude's response
    return _extract_json(text)


def extract_om_financials(file_bytes: bytes, media_type: str = "application/pdf") -> dict:
    """
    Extract comprehensive financial data from an OM PDF using Claude.
    Returns revenue breakdown, operating expense line items, NOI, and metadata.
    This is the primary AI-powered financial extraction used in the main parsing pipeline.
    """
    client = Anthropic(api_key=settings.anthropic_api_key)
    b64 = base64.standard_b64encode(file_bytes).decode("utf-8")

    if media_type.startswith("image/"):
        file_block = {
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": b64},
        }
    else:
        file_block = {
            "type": "document",
            "source": {"type": "base64", "media_type": "application/pdf", "data": b64},
        }

    system_prompt = """You are an expert CRE (Commercial Real Estate) financial analyst. Extract ALL financial operating data from this Offering Memorandum.

CRITICAL INSTRUCTIONS:
1. Look for income statements, operating statements, pro formas, T12/trailing twelve month financials, and financial summaries.
2. PREFER actual/historical/T12 numbers over pro forma projections when both are available.
3. All dollar amounts must be ANNUAL totals. If you find monthly figures, multiply by 12.
4. Extract individual operating expense line items whenever possible — do NOT just give a total.
5. If the OM only shows a total operating expense number without line items, still report it as total_operating_expenses.
6. If you can find an expense ratio (OpEx/Revenue), use it to cross-check or derive total OPEX.
7. Look carefully in ALL sections — financial summaries, property descriptions, investment highlights, appendices, and tables. OMs often bury operating data in different sections.

RENT ESCALATION / GROWTH:
8. Look for annual rent escalations, bumps, contractual increases, or rent growth rates mentioned anywhere in the OM — lease abstracts, investment highlights, rent roll notes, or pro forma assumptions.
9. Common terms: "annual escalation", "rent bumps", "contractual increases", "annual increase", "step-ups", "CPI adjustment", "fixed escalation".
10. Return rent_escalation_pct as a number (e.g. 3.0 for 3%). If multiple tenants have different escalations, return the weighted average or most common rate. If not found, return null.
11. Also extract vacancy_pct (economic or physical vacancy rate) if mentioned. Return as a number (e.g. 5.0 for 5%).

EXPENSE RATIO BENCHMARKS (flag if outside these ranges):
- Multifamily: 35-55%
- Office: 35-55%
- Retail (NNN): 10-25% (low because tenants pay most expenses)
- Retail (Gross): 30-50%
- Industrial: 15-30%
- Mixed-Use: 30-50%

Return ONLY valid JSON with this exact structure (use null for fields not found, 0 for expense categories confirmed as zero):

{
  "revenue": {
    "gross_potential_rent": null,
    "vacancy_loss": null,
    "effective_gross_income": null,
    "other_income": null
  },
  "operating_expenses": {
    "management_fee": null,
    "insurance": null,
    "taxes": null,
    "repairs_maintenance": null,
    "utilities": null,
    "payroll": null,
    "general_admin": null,
    "marketing": null,
    "contract_services": null,
    "other_opex": null,
    "total_operating_expenses": null
  },
  "noi": null,
  "expense_ratio": null,
  "capex_reserves": null,
  "rent_escalation_pct": null,
  "vacancy_pct": null,
  "year_type": "actual|pro_forma|projected|budget",
  "year_label": "e.g. 2024 T12, Year 1 Pro Forma, 2023 Actual",
  "confidence": "high|medium|low",
  "notes": "Any discrepancies, assumptions made, or important context about the financials"
}"""

    extraction_model = settings.anthropic_extraction_model or settings.anthropic_model
    response = client.messages.create(
        model=extraction_model,
        max_tokens=4000,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": [
                    file_block,
                    {"type": "text", "text": "Extract all financial operating data as JSON. Focus especially on operating expenses, revenue, and NOI. Look in every section of the document."},
                ],
            }
        ],
    )

    text = ""
    for block in response.content:
        if block.type == "text":
            text = block.text
            break

    print(f"[Claude extract_om_financials] model={extraction_model} stop_reason={response.stop_reason} usage={response.usage} text_len={len(text)}")
    if not text.strip():
        print(f"[Claude extract_om_financials] WARNING: Empty response. Full content blocks: {[b.type for b in response.content]}")
        raise ValueError(f"Claude returned empty response (stop_reason={response.stop_reason})")

    return _extract_json(text)


def refine_om_financials(file_bytes: bytes, current_results: dict, issue: str, media_type: str = "application/pdf") -> dict:
    """
    Targeted refinement call to Claude when the initial extraction has issues.
    Sends the PDF again with the current results and a specific issue to resolve.
    """
    client = Anthropic(api_key=settings.anthropic_api_key)
    b64 = base64.standard_b64encode(file_bytes).decode("utf-8")

    if media_type.startswith("image/"):
        file_block = {
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": b64},
        }
    else:
        file_block = {
            "type": "document",
            "source": {"type": "base64", "media_type": "application/pdf", "data": b64},
        }

    system_prompt = f"""You are an expert CRE financial analyst. We previously extracted financial data from this OM but found an issue that needs correction.

CURRENT EXTRACTION RESULTS:
{json.dumps(current_results, indent=2)}

ISSUE TO RESOLVE:
{issue}

Re-examine the document carefully and return corrected JSON in the SAME format as the current results. Only change the fields that need correction. Use the same structure:

{{
  "revenue": {{"gross_potential_rent":null,"vacancy_loss":null,"effective_gross_income":null,"other_income":null}},
  "operating_expenses": {{"management_fee":null,"insurance":null,"taxes":null,"repairs_maintenance":null,"utilities":null,"payroll":null,"general_admin":null,"marketing":null,"contract_services":null,"other_opex":null,"total_operating_expenses":null}},
  "noi": null,
  "expense_ratio": null,
  "capex_reserves": null,
  "year_type": "actual|pro_forma|projected|budget",
  "year_label": "string",
  "confidence": "high|medium|low",
  "notes": "Explain what was corrected and why"
}}"""

    extraction_model = settings.anthropic_extraction_model or settings.anthropic_model
    response = client.messages.create(
        model=extraction_model,
        max_tokens=2000,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": [
                    file_block,
                    {"type": "text", "text": f"Please re-examine the document and fix: {issue}"},
                ],
            }
        ],
    )

    text = ""
    for block in response.content:
        if block.type == "text":
            text = block.text
            break

    print(f"[Claude refine_om_financials] model={extraction_model} stop_reason={response.stop_reason} text_len={len(text)}")
    if not text.strip():
        raise ValueError(f"Claude returned empty response (stop_reason={response.stop_reason})")

    return _extract_json(text)


def extract_debt_terms(file_bytes: bytes, media_type: str) -> dict:
    """
    Extract loan/debt term sheet fields from a PDF or image using Claude.
    Returns a dict of extracted loan terms.
    """
    client = Anthropic(api_key=settings.anthropic_api_key)

    b64 = base64.standard_b64encode(file_bytes).decode("utf-8")

    if media_type.startswith("image/"):
        file_block = {
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": b64},
        }
    else:
        file_block = {
            "type": "document",
            "source": {"type": "base64", "media_type": "application/pdf", "data": b64},
        }

    system_prompt = (
        "Extract loan terms from this debt term sheet. "
        "Return ONLY valid JSON with these fields (use null for unknown):\n"
        '{"ltv":number,"rate":number,"amort":number,"ioPeriod":number,'
        '"isIO":boolean,"origFee":number,"prepayPct":number,"recourse":boolean}'
    )

    response = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=800,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": [file_block, {"type": "text", "text": "Extract loan terms as JSON."}],
            }
        ],
    )

    text = ""
    for block in response.content:
        if block.type == "text":
            text = block.text
            break

    return _extract_json(text)
