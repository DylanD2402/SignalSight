#!/bin/bash
# Run only unit-level tests

echo "===================================="
echo "Running Unit Tests"
echo "===================================="

robot --outputdir tests/reports \
      --include unit \
      --exclude TODO \
      --loglevel INFO \
      --name "SignalSight Unit Tests" \
      tests/unit/

echo ""
echo "===================================="
echo "Unit test execution complete!"
echo "View reports:"
echo "  - tests/reports/report.html"
echo "  - tests/reports/log.html"
echo "===================================="
