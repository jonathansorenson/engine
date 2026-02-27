# Quick Start Guide

## 1-Minute Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env

# Edit .env with your Anthropic API key
# ANTHROPIC_API_KEY=sk-ant-your-key-here

# Run the server
uvicorn app.main:app --reload
```

Server runs at: http://localhost:8000

## Interactive API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Test the API

### 1. Create a Deal (Upload & Parse)

```bash
# Upload a PDF offering memorandum
curl -F "pdf_file=@deal.pdf" \
  http://localhost:8000/api/v1/deals

# Returns deal ID and parsed data
# Save the deal ID for next steps
```

**Expected Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Property Name",
  "status": "parsed",
  "parsed_data": {...},
  "assumptions": {...},
  "created_at": "2024-01-15T10:30:00"
}
```

### 2. List Deals

```bash
curl http://localhost:8000/api/v1/deals
```

### 3. Get Deal Details

```bash
DEAL_ID="550e8400-e29b-41d4-a716-446655440000"
curl http://localhost:8000/api/v1/deals/$DEAL_ID
```

### 4. Update Assumptions

```bash
DEAL_ID="550e8400-e29b-41d4-a716-446655440000"

curl -X PUT \
  -H "Content-Type: application/json" \
  -d '{
    "exit_cap_rate": 4.5,
    "noi_growth": 2.5,
    "hold_period": 7
  }' \
  http://localhost:8000/api/v1/deals/$DEAL_ID/assumptions
```

### 5. Stream Chat Response (Server-Sent Events)

```bash
DEAL_ID="550e8400-e29b-41d4-a716-446655440000"

# Start streaming
curl -H "Content-Type: application/json" \
  -d '{"message": "Analyze the rent roll and identify tenant concentration risk"}' \
  http://localhost:8000/api/v1/deals/$DEAL_ID/chat

# Expected: Real-time text stream from Claude
```

### 6. Get Chat History

```bash
DEAL_ID="550e8400-e29b-41d4-a716-446655440000"

curl http://localhost:8000/api/v1/deals/$DEAL_ID/chat
```

## Environment Variables

```env
# Database (defaults to SQLite)
DATABASE_URL=sqlite:///./deals.db

# JWT
JWT_SECRET=change-me-in-production

# Claude API
ANTHROPIC_API_KEY=sk-ant-your-key-here

# CORS
CORS_ORIGINS=http://localhost:3000

# File uploads
UPLOAD_DIR=./uploads_temp
MAX_UPLOAD_SIZE_MB=100
```

## What Gets Parsed from PDF

The pipeline automatically extracts:
- **Property**: name, address, city, state, type, SF, year built, asking price
- **Financials**: cap rate, NOI, revenue, operating expenses, vacancy
- **Assumptions**: calculated with smart defaults

## What Gets Parsed from Excel

The pipeline looks for rent roll data with fuzzy matching:
- Unit/suite numbers
- Tenant names
- Square footage
- Annual rent and rent per SF
- Lease dates and types
- Occupancy status

## Docker

```bash
# Build
docker build -t cre-backend .

# Run (set ANTHROPIC_API_KEY)
docker run -p 8000:8000 \
  -e ANTHROPIC_API_KEY=sk-ant-your-key-here \
  cre-backend
```

## Database

### Default (SQLite)
Works out of the box, no setup needed.

### PostgreSQL
```env
DATABASE_URL=postgresql://user:password@localhost:5432/cre_deals
```

## Authentication (Optional)

By default, all requests are scoped to fund `lost-tree-default`.

To use custom fund IDs, pass a JWT:
```bash
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  http://localhost:8000/api/v1/deals
```

JWT payload should include:
```json
{
  "fund_id": "your-fund-id",
  "exp": 1234567890
}
```

Create tokens using `/app/auth/utils.py`:
```python
from app.auth.utils import create_access_token

token = create_access_token({"fund_id": "your-fund-id"})
```

## Troubleshooting

### Module not found errors
```bash
# Make sure you're in the project directory
cd /path/to/backend

# Install dependencies
pip install -r requirements.txt
```

### API key not configured
Set `ANTHROPIC_API_KEY` in `.env` before running:
```bash
echo "ANTHROPIC_API_KEY=sk-ant-your-key-here" >> .env
```

### PDF parsing issues
- Ensure pdfplumber is installed: `pip install pdfplumber`
- Test with a text-based PDF (scanned PDFs may not parse well)

### Port already in use
Use a different port:
```bash
uvicorn app.main:app --reload --port 8001
```

## Example Data

Test with sample files:

### Sample PDF structure (for testing)
A simple PDF with:
- Property name: "Downtown Office Tower"
- Address: "123 Main St, Denver, CO"
- Cap rate: 4.5%
- NOI: $2,500,000
- Asking price: $55,000,000

### Sample Excel structure (for testing)
A spreadsheet with columns:
- Unit | Tenant | SF | Annual Rent | Lease Type | Status

## Next Steps

1. Read the full [README.md](README.md) for detailed documentation
2. Check [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) for technical details
3. Review the Swagger UI for interactive API exploration
4. Test with your own deal documents

## Support

- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health
- See README.md for troubleshooting and deployment
