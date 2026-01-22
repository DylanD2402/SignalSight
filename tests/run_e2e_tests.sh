#!/bin/bash
# Run only end-to-end tests

echo "===================================="
echo "Running End-to-End Tests"
echo "===================================="

robot --outputdir tests/reports \
      --include e2e \
      --exclude TODO \
      --loglevel INFO \
      --name "SignalSight E2E Tests" \
      tests/e2e/

echo ""
echo "===================================="
echo "E2E test execution complete!"
echo "View reports:"
echo "  - tests/reports/report.html"
echo "  - tests/reports/log.html"
echo "===================================="
