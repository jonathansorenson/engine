# CRE Deal Underwriting Tool - Backend

A production-grade FastAPI backend for commercial real estate deal analysis with AI-powered insights.

## Features

- **Document Parsing**: Extracts deal information from PDFs and Excel files
- **Intelligent Parsing**: Uses regex patterns and AI to extract key financial metrics
- **AI Analysis**: Claude-powered chat interface for deal underwriting
- **Deal Management**: Full CRUD operations for deals
- **Multi-tenant Support**: Fund-scoped data isolation
- **Chat History**: Persistent conversation history for each deal
- **SSE Streaming**: Real-time streaming responses from Claude

## Architecture

```
app/
├── __init__.py
├── config.py              # Pydantic settings
├── database.py            # SQLAlchemy setup
├── main.py                # FastAPI app entry point
├── models/
│   ├── base.py           # Base model with common fields
│   ├── deal.py           # Deal model
│   └── chat_message.py   # Chat message model
├── schemas/
│   ├── deal.py           # Deal schemas
│   └── chat.py           # Chat schemas
├── auth/
│   ├── utils.py          # JWT utilities
│   └── middleware.py     # Fund ID extraction middleware
├── services/
│   ├── pipeline.py       # OM parsing pipeline
│   └── claude_ai.py      # Claude AI integration
└── routes/
    ├── deals.py          # Deal endpoints
    └── chat.py           # Chat endpoints
```

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and update values:

```bash
cp .env.example .env
```

Key settings:
- `ANTHROPIC_API_KEY`: Your Claude API key (required for chat)
- `DATABASE_URL`: Database connection string (defaults to SQLite)
- `CORS_ORIGINS`: Comma-separated allowed origins
- `UPLOAD_DIR`: Directory for temporary file uploads

### 3. Run the Server

```bash
uvicorn app.main:app --reload
```

Server runs at `http://localhost:8000`

- API docs: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Health check: `http://localhost:8000/health`

## API Endpoints

### Deals

#### POST `/api/v1/deals`
Upload and parse a deal document.

**Request**: Multipart form with optional `pdf_file` and `excel_file`
**Response**: Deal with parsed data and assumptions

```bash
curl -F "pdf_file=@deal.pdf" http://localhost:8000/api/v1/deals
```

#### GET `/api/v1/deals`
List all deals for the fund.

**Query Parameters**:
- `skip`: Offset (default: 0)
- `limit`: Limit (default: 50)

```bash
curl http://localhost:8000/api/v1/deals
```

#### GET `/api/v1/deals/{deal_id}`
Get full deal details.

```bash
curl http://localhost:8000/api/v1/deals/550e8400-e29b-41d4-a716-446655440000
```

#### PUT `/api/v1/deals/{deal_id}/assumptions`
Update deal assumptions.

**Request Body**:
```json
{
  "exit_cap_rate": 4.5,
  "noi_growth": 2.5,
  "hold_period": 5,
  "ltv": 60.0,
  "interest_rate": 5.5,
  "amortization_years": 25
}
```

```bash
curl -X PUT -H "Content-Type: application/json" \
  -d '{"exit_cap_rate": 4.5}' \
  http://localhost:8000/api/v1/deals/550e8400-e29b-41d4-a716-446655440000/assumptions
```

#### DELETE `/api/v1/deals/{deal_id}`
Soft delete a deal.

```bash
curl -X DELETE http://localhost:8000/api/v1/deals/550e8400-e29b-41d4-a716-446655440000
```

### Chat

#### POST `/api/v1/deals/{deal_id}/chat`
Stream chat response for a deal (Server-Sent Events).

**Request Body**:
```json
{
  "message": "What is the risk profile of this deal?"
}
```

**Response**: SSE stream

```bash
curl -H "Content-Type: application/json" \
  -d '{"message": "Analyze the rent roll"}' \
  http://localhost:8000/api/v1/deals/550e8400-e29b-41d4-a716-446655440000/chat
```

#### GET `/api/v1/deals/{deal_id}/chat`
Get chat history for a deal.

**Query Parameters**:
- `skip`: Offset (default: 0)
- `limit`: Limit (default: 100)

```bash
curl http://localhost:8000/api/v1/deals/550e8400-e29b-41d4-a716-446655440000/chat
```

## Authentication

The backend uses JWT-based authentication. By default, if no authorization header is provided, requests are scoped to `lost-tree-default` fund.

**With JWT**:
```bash
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" http://localhost:8000/api/v1/deals
```

The JWT payload should include a `fund_id` claim:
```json
{
  "fund_id": "your-fund-id",
  "exp": 1234567890
}
```

## Document Parsing

The pipeline automatically extracts:

**From PDF**:
- Property name, address, city, state
- Property type and year built
- Total square footage
- Asking price
- Cap rate, NOI, annual revenue
- Operating expenses, vacancy rate

**From Excel**:
- Rent roll with units, tenants, square footage
- Annual rent and rent per SF
- Lease dates and types
- Unit status

## Data Models

### Deal

```python
{
  "id": "uuid",
  "fund_id": "string",
  "name": "property name",
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
    "assumptions": {
      "exit_cap_rate": "float",
      "noi_growth": "float",
      "hold_period": "int",
      "ltv": "float",
      "interest_rate": "float",
      "amortization_years": "int"
    },
    "raw_text": "full extracted text"
  },
  "parsing_report": {
    "errors": ["string"],
    "warnings": ["string"],
    "quality_score": "float (0-100)"
  },
  "assumptions": {...},
  "original_filename": "string",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### ChatMessage

```python
{
  "id": "uuid",
  "deal_id": "uuid",
  "fund_id": "string",
  "role": "user|assistant",
  "content": "string",
  "tokens_used": "int (nullable)",
  "created_at": "datetime"
}
```

## Database

By default, SQLite is used (`deals.db`). For production, configure PostgreSQL:

```env
DATABASE_URL=postgresql://user:password@localhost/cre_deals
```

## Docker

Build and run with Docker:

```bash
docker build -t cre-backend .
docker run -p 8000:8000 -e ANTHROPIC_API_KEY=your-key cre-backend
```

## Testing the SSE Chat Endpoint

```bash
# Create a deal first
DEAL_ID=$(curl -F "pdf_file=@sample.pdf" http://localhost:8000/api/v1/deals | jq -r '.id')

# Stream chat response
curl -H "Content-Type: application/json" \
  -d '{"message": "Analyze the deal"}' \
  http://localhost:8000/api/v1/deals/$DEAL_ID/chat
```

## Error Handling

The API returns appropriate HTTP status codes:
- `200`: Success
- `400`: Bad request (missing required fields)
- `404`: Resource not found
- `500`: Server error

All errors include a detail message explaining the issue.

## Performance Considerations

- PDF parsing is CPU-intensive; consider async file processing for large volumes
- Chat streaming uses server-sent events for real-time responses
- Database queries are indexed on `fund_id` for fast scoping
- File uploads are stored temporarily and deleted after parsing

## Development

### Project Structure

- **Models**: SQLAlchemy ORM models in `app/models/`
- **Schemas**: Pydantic validation schemas in `app/schemas/`
- **Services**: Business logic in `app/services/`
- **Routes**: API endpoints in `app/routes/`
- **Auth**: JWT and fund scoping in `app/auth/`

### Adding New Endpoints

1. Create schema in `app/schemas/`
2. Create model in `app/models/` if needed
3. Create route in `app/routes/`
4. Import and include router in `app/main.py`

## Production Deployment

Before deploying to production:

1. Update `JWT_SECRET` to a strong random value
2. Set `DATABASE_URL` to production database
3. Configure `CORS_ORIGINS` for your frontend domain
4. Set `ANTHROPIC_API_KEY` securely (use secrets manager)
5. Use production ASGI server (Gunicorn):

```bash
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app
```

6. Set up database migrations (alembic)
7. Configure logging and monitoring
8. Set up automated backups

## License

Proprietary
