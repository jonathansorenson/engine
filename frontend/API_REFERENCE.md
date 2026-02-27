# API Reference — CRE Deal Underwriting Tool

This document specifies all API endpoints the frontend expects from the FastAPI backend.

## Base URL
```
http://localhost:8000/api/v1
```

Configure in `index.html` (line 48):
```javascript
const API_URL = 'http://localhost:8000';
```

---

## Endpoints

### 1. GET /deals

Fetch list of all deals for the Deal List view.

**Request:**
```http
GET /api/v1/deals
```

**Response:** `200 OK`
```json
[
  {
    "id": "1",
    "property_name": "Westlake Commerce Center",
    "address": "1234 Commerce Drive, Austin, TX 78704",
    "property_type": "Industrial",
    "asking_price": 45000000,
    "noi": 2700000,
    "rentable_sf": 320000,
    "cap_rate": 0.06,
    "dscr": 1.35,
    "ltv": 0.65,
    "status": "active",
    "created_at": "2025-02-01"
  }
]
```

**Error Handling:**
- On error: Frontend returns empty array `[]`
- Shows "No deals yet" message in UI

**Frontend Code:**
```javascript
const fetchDeals = async () => {
  try {
    const res = await fetch(`${API_URL}/api/v1/deals`);
    if (!res.ok) throw new Error('Failed to fetch deals');
    return await res.json();
  } catch (error) {
    console.error('Error fetching deals:', error);
    return [];
  }
};
```

---

### 2. POST /deals

Upload and analyze new deal documents (PDF/Excel).

**Request:**
```http
POST /api/v1/deals
Content-Type: multipart/form-data

[Form data with files]
```

**Files:**
- `files`: Array of uploaded files (PDF and/or Excel)
  - Max 5 files per upload
  - Accepted types: `.pdf`, `.xlsx`, `.xls`
  - Max file size: 20MB (typical OM + financials)

**Response:** `201 Created`
```json
{
  "id": "12345",
  "property_name": "New Property Name",
  "address": "Address from document",
  "property_type": "Industrial",
  "asking_price": 50000000,
  "noi": 3000000,
  "rentable_sf": 350000,
  "cap_rate": 0.06,
  "dscr": 1.40,
  "ltv": 0.65,
  "status": "draft",
  "created_at": "2025-02-26T19:46:00Z",
  "assumptions": {
    "exit_cap_rate": 0.065,
    "noi_growth": 0.02,
    "hold_period": 5,
    "ltv": 0.65,
    "interest_rate": 0.045,
    "amortization_years": 25
  },
  "rent_roll": []
}
```

**Error Responses:**

`400 Bad Request` - Invalid file format
```json
{
  "error": "Unsupported file type. Please upload PDF or Excel files.",
  "parsing_errors": ["file.txt: Unsupported format"]
}
```

`413 Payload Too Large` - File too large
```json
{
  "error": "File exceeds maximum size of 20MB"
}
```

`500 Internal Server Error` - Parsing failed
```json
{
  "error": "Failed to parse documents",
  "details": "Could not extract structured data from files"
}
```

**Frontend Code:**
```javascript
const uploadDeal = async (files) => {
  const formData = new FormData();
  files.forEach(file => formData.append('files', file));

  const res = await fetch(`${API_URL}/api/v1/deals`, {
    method: 'POST',
    body: formData
  });

  if (!res.ok) throw new Error('Upload failed');
  return await res.json();
};
```

---

### 3. GET /deals/{dealId}

Fetch complete deal details for dashboard view.

**Request:**
```http
GET /api/v1/deals/1
```

**Response:** `200 OK`
```json
{
  "id": "1",
  "property_name": "Westlake Commerce Center",
  "address": "1234 Commerce Drive, Austin, TX 78704",
  "property_type": "Industrial",
  "asking_price": 45000000,
  "noi": 2700000,
  "rentable_sf": 320000,
  "cap_rate": 0.06,
  "dscr": 1.35,
  "ltv": 0.65,
  "status": "active",
  "created_at": "2025-02-01",
  "assumptions": {
    "exit_cap_rate": 0.065,
    "noi_growth": 0.02,
    "hold_period": 5,
    "ltv": 0.65,
    "interest_rate": 0.045,
    "amortization_years": 25
  },
  "rent_roll": [
    {
      "unit": "Suite A",
      "tenant": "Tech Logistics Inc",
      "sf": 50000,
      "rent_psf": 8.50,
      "annual_rent": 425000,
      "expiry": "2027-06-30"
    },
    {
      "unit": "Suite B",
      "tenant": "Distribution Plus",
      "sf": 80000,
      "rent_psf": 7.50,
      "annual_rent": 600000,
      "expiry": "2028-12-31"
    }
  ]
}
```

**Error Responses:**

`404 Not Found` - Deal doesn't exist
```json
{
  "error": "Deal not found",
  "deal_id": "1"
}
```

**Frontend Code:**
```javascript
const fetchDeal = async (dealId) => {
  try {
    const res = await fetch(`${API_URL}/api/v1/deals/${dealId}`);
    if (!res.ok) throw new Error('Failed to fetch deal');
    return await res.json();
  } catch (error) {
    console.error('Error fetching deal:', error);
    return null;
  }
};
```

---

### 4. POST /deals/{dealId}/chat

Send message to AI for deal insights. Response uses Server-Sent Events (SSE) for streaming.

**Request:**
```http
POST /api/v1/deals/1/chat
Content-Type: application/json

{
  "message": "What are the key risks in this deal?"
}
```

**Response:** `200 OK`
```
Content-Type: text/event-stream
Transfer-Encoding: chunked

Based on the offering memorandum, the primary risks are:

1. Tenant Concentration...
```

**Streaming Format:**
The response body is a continuous stream of plain text tokens. The frontend reads the stream byte-by-byte and displays tokens as they arrive, creating a real-time typewriter effect.

```javascript
// Pseudo-code for streaming
const reader = res.body.getReader();
const decoder = new TextDecoder();
while (true) {
  const { done, value } = await reader.read();
  if (done) break;

  const chunk = decoder.decode(value);
  updateChatMessage(assistantMessage += chunk);
}
```

**Error Responses:**

`404 Not Found` - Deal doesn't exist
```json
{
  "error": "Deal not found"
}
```

`500 Internal Server Error` - AI service failed
```json
{
  "error": "Failed to generate response",
  "details": "AI model unavailable"
}
```

**Frontend Code:**
```javascript
const handleSendMessage = async (e) => {
  const userMessage = input.trim();
  setMessages(prev => [...prev, { type: 'user', text: userMessage }]);

  const res = await fetch(`${API_URL}/api/v1/deals/${dealId}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message: userMessage })
  });

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let assistantMessage = '';

  setMessages(prev => [...prev, { type: 'assistant', text: '' }]);

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value);
    assistantMessage += chunk;

    setMessages(prev => {
      const updated = [...prev];
      updated[updated.length - 1].text = assistantMessage;
      return updated;
    });
  }
};
```

---

## Data Types

### Deal Object
```typescript
interface Deal {
  id: string;                          // Unique identifier
  property_name: string;               // e.g., "Westlake Commerce Center"
  address: string;                     // Full street address
  property_type: string;               // "Industrial", "Office", etc.
  asking_price: number;                // In dollars, e.g., 45000000
  noi: number;                         // Annual NOI, e.g., 2700000
  rentable_sf: number;                 // Total SF, e.g., 320000
  cap_rate: number;                    // Current cap rate, 0-1, e.g., 0.06
  dscr: number;                        // Debt service coverage, e.g., 1.35
  ltv: number;                         // Loan-to-value, 0-1, e.g., 0.65
  status: "active" | "draft" | "completed";
  created_at: string;                  // ISO timestamp
  assumptions: Assumptions;
  rent_roll: RentRollUnit[];
}

interface Assumptions {
  exit_cap_rate: number;               // 0.04 - 0.09
  noi_growth: number;                  // -0.05 to 0.15
  hold_period: number;                 // 1 - 15 years
  ltv: number;                         // 0 - 0.80
  interest_rate: number;               // 0.03 - 0.08
  amortization_years: number;          // Typically 25
}

interface RentRollUnit {
  unit: string;                        // e.g., "Suite A"
  tenant: string;                      // e.g., "Tech Logistics Inc"
  sf: number;                          // Square footage
  rent_psf: number;                    // Annual rent per SF
  annual_rent: number;                 // Total annual rent
  expiry: string;                      // Lease expiration date (ISO) or "N/A"
}
```

---

## CORS Requirements

The frontend runs on the user's local browser or a different domain than the backend API. The backend **MUST** include CORS headers:

```python
# FastAPI backend example
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or specify: ["http://localhost:3000"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Error Handling Strategy

The frontend is defensive about API errors:

1. **Network failures**: Return empty array/null, show "loading" state
2. **Invalid responses**: Log to console, show generic error message
3. **Demo mode**: If `DEMO_MODE = true`, all API calls return mock data
4. **User-facing**: Errors are graceful; app never crashes

Example:
```javascript
try {
  const res = await fetch(...);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
} catch (error) {
  console.error('Error:', error);
  return fallbackValue;  // Empty array, null, etc.
}
```

---

## Rate Limiting (Recommended)

For production deployments, implement rate limiting on the backend:

```python
# Example: 100 requests per minute per IP
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.get("/api/v1/deals")
@limiter.limit("100/minute")
async def get_deals(request: Request):
    ...
```

---

## Authentication (Optional)

The current frontend has no authentication. For production:

1. **Bearer Token**: Add `Authorization: Bearer {token}` header
   ```javascript
   fetch(url, {
     headers: {
       'Authorization': `Bearer ${token}`,
       'Content-Type': 'application/json'
     }
   })
   ```

2. **OAuth2**: Implement login flow in frontend
3. **API Key**: Add `X-API-Key` header

---

## Testing Endpoints

### Using curl

**List deals:**
```bash
curl http://localhost:8000/api/v1/deals
```

**Get single deal:**
```bash
curl http://localhost:8000/api/v1/deals/1
```

**Upload deal:**
```bash
curl -X POST \
  -F "files=@offering_memo.pdf" \
  -F "files=@financials.xlsx" \
  http://localhost:8000/api/v1/deals
```

**Chat:**
```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the cap rate?"}' \
  http://localhost:8000/api/v1/deals/1/chat
```

### Using Python Requests

```python
import requests

BASE_URL = "http://localhost:8000/api/v1"

# List deals
response = requests.get(f"{BASE_URL}/deals")
print(response.json())

# Get deal
response = requests.get(f"{BASE_URL}/deals/1")
print(response.json())

# Upload deal
files = [
  ('files', open('offering_memo.pdf', 'rb')),
  ('files', open('financials.xlsx', 'rb'))
]
response = requests.post(f"{BASE_URL}/deals", files=files)
print(response.json())

# Chat (streaming)
response = requests.post(
  f"{BASE_URL}/deals/1/chat",
  json={"message": "What are the risks?"},
  stream=True
)
for chunk in response.iter_content(decode_unicode=True):
  print(chunk, end='')
```

---

## Response Headers

The backend should return appropriate headers:

```
Content-Type: application/json
Cache-Control: no-cache, no-store, must-revalidate
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
```

For chat endpoint:
```
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
```

---

## Deployment Checklist

- [ ] API responds to GET /api/v1/deals
- [ ] API responds to POST /api/v1/deals with FormData
- [ ] API responds to GET /api/v1/deals/{id}
- [ ] API responds to POST /api/v1/deals/{id}/chat with SSE
- [ ] CORS headers configured correctly
- [ ] Rate limiting enabled
- [ ] Error responses include meaningful error messages
- [ ] Logging configured for debugging
- [ ] Database backups scheduled
- [ ] Frontend API_URL configured correctly
- [ ] DEMO_MODE set to false in production
- [ ] SSL/TLS enabled (HTTPS)

---

## Support

For questions about API integration:
1. Check backend logs for errors
2. Test endpoints with curl/Postman
3. Review TECHNICAL_SPEC.md in frontend documentation
4. Verify network connectivity and CORS headers
