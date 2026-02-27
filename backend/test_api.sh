#!/bin/bash

# CRE Deal Underwriting Tool - API Testing Script
# This script demonstrates and tests the API endpoints

BASE_URL="http://localhost:8000"
CONTENT_TYPE="Content-Type: application/json"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}CRE Deal Underwriting Tool - API Test${NC}\n"

# Check if server is running
echo -e "${YELLOW}Checking server health...${NC}"
HEALTH=$(curl -s http://localhost:8000/health)
if [ -z "$HEALTH" ]; then
    echo "Error: Server is not running. Start with: uvicorn app.main:app --reload"
    exit 1
fi
echo -e "${GREEN}Server is healthy${NC}\n"

# Test 1: Create a sample deal
echo -e "${YELLOW}Test 1: Creating a sample deal with minimal data${NC}"
echo "Creating a deal record..."

DEAL_RESPONSE=$(curl -s -F "pdf_file=@/dev/null" \
    "$BASE_URL/api/v1/deals" 2>&1)

if echo "$DEAL_RESPONSE" | grep -q "error\|Error"; then
    echo -e "${YELLOW}Note: PDF upload failed (expected - /dev/null is not a valid PDF)${NC}"
    echo "For real testing, provide an actual PDF file"
    echo ""
else
    DEAL_ID=$(echo "$DEAL_RESPONSE" | grep -o '"id":"[^"]*' | head -1 | cut -d'"' -f4)
    if [ -n "$DEAL_ID" ]; then
        echo -e "${GREEN}Deal created with ID: $DEAL_ID${NC}\n"
    fi
fi

# Test 2: List deals
echo -e "${YELLOW}Test 2: List all deals${NC}"
curl -s "$BASE_URL/api/v1/deals?limit=10&skip=0" | jq . || echo "No deals found or invalid response"
echo ""

# Test 3: Health check
echo -e "${YELLOW}Test 3: Health check endpoint${NC}"
curl -s "$BASE_URL/health" | jq .
echo ""

# Test 4: Root endpoint
echo -e "${YELLOW}Test 4: Root endpoint${NC}"
curl -s "$BASE_URL/" | jq .
echo ""

# If we have a valid deal ID, test additional endpoints
if [ -n "$DEAL_ID" ]; then
    echo -e "${YELLOW}Test 5: Get deal details (ID: $DEAL_ID)${NC}"
    curl -s "$BASE_URL/api/v1/deals/$DEAL_ID" | jq . || echo "Deal not found"
    echo ""

    echo -e "${YELLOW}Test 6: Update assumptions${NC}"
    curl -s -X PUT \
        -H "$CONTENT_TYPE" \
        -d '{
            "exit_cap_rate": 4.5,
            "noi_growth": 2.5,
            "hold_period": 7,
            "ltv": 60.0,
            "interest_rate": 5.5,
            "amortization_years": 30
        }' \
        "$BASE_URL/api/v1/deals/$DEAL_ID/assumptions" | jq . || echo "Failed to update assumptions"
    echo ""

    echo -e "${YELLOW}Test 7: Get chat history (should be empty)${NC}"
    curl -s "$BASE_URL/api/v1/deals/$DEAL_ID/chat" | jq .
    echo ""

    echo -e "${YELLOW}Test 8: Test chat endpoint (streaming - will show real-time response)${NC}"
    echo "Note: This is a Server-Sent Events (SSE) stream"
    echo "Sending: 'Analyze this deal'"
    echo ""

    TIMEOUT=5
    timeout $TIMEOUT curl -s -H "$CONTENT_TYPE" \
        -d '{"message": "Summarize the key metrics of this deal"}' \
        "$BASE_URL/api/v1/deals/$DEAL_ID/chat" || {
        EXIT_CODE=$?
        if [ $EXIT_CODE -eq 124 ]; then
            echo -e "${YELLOW}(Stream timeout after ${TIMEOUT}s - expected for SSE)${NC}"
        fi
    }
    echo ""
else
    echo -e "${YELLOW}Skipping deal-specific tests (no valid deal created)${NC}"
    echo "To test with real data:"
    echo "1. Create a test PDF file"
    echo "2. Run: curl -F 'pdf_file=@test.pdf' http://localhost:8000/api/v1/deals"
    echo "3. Use the returned deal ID in the curl commands above"
    echo ""
fi

# Test 9: Test with custom fund ID (JWT)
echo -e "${YELLOW}Test 9: Testing with custom fund ID (using default fallback)${NC}"
curl -s "$BASE_URL/api/v1/deals" | jq . || echo "Error in request"
echo ""

echo -e "${GREEN}API testing completed!${NC}"
echo ""
echo "For interactive testing, open:"
echo "  Swagger UI:  http://localhost:8000/docs"
echo "  ReDoc:       http://localhost:8000/redoc"
echo ""
echo "For real testing, try:"
echo "  curl -F 'pdf_file=@your_deal.pdf' http://localhost:8000/api/v1/deals"
