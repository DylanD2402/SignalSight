# SignalSight Test Suite

Comprehensive Robot Framework test suite for the SignalSight AI traffic light detection system.

## Overview

This test suite uses Robot Framework to test all components of the SignalSight system across three test levels:

- **Unit Tests**: Individual component testing (GPS, YOLOv8, Arduino, Alerts)
- **Integration Tests**: Component interaction testing (GPS+GPSD, Detection pipeline, System integration)
- **E2E Tests**: Full system scenario testing (Traffic detection, Driver alerts)

## Directory Structure

```
tests/
├── unit/                      # Unit-level tests
│   ├── gps_unit_tests.robot          # GPS module unit tests (26 tests)
│   ├── yolov8_unit_tests.robot       # YOLOv8 detection tests (TODO)
│   ├── arduino_unit_tests.robot      # Arduino communication tests (TODO)
│   └── alert_unit_tests.robot        # Alert system tests (TODO)
├── integration/               # Integration-level tests
│   ├── gps_integration_tests.robot   # GPS+GPSD integration (14 tests)
│   ├── detection_integration_tests.robot  # YOLOv8+HSV integration (TODO)
│   └── system_integration_tests.robot     # Cross-component tests (TODO)
├── e2e/                       # End-to-end tests
│   ├── traffic_detection_e2e.robot   # Traffic detection scenarios (TODO)
│   └── driver_alert_e2e.robot        # Driver alert scenarios (TODO)
├── resources/                 # Shared test resources
│   ├── libraries/
│   │   ├── GPSLibrary.py             # GPS test library (20+ keywords)
│   │   └── __init__.py
│   └── keywords/
│       └── gps_keywords.robot        # Reusable GPS keywords
└── reports/                   # Test execution reports (generated)
```

## Prerequisites

Install Robot Framework and dependencies:

```bash
pip3 install robotframework robotframework-seriallibrary robotframework-requests pyyaml
```

For GPS tests, ensure GPSD is installed and configured:

```bash
sudo apt-get install gpsd gpsd-clients
```

## Running Tests

### Quick Start Scripts

Seven execution scripts are provided in the project root:

```bash
# Run all tests
./run_all_tests.sh

# Run tests by category
./run_unit_tests.sh           # Unit tests only
./run_integration_tests.sh    # Integration tests only
./run_e2e_tests.sh            # E2E tests only

# Run tests by hardware requirement
./run_hardware_tests.sh       # Tests requiring hardware (GPS, Arduino)
./run_software_tests.sh       # Tests not requiring hardware (CI/CD safe)

# Run tests by component
./run_gps_tests.sh            # GPS tests only (unit + integration)
```

### Manual Execution

Run tests manually with custom options:

```bash
# Run all tests
robot --outputdir tests/reports tests/

# Run specific test suite
robot --outputdir tests/reports tests/unit/gps_unit_tests.robot

# Run tests by tag
robot --outputdir tests/reports --include gps tests/
robot --outputdir tests/reports --include hardware tests/
robot --outputdir tests/reports --exclude TODO tests/

# Run with specific log level
robot --outputdir tests/reports --loglevel DEBUG tests/
```

## Test Tags

Tests are organized using tags for flexible execution:

### Component Tags
- `gps` - GPS module tests
- `yolov8` - YOLOv8 detection tests
- `arduino` - Arduino communication tests
- `alert` - Alert system tests

### Level Tags
- `unit` - Unit-level tests
- `integration` - Integration-level tests
- `e2e` - End-to-end system tests

### Requirement Tags
- `hardware` - Tests requiring physical hardware (GPS, Arduino)
- `software` - Tests not requiring hardware (safe for CI/CD)

### Feature Tags
- `connection` - Connection/communication tests
- `conversion` - Data conversion tests
- `position` - Position/coordinate tests
- `slow` - Tests that take longer to execute (20+ seconds)
- `TODO` - Placeholder tests not yet implemented

### Usage Examples

```bash
# Run only software tests (no hardware)
robot --outputdir tests/reports --exclude hardware --exclude TODO tests/

# Run all GPS tests
robot --outputdir tests/reports --include gps tests/

# Run only unit tests
robot --outputdir tests/reports --include unit tests/

# Run hardware integration tests
robot --outputdir tests/reports --include hardware --include integration tests/

# Run fast tests only (exclude slow tests)
robot --outputdir tests/reports --exclude slow tests/
```

## Viewing Test Reports

After test execution, reports are generated in `tests/reports/`:

- **report.html** - High-level test execution summary
- **log.html** - Detailed test execution log with keywords
- **output.xml** - Machine-readable test results

Open reports in a web browser:

```bash
firefox tests/reports/report.html
# or
chromium tests/reports/report.html
```

## GPS Tests

### GPS Unit Tests (26 test cases)

Tests GPS module functionality without external dependencies:

- Connection to GPSD daemon
- Data reception and report types
- TPV (Time-Position-Velocity) report structure
- SKY report structure and satellite data
- Position data validation
- Speed conversion (m/s to km/h)
- Coordinate formatting and validation
- Timeout handling
- GPS mode detection
- Device path verification

Tags: `gps`, `unit`, `hardware`/`software`

### GPS Integration Tests (14 test cases)

Tests GPS integration with system services:

- GPSD service status and availability
- GPSD configuration verification
- GPS device persistence (/dev/gps0)
- Data flow from GPSD to application
- Concurrent connection handling
- GPS fix acquisition time
- Satellite data updates
- Position stability over time
- Error recovery and reconnection

Tags: `gps`, `integration`, `hardware`

### Running GPS Tests

```bash
# All GPS tests (unit + integration)
./run_gps_tests.sh

# GPS unit tests only
robot --outputdir tests/reports --include gps --include unit tests/

# GPS integration tests only
robot --outputdir tests/reports --include gps --include integration tests/

# GPS software tests only (no hardware required)
robot --outputdir tests/reports --include gps --exclude hardware tests/
```

Note: Many GPS tests require a GPS module connected to `/dev/gps0` with satellite fix. Tests requiring hardware are tagged with `hardware`.

## Placeholder Test Suites

Several test suites are placeholders for future development and are tagged with `TODO`:

- **yolov8_unit_tests.robot** - YOLOv8 object detection unit tests
- **arduino_unit_tests.robot** - Arduino Uno R3 communication tests
- **alert_unit_tests.robot** - Alert system unit tests
- **detection_integration_tests.robot** - YOLOv8 + HSV color classification integration
- **system_integration_tests.robot** - Cross-component system integration
- **traffic_detection_e2e.robot** - End-to-end traffic light detection scenarios
- **driver_alert_e2e.robot** - End-to-end driver alert system scenarios

These suites contain skeleton test cases with the `TODO` tag and will be implemented as the corresponding components are developed.

To exclude placeholder tests:

```bash
robot --outputdir tests/reports --exclude TODO tests/
```

## Creating New Tests

### Adding Test Cases

1. Choose the appropriate test suite file based on component and level
2. Add test case with descriptive name
3. Apply relevant tags
4. Use existing keywords from `resources/keywords/` or create new ones
5. Document test purpose and expected behavior

Example test case:

```robot
Test GPS Connection Timeout Handling
    [Documentation]    Verify GPS library handles connection timeouts gracefully
    [Tags]    gps    unit    software    timeout
    ${status}=    Connect To GPSD With Timeout    timeout=5
    Should Be Equal    ${status}    success
```

### Creating New Keywords

Add reusable keywords to `tests/resources/keywords/*.robot`:

```robot
Wait For GPS Fix With Retry
    [Documentation]    Wait for GPS fix with automatic retry
    [Arguments]    ${timeout}=30    ${retries}=3
    FOR    ${i}    IN RANGE    ${retries}
        ${status}=    Run Keyword And Return Status    Wait For GPS Fix    timeout=${timeout}
        Return From Keyword If    ${status}
        Log    Retry ${i+1}/${retries} - GPS fix not acquired
        Sleep    5s
    END
    Fail    GPS fix not acquired after ${retries} retries
```

### Creating Python Libraries

Add new Python libraries to `tests/resources/libraries/`:

1. Create `ComponentLibrary.py` file
2. Implement keywords using Robot Framework decorator: `@keyword("Keyword Name")`
3. Import library in test suite: `Library    resources/libraries/ComponentLibrary.py`

## Continuous Integration

For CI/CD pipelines, use the software test script to run tests without hardware:

```bash
./run_software_tests.sh
```

This excludes tests tagged with `hardware` or `TODO`, making it safe for automated testing environments.

## Troubleshooting

### GPS Tests Failing

1. **GPSD not running**: `sudo systemctl start gpsd`
2. **GPS device not found**: Check `/dev/gps0` exists, run `GPS/demo/setup_gps_device.sh`
3. **No GPS fix**: Tests requiring fix need clear sky view, may take 30+ seconds
4. **Permission denied**: Add user to `dialout` group: `sudo usermod -a -G dialout $USER`

### Robot Framework Issues

1. **Module not found**: Reinstall dependencies with pip3
2. **Keyword not found**: Check library import path and keyword name spelling
3. **Test timeout**: Increase timeout in test case arguments

### Report Generation

If reports aren't generated:

1. Ensure `tests/reports/` directory exists: `mkdir -p tests/reports`
2. Check write permissions: `chmod 755 tests/reports`
3. Verify Robot Framework is installed: `robot --version`

## Additional Resources

- [Robot Framework User Guide](https://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html)
- [Robot Framework Standard Libraries](https://robotframework.org/robotframework/#standard-libraries)
- [Creating Test Libraries](https://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#creating-test-libraries)

## Contributing

When adding new tests:

1. Follow existing naming conventions
2. Apply appropriate tags
3. Document test purpose in `[Documentation]` field
4. Keep tests focused and independent
5. Use reusable keywords from `resources/keywords/`
6. Update this README if adding new test categories or scripts
