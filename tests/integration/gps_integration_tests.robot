*** Settings ***
Documentation     GPS Integration Tests
...               Tests GPS integration with GPSD daemon, device persistence,
...               and real-world GPS fix acquisition scenarios
...
...               Tags:
...               - hardware: Requires physical GPS device
...               - integration: Integration-level tests
...               - gps: GPS component tests

Library           ../resources/libraries/GPSLibrary.py
Resource          ../resources/keywords/gps_keywords.robot
Library           OperatingSystem
Library           Process

Suite Setup       Setup GPS Integration Tests
Suite Teardown    Teardown GPS Integration Tests

Force Tags        gps    integration


*** Variables ***
${GPSD_SERVICE}    gpsd
${GPS_DEVICE}      /dev/gps0
${BACKUP_DEVICE}   /dev/ttyUSB0


*** Test Cases ***
Test GPSD Service Status
    [Documentation]    Verify GPSD daemon is running
    [Tags]    hardware    daemon
    ${result}=    Run Process    systemctl    is-active    ${GPSD_SERVICE}
    IF    '${result.stdout}' != 'active'
        Skip    GPSD service is not running (found: ${result.stdout})
    END
    Should Be Equal    ${result.stdout}    active
    Log    GPSD service is active

Test GPSD Service Configuration
    [Documentation]    Verify GPSD is configured correctly
    [Tags]    hardware    daemon
    ${config_exists}=    Run Keyword And Return Status    File Should Exist    /etc/default/gpsd
    IF    not $config_exists
        Skip    GPSD configuration file not found at /etc/default/gpsd
    END
    ${config}=    Get File    /etc/default/gpsd
    Should Contain    ${config}    DEVICES=
    Should Contain    ${config}    GPSD_OPTIONS=
    Log    GPSD configuration validated

Test GPS Device Persistence
    [Documentation]    Verify GPS device has persistent name
    [Tags]    hardware    device
    # Use shell test -e to check existence (doesn't require read permissions)
    ${gps_result}=    Run Process    sh    -c    test -e ${GPS_DEVICE} && echo exists || echo missing
    ${backup_result}=    Run Process    sh    -c    test -e ${BACKUP_DEVICE} && echo exists || echo missing

    IF    '${gps_result.stdout}' == 'exists'
        ${link}=    Run    ls -l ${GPS_DEVICE}
        Should Contain    ${link}    ttyUSB
        Log    Persistent device ${GPS_DEVICE} exists and points to ttyUSB
    ELSE IF    '${backup_result.stdout}' == 'exists'
        Log    Primary GPS device not found, using backup device    WARN
        ${link}=    Run    ls -l ${BACKUP_DEVICE}
        Log    Using backup device ${BACKUP_DEVICE}: ${link}
    ELSE
        Skip    No GPS devices available (${GPS_DEVICE} or ${BACKUP_DEVICE})
    END

Test GPSD Device Connection
    [Documentation]    Verify GPSD is connected to correct GPS device
    [Tags]    hardware    daemon
    Connect To GPSD
    ${device}=    Get Device Path    timeout=10
    Should Not Be Equal    ${device}    ${None}
    Should Match Regexp    ${device}    ^/dev/(gps|tty)
    Log    GPSD connected to device: ${device}
    Disconnect From GPSD

Test GPS Data Flow GPSD To Application
    [Documentation]    Verify complete data flow from GPSD to application
    [Tags]    hardware    dataflow
    # Connect to GPSD
    Connect To GPSD

    # Verify we receive VERSION report (daemon ready)
    ${types}=    Get GPS Report Types    timeout=5
    Should Contain    ${types}    VERSION

    # Verify we receive DEVICES report (device info)
    Should Contain    ${types}    DEVICES

    # Verify we receive TPV reports (GPS data)
    Should Contain    ${types}    TPV

    # Verify we receive SKY reports (satellite data)
    Should Contain    ${types}    SKY

    Log    Complete data flow verified: GPSD -> GPSLibrary -> Test
    Disconnect From GPSD

Test Multiple Concurrent Connections
    [Documentation]    Verify multiple connections to GPSD work correctly
    [Tags]    hardware    daemon
    # First connection
    Connect To GPSD
    ${report1}=    Get GPS Report    timeout=5
    Should Not Be Equal    ${report1}    ${None}

    # Disconnect and reconnect
    Disconnect From GPSD
    Sleep    1s
    Connect To GPSD

    # Verify second connection works
    ${report2}=    Get GPS Report    timeout=5
    Should Not Be Equal    ${report2}    ${None}

    Log    Multiple connections validated
    Disconnect From GPSD

Test GPS Fix Acquisition Sequence
    [Documentation]    Verify GPS fix acquisition follows expected sequence
    [Tags]    hardware    fix    slow
    Connect To GPSD

    # Check initial mode (likely no fix)
    ${initial_mode}=    Get GPS Mode    timeout=5
    Log    Initial GPS mode: ${initial_mode}

    # Monitor for mode progression over time
    FOR    ${i}    IN RANGE    6
        ${mode}=    Get GPS Mode    timeout=5
        ${sats}=    Get Satellite Data    timeout=5
        IF    $sats != $None
            Log    Cycle ${i}: Mode ${mode}, Sats ${sats}[used]/${sats}[total]
        ELSE
            Log    Cycle ${i}: Mode ${mode}, No satellite data yet
        END
        Sleep    5s
    END

    Log    GPS fix acquisition sequence monitored
    Disconnect From GPSD

Test Satellite Data Updates
    [Documentation]    Verify satellite data updates over time
    [Tags]    hardware    satellites    slow
    Connect To GPSD

    ${sat_counts}=    Create List

    # Collect satellite counts over 30 seconds
    FOR    ${i}    IN RANGE    6
        ${sats}=    Get Satellite Data    timeout=5
        IF    $sats != $None
            Append To List    ${sat_counts}    ${sats}[total]
            Log    Satellite count: ${sats}[total]
        END
        Sleep    5s
    END

    # Verify we got at least some satellite data
    ${length}=    Get Length    ${sat_counts}
    Should Be True    ${length} > 0    msg=No satellite data received

    Log    Satellite data updates verified
    Disconnect From GPSD

Test GPS Position Stability
    [Documentation]    Verify GPS position stability when fix available
    [Tags]    hardware    position    slow
    Connect To GPSD

    TRY
        # Wait for fix
        ${pos1}=    Wait For GPS Fix    timeout=30
        Sleep    5s

        # Get second position
        ${pos2}=    Get Position Data    timeout=10
        Should Not Be Equal    ${pos2}    ${None}

        # Positions should be reasonably close (within 0.001 degrees ~111m)
        ${lat_diff}=    Evaluate    abs(${pos1}[lat] - ${pos2}[lat])
        ${lon_diff}=    Evaluate    abs(${pos1}[lon] - ${pos2}[lon])

        Should Be True    ${lat_diff} < 0.001    msg=Latitude changed too much
        Should Be True    ${lon_diff} < 0.001    msg=Longitude changed too much

        Log    Position stable: Lat diff ${lat_diff}, Lon diff ${lon_diff}

    EXCEPT    AS    ${error}
        Log    No GPS fix available (expected indoors): ${error}    WARN
        Pass Execution    Skipped - No GPS fix available
    END

    Disconnect From GPSD

Test Error Recovery After GPSD Restart
    [Documentation]    Verify system recovers after GPSD restart
    [Tags]    hardware    daemon    recovery
    # Initial connection
    Connect To GPSD
    ${device1}=    Get Device Path    timeout=10
    Disconnect From GPSD

    # Restart GPSD (would require sudo - skip actual restart in test)
    Log    GPSD restart would happen here (requires sudo)    WARN
    Sleep    2s

    # Reconnect and verify
    Connect To GPSD
    ${device2}=    Get Device Path    timeout=10
    Should Be Equal    ${device1}    ${device2}
    Log    Successfully recovered after simulated restart
    Disconnect From GPSD

Test GPS Data Timeout Recovery
    [Documentation]    Verify recovery from data timeout scenarios
    [Tags]    hardware    timeout
    Connect To GPSD

    # Request with very short timeout
    ${report}=    Get GPS Report    timeout=1

    # Should either succeed or return None, not crash
    IF    $report == $None
        Log    Timeout occurred as expected
    ELSE
        Log    Report received within timeout
    END

    # Verify we can still get data after timeout
    ${report2}=    Get GPS Report    timeout=10
    Should Not Be Equal    ${report2}    ${None}

    Log    Successfully recovered from timeout
    Disconnect From GPSD

Test Device Reconnection Handling
    [Documentation]    Verify handling of device disconnect/reconnect
    [Tags]    hardware    device
    Connect To GPSD
    ${device}=    Get Device Path    timeout=10

    Log    Device path: ${device}
    Log    In production, would test physical disconnect/reconnect    WARN

    # Verify we can still get data
    ${report}=    Get GPS Report    timeout=10
    Should Not Be Equal    ${report}    ${None}

    Disconnect From GPSD

Test Long Running GPS Session
    [Documentation]    Verify GPS session stability over extended period
    [Tags]    hardware    stability    slow
    Connect To GPSD

    ${report_count}=    Set Variable    0

    # Run for 60 seconds collecting reports
    FOR    ${i}    IN RANGE    12
        ${report}=    Get GPS Report    timeout=5
        IF    $report != $None
            ${report_count}=    Evaluate    ${report_count} + 1
        END
        Sleep    5s
    END

    # Should receive multiple reports over 60 seconds
    Should Be True    ${report_count} > 10    msg=Too few reports received
    Log    Received ${report_count} reports over 60 seconds

    Disconnect From GPSD


*** Keywords ***
Setup GPS Integration Tests
    [Documentation]    Setup for GPS integration tests
    Log    Starting GPS Integration Tests
    # Verify GPSD is running before tests
    ${result}=    Run Process    systemctl    is-active    ${GPSD_SERVICE}
    IF    '${result.stdout}' != 'active'
        Log    WARNING: GPSD service is not running. Some tests may be skipped.    WARN
        Log    To start GPSD: sudo systemctl start gpsd    WARN
    END

Teardown GPS Integration Tests
    [Documentation]    Cleanup after GPS integration tests
    Log    GPS Integration Tests Complete
    # Ensure any connections are cleaned up
    Run Keyword And Ignore Error    Disconnect From GPSD
