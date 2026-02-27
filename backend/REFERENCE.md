# API Reference Card

## Quick Reference

### Base URL
```
http://localhost:8000
```

### Authentication
```bash
# Optional JWT header
Authorization: Bearer YOUR_JWT_TOKEN
```

### Content Type
```
Content-Type: application/json
Content-Type: multipart/form-data (for file uploads)
```

---

## Endpoints

### Deals

#### Upload & Parse Deal
```
POST /api/v1/deals
Content-Type: multipart/form-data

Body:
  pdf_file: [file] (optional)
  excel_file: [file] (optional)

Returns: DealResponse
Status: 200, 400, 500
```

**Example**:
```bash
curl -F "pdf_file=@deal.pdf" http://localhost:8000/api/v1/deals
```

---

#### List Deals
```
GET /api/v1/deals?skip=0&limit=50

Returns: List[DealListItem]
Status: 200
```

**Example**:
```bash
curl "http://localhost:8000/api/v1/deals?limit=20"
```

---

#### Get Deal Details
```
GET /api/v1/deals/{deal_id}

Returns: DealResponse
Status: 200, 404
```

**Example**:
```bash
curl http://localhost:8000/api/v1/deals/550e8400-e29b-41d4-a716-446655440000
```

---

#### Update Assumptions
```
PUT /api/v1/deals/{deal_id}/assumptions
Content-Type: application/json

Body: {
  "exit_cap_rate": float (optional),
  "noi_growth": float (optional),
  "hold_period": int (optional),
  "ltv": float (optional),
  "interest_rate": float (optional),
  "amortization_years": int (optional)
}

Returns: DealResponse
Status: 200, 404
```

**Example**:
```bash
curl -X PUT \
  -H "Content-Type: application/json" \
  -d '{
    "exit_cap_rate": 4.5,
    "hold_period": 7
  }' \
  http://localhost:8000/api/v1/deals/{deal_id}/assumptions
```

---

#### Delete Deal
```
DELETE /api/v1/deals/{deal_id}

Returns: {"message": "Deal deleted successfully"}
Status: 200, 404
```

**Example**:
```bash
curl -X DELETE http://localhost:8000/api/v1/deals/{deal_id}
```

---

### Chat

#### Stream Chat Response (SSE)
```
POST /api/v1/deals/{deal_id}/chat
Content-Type: application/json

Body: {
  "message": "string"
}

Returns: Server-Sent Events stream
Status: 200, 404
```

**Example**:
```bash
curl -H "Content-Type: application/json" \
  -d '{"message": "Analyze the rent roll"}' \
  http://localhost:8000/api/v1/deals/{deal_id}/chat
```

**Response Format** (SSE):
```
data: This
data:  is
data:  streaming
data:  text
data: [DONE]
```

---

#### Get Chat History
```
GET /api/v1/deals/{deal_id}/chat?skip=0&limit=100

Returns: List[ChatMessageResponse]
Status: 200, 404
```

**Example**:
```bash
curl "http://localhost:8000/api/v1/deals/{deal_id}/chat?limit=50"
```

---

### Utilities

#### Health Check
```
GET /health

Returns: {
  "status": "healthy",
  "service": "CRE Deal Underwriting Tool",
  "version": "1.0.0"
}
Status: 200
```

---

#### API Info
```
GET /

Returns: {
  "message": "CRE Deal Underwriting Tool API",
  "docs": "/docs",
  "version": "1.0.0"
}
Status: 200
```

---

## Data Models

### DealResponse
```json
{
  "id": "uuid",
  "name": "string",
  "status": "uploading|parsing|parsed|error",
  "parsed_data": {
    "property": {
      "name": "string",
      "address": "string",
      "city": "string",
      "state": "string",
      "property_type": "string",
      "total_sf": "float",
      "year_built": "int",
      "asking_price": "float"
    },
    "financials": {
      "noi": "float",
      "cap_rate": "float",
      "annual_revenue": "float",
      "operating_expenses": "float",
      "vacancy_rate": "float",
      "price_per_sf": "float"
    },
    "rent_roll": [
      {
        "unit": "string",
        "tenant": "string",
        "sf": "float",
        "annual_rent": "float",
        "rent_psf": "float",
        "lease_start": "string",
        "lease_end": "string",
        "lease_type": "string",
        "status": "string"
      }
    ],
    "assumptions": {...},
    "raw_text": "string"
  },
  "parsing_report": {
    "errors": ["string"],
    "warnings": ["string"],
    "quality_score": "float"
  },
  "assumptions": {
    "exit_cap_rate": "float",
    "noi_growth": "float",
    "hold_period": "int",
    "ltv": "float",
    "interest_rate": "float",
    "amortization_years": "int"
  },
  "original_filename": "string",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### DealListItem
```json
{
  "id": "uuid",
  "name": "string",
  "status": "string",
  "property_type": "string",
  "asking_price": "float",
  "noi": "float",
  "cap_rate": "float",
  "created_at": "datetime"
}
```

### ChatMessageResponse
```json
{
  "id": "uuid",
  "role": "user|assistant",
  "content": "string",
  "created_at": "datetime"
}
```

---

## Status Codes

| Code | Meaning |
|------|---------|
| 200 | OK - Successful request |
| 400 | Bad Request - Invalid input |
| 404 | Not Found - Resource doesn't exist |
| 500 | Server Error - Internal error |

---

## Common Queries

### Create Deal and Chat
```bash
# 1. Create deal
DEAL=$(curl -s -F "pdf_file=@deal.pdf" \
  http://localhost:8000/api/v1/deals)
DEAL_ID=$(echo $DEAL | jq -r '.id')

# 2. Stream chat
curl -H "Content-Type: application/json" \
  -d '{"message": "Analyze this deal"}' \
  http://localhost:8000/api/v1/deals/$DEAL_ID/chat

# 3. Get chat history
curl http://localhost:8000/api/v1/deals/$DEAL_ID/chat
```

### Update Multiple Assumptions
```bash
curl -X PUT \
  -H "Content-Type: application/json" \
  -d '{
    "exit_cap_rate": 4.5,
    "noi_growth": 2.5,
    "hold_period": 7,
    "ltv": 60.0,
    "interest_rate": 5.5,
    "amortization_years": 30
  }' \
  http://localhost:8000/api/v1/deals/$DEAL_ID/assumptions
```

### Paginated List
```bash
# First 20 deals
curl "http://localhost:8000/api/v1/deals?limit=20&skip=0"

# Next 20 deals
curl "http://localhost:8000/api/v1/deals?limit=20&skip=20"
```

---

## Authentication with JWT

### Create Token (Python)
```python
from app.auth.utils import create_access_token

token = create_access_token({"fund_id": "my-fund"})
print(f"Authorization: Bearer {token}")
```

### Use Token in Request
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/v1/deals
```

---

## Parsed Data Fields

### Extracted from PDF
- Property name, address, city, state
- Property type (apartment, office, retail, etc.)
- Total square footage
- Year built
- Asking price
- Cap rate (%)
- NOI
- Annual revenue
- Operating expenses
- Vacancy rate (%)

### Extracted from Excel
- Unit/suite numbers
- Tenant names
- Square footage by unit
- Annual rent
- Rent per SF
- Lease start/end dates
- Lease type
- Occupancy status

### Calculated
- Price per SF
- Exit cap rate (cap rate + 0.25%)
- NOI growth (default 3%)
- Hold period (default 5 years)
- LTV (default 65%)
- Interest rate (default 5.75%)
- Amortization years (default 25)

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| DATABASE_URL | sqlite:///./deals.db | Database connection |
| JWT_SECRET | change-me | JWT signing key |
| ANTHROPIC_API_KEY | (empty) | Claude API key (required) |
| CORS_ORIGINS | http://localhost:3000 | CORS allowed origins |
| UPLOAD_DIR | ./uploads_temp | Temp file storage |
| MAX_UPLOAD_SIZE_MB | 100 | Max file size |

---

## Troubleshooting

### Port 8000 Already in Use
```bash
uvicorn app.main:app --reload --port 8001
```

### ANTHROPIC_API_KEY Not Set
```bash
export ANTHROPIC_API_KEY=sk-ant-your-key
# or
echo "ANTHROPIC_API_KEY=sk-ant-..." >> .env
```

### PDF Not Parsing
- Ensure file is not scanned (OCR)
- Try with a different PDF
- Check pdfplumber: `pip install --upgrade pdfplumber`

### Module Not Found
```bash
pip install -r requirements.txt
```

### Database Error
```bash
# Reset database
rm deals.db
# Server will recreate on startup
```

---

## Interactive Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## Performance Tips

- Use pagination for large lists
- Cache chat history on client side
- Stream large responses instead of buffering
- Use database indexes (already set up)
- Consider async operations for bulk uploads

---

## Version
**API Version**: 1.0.0
**Last Updated**: February 26, 2026

See full documentation in README.md and QUICKSTART.md
