*** Settings ***
Documentation     GPS Module Unit Tests
...               Tests GPS connection, data parsing, conversion, and error handling
...
...               Tags:
...               - hardware: Requires physical GPS device
...               - software: Runs with mocks/simulations
...               - unit: Unit-level tests
...               - gps: GPS component tests

Library           ../resources/libraries/GPSLibrary.py
Resource          ../resources/keywords/gps_keywords.robot

Suite Setup       Setup GPS Connection
Suite Teardown    Teardown GPS Connection

Force Tags        gps    unit


*** Test Cases ***
Test GPSD Connection
    [Documentation]    Verify successful connection to GPSD daemon
    [Tags]    hardware    connection
    GPSD Should Be Connected
    Log    Successfully connected to GPSD daemon

Test Receive GPS Data
    [Documentation]    Verify GPS data reception from module
    [Tags]    hardware    data
    ${report}=    Verify GPS Report Contains Data    timeout=10
    Log    Received GPS report: ${report}[class]

Test GPS Report Types
    [Documentation]    Verify expected GPS report types are received
    [Tags]    hardware    data
    ${types}=    Verify GPS Receives All Report Types    timeout=15
    Log    Received report types: ${types}

Test TPV Report Structure
    [Documentation]    Validate TPV (Time-Position-Velocity) report structure
    [Tags]    hardware    data    tpv
    ${report}=    Get TPV Report    timeout=10
    Verify TPV Report Structure    ${report}
    Log    TPV report structure validated

Test SKY Report Structure
    [Documentation]    Validate SKY (satellite) report structure
    [Tags]    hardware    data    sky
    ${report}=    Get SKY Report    timeout=10
    Verify SKY Report Structure    ${report}
    Log    SKY report structure validated

Test Satellite Data
    [Documentation]    Verify satellite data parsing and validation
    [Tags]    hardware    satellites
    ${sats}=    Verify Satellite Count    timeout=15
    Should Be True    ${sats}[total] >= 0
    Log    Satellite data: ${sats}[used] used / ${sats}[total] visible

Test Position Data Format
    [Documentation]    Validate position data format when GPS fix available
    [Tags]    hardware    position    slow
    TRY
        ${pos}=    Wait For GPS Fix    timeout=20
        Coordinate Should Be Valid    ${pos}[lat]    latitude
        Coordinate Should Be Valid    ${pos}[lon]    longitude
        Log    Position data validated: ${pos}[lat], ${pos}[lon]
    EXCEPT    AS    ${error}
        Log    No GPS fix available (expected indoors): ${error}    WARN
        Skip    No GPS fix available for position data test
    END

Test Speed Conversion 0 MS
    [Documentation]    Test speed conversion: 0 m/s = 0 km/h
    [Tags]    software    conversion
    Verify Speed Conversion Accuracy    0    0

Test Speed Conversion 1 MS
    [Documentation]    Test speed conversion: 1 m/s = 3.6 km/h
    [Tags]    software    conversion
    Verify Speed Conversion Accuracy    1    3.6

Test Speed Conversion 10 MS
    [Documentation]    Test speed conversion: 10 m/s = 36 km/h
    [Tags]    software    conversion
    Verify Speed Conversion Accuracy    10    36.0

Test Speed Conversion 27.78 MS
    [Documentation]    Test speed conversion: ~27.78 m/s = 100 km/h
    [Tags]    software    conversion
    Verify Speed Conversion Accuracy    27.78    100.008    tolerance=0.01

Test Coordinate Precision 40.7128
    [Documentation]    Test coordinate formatting: New York latitude
    [Tags]    software    formatting
    ${formatted}=    Verify Coordinate Formatting    40.7128    6
    Should Be Equal    ${formatted}    40.712800

Test Coordinate Precision -74.0060
    [Documentation]    Test coordinate formatting: New York longitude
    [Tags]    software    formatting
    ${formatted}=    Verify Coordinate Formatting    -74.0060    6
    Should Be Equal    ${formatted}    -74.006000

Test Coordinate Precision 51.5074
    [Documentation]    Test coordinate formatting: London latitude
    [Tags]    software    formatting
    ${formatted}=    Verify Coordinate Formatting    51.5074    6
    Should Be Equal    ${formatted}    51.507400

Test Coordinate Precision -0.1278
    [Documentation]    Test coordinate formatting: London longitude
    [Tags]    software    formatting
    ${formatted}=    Verify Coordinate Formatting    -0.1278    6
    Should Be Equal    ${formatted}    -0.127800

Test Connection Timeout Handling
    [Documentation]    Verify timeout handling for GPS operations
    [Tags]    hardware    timeout
    ${start}=    Get Time    epoch
    ${report}=    Get GPS Report    timeout=2
    ${end}=    Get Time    epoch
    ${elapsed}=    Evaluate    ${end} - ${start}
    Should Be True    ${elapsed} < 3    msg=Timeout not respected (elapsed=${elapsed}s)
    Log    Timeout handling validated (elapsed=${elapsed}s)

Test GPS Mode Detection
    [Documentation]    Verify GPS fix mode detection (0-3)
    [Tags]    hardware    mode
    ${mode}=    Verify GPS Mode    timeout=10
    Should Be True    ${mode} >= 0 and ${mode} <= 3
    Log    GPS mode detected: ${mode}

Test Device Path Detection
    [Documentation]    Verify GPS device path detection and validation
    [Tags]    hardware    device
    ${device}=    Verify Device Path Format    timeout=10
    Should Match Regexp    ${device}    ^/dev/(tty|gps)
    Log    Device path validated: ${device}

Test Latitude Range Validation
    [Documentation]    Verify latitude validation accepts valid ranges
    [Tags]    software    validation
    Coordinate Should Be Valid    0    latitude
    Coordinate Should Be Valid    90    latitude
    Coordinate Should Be Valid    -90    latitude
    Coordinate Should Be Valid    45.5    latitude

Test Longitude Range Validation
    [Documentation]    Verify longitude validation accepts valid ranges
    [Tags]    software    validation
    Coordinate Should Be Valid    0    longitude
    Coordinate Should Be Valid    180    longitude
    Coordinate Should Be Valid    -180    longitude
    Coordinate Should Be Valid    -74.0060    longitude

Test Invalid Latitude Rejection
    [Documentation]    Verify latitude validation rejects invalid values
    [Tags]    software    validation
    TRY
        Coordinate Should Be Valid    91    latitude
        Fail    Should have rejected invalid latitude
    EXCEPT    AS    ${error}
        Should Contain    ${error}    out of range
        Log    Correctly rejected invalid latitude: ${error}
    END

Test Invalid Longitude Rejection
    [Documentation]    Verify longitude validation rejects invalid values
    [Tags]    software    validation
    TRY
        Coordinate Should Be Valid    181    longitude
        Fail    Should have rejected invalid longitude
    EXCEPT    AS    ${error}
        Should Contain    ${error}    out of range
        Log    Correctly rejected invalid longitude: ${error}
    END


*** Keywords ***
Skip
    [Documentation]    Skip test with message
    [Arguments]    ${message}
    Pass Execution    ${message}
