#!/bin/bash
# Run only tests that require hardware (GPS device, Arduino, etc.)

echo "===================================="
echo "Running Hardware Tests"
echo "===================================="

robot --outputdir tests/reports \
      --include hardware \
      --loglevel INFO \
      --name "SignalSight Hardware Tests" \
      tests/

echo ""
echo "===================================="
echo "Hardware test execution complete!"
echo "View reports:"
echo "  - tests/reports/report.html"
echo "  - tests/reports/log.html"
echo "===================================="
