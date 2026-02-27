from fastapi import Request
from app.auth.utils import extract_fund_id_from_token

DEFAULT_FUND_ID = "lost-tree-default"


async def add_fund_id_to_request(request: Request, call_next):
    """Middleware to extract fund_id from JWT and add to request state."""
    fund_id = DEFAULT_FUND_ID

    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]  # Remove "Bearer " prefix
        extracted_fund_id = extract_fund_id_from_token(token)
        if extracted_fund_id:
            fund_id = extracted_fund_id

    request.state.fund_id = fund_id
    response = await call_next(request)
    return response
