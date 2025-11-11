#!/bin/bash

# Run all Riva API tests
# This script runs all the test files in sequence

# Change to the app-backend directory
cd "$(dirname "$0")/.." || exit 1

# Check for sample WAV file
SAMPLE_WAV="tests/samples/test.wav"
if [ ! -f "$SAMPLE_WAV" ]; then
  echo "Error: Sample WAV file not found at $SAMPLE_WAV"
  echo "Please place a test.wav file in the tests/samples directory"
  exit 1
fi

# Define colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# Function to run a test and print status
run_test() {
  test_file=$1
  test_name=$2
  
  echo -e "\n${YELLOW}=======================================${NC}"
  echo -e "${YELLOW}Running test: ${test_name}${NC}"
  echo -e "${YELLOW}=======================================${NC}\n"
  
  node "$test_file" "$SAMPLE_WAV"
  
  if [ $? -eq 0 ]; then
    echo -e "\n${GREEN}✓ Test completed: ${test_name}${NC}\n"
    return 0
  else
    echo -e "\n${RED}✗ Test failed: ${test_name}${NC}\n"
    return 1
  fi
}

# Make sure the server is running
echo -e "${YELLOW}Checking if server is running...${NC}"
curl -s http://localhost:3002/api/health > /dev/null
if [ $? -ne 0 ]; then
  echo -e "${RED}Server is not running at http://localhost:3002${NC}"
  echo -e "${YELLOW}Starting server in the background...${NC}"
  node server.js &
  SERVER_PID=$!
  sleep 2
  echo -e "${GREEN}Server started with PID: ${SERVER_PID}${NC}"
else
  echo -e "${GREEN}Server is already running${NC}"
  SERVER_PID=""
fi

# Track failures
FAILURES=0

# Run tests
run_test "tests/test-asr.js" "ASR API Test"
FAILURES=$((FAILURES + $?))

run_test "tests/test-wav-file.js" "WAV File Handling Test" 
FAILURES=$((FAILURES + $?))

run_test "tests/test-streaming.js" "Streaming ASR Test"
FAILURES=$((FAILURES + $?))

run_test "tests/direct-riva-test.js" "Direct Riva Communication Test"
FAILURES=$((FAILURES + $?))

# Stop server if we started it
if [ -n "$SERVER_PID" ]; then
  echo -e "${YELLOW}Stopping server with PID: ${SERVER_PID}${NC}"
  kill $SERVER_PID
  echo -e "${GREEN}Server stopped${NC}"
fi

# Display summary
echo -e "\n${YELLOW}=======================================${NC}"
echo -e "${YELLOW}Test Summary${NC}"
echo -e "${YELLOW}=======================================${NC}"

if [ $FAILURES -eq 0 ]; then
  echo -e "${GREEN}All tests passed successfully!${NC}"
  exit 0
else
  echo -e "${RED}${FAILURES} test(s) failed${NC}"
  exit 1
fi 