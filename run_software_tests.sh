#!/bin/bash
# Run only tests that don't require hardware (can run in CI/CD)

echo "===================================="
echo "Running Software Tests (No Hardware)"
echo "===================================="

robot --outputdir tests/reports \
      --exclude hardware \
      --exclude TODO \
      --loglevel INFO \
      --name "SignalSight Software Tests" \
      tests/

echo ""
echo "===================================="
echo "Software test execution complete!"
echo "View reports:"
echo "  - tests/reports/report.html"
echo "  - tests/reports/log.html"
echo "===================================="
