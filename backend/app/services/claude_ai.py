import json
import base64
from typing import AsyncGenerator, List, Tuple, Optional
from anthropic import Anthropic, APIError
from app.config import settings
from app.models import Deal


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
    cleaned = text.replace("```json", "").replace("```", "").strip()
    return json.loads(cleaned)


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

    cleaned = text.replace("```json", "").replace("```", "").strip()
    return json.loads(cleaned)
