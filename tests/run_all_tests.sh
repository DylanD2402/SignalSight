#!/bin/bash
# Run all Robot Framework tests

echo "===================================="
echo "Running All Robot Framework Tests"
echo "===================================="

robot --outputdir tests/reports \
      --loglevel INFO \
      --name "SignalSight All Tests" \
      tests/

echo ""
echo "===================================="
echo "Test execution complete!"
echo "View reports:"
echo "  - tests/reports/report.html"
echo "  - tests/reports/log.html"
echo "===================================="
