#!/bin/bash
# Run only integration-level tests

echo "===================================="
echo "Running Integration Tests"
echo "===================================="

robot --outputdir tests/reports \
      --include integration \
      --exclude TODO \
      --loglevel INFO \
      --name "SignalSight Integration Tests" \
      tests/integration/

echo ""
echo "===================================="
echo "Integration test execution complete!"
echo "View reports:"
echo "  - tests/reports/report.html"
echo "  - tests/reports/log.html"
echo "===================================="
