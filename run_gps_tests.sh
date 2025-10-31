#!/bin/bash
# Run only GPS-related tests (unit and integration)

echo "===================================="
echo "Running GPS Tests"
echo "===================================="

robot --outputdir tests/reports \
      --include gps \
      --loglevel INFO \
      --name "SignalSight GPS Tests" \
      tests/

echo ""
echo "===================================="
echo "GPS test execution complete!"
echo "View reports:"
echo "  - tests/reports/report.html"
echo "  - tests/reports/log.html"
echo "===================================="
