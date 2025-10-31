*** Settings ***
Documentation    GPS Module Keywords
...              Reusable keywords for GPS module testing
Library          ../libraries/GPSLibrary.py
Library          String
Library          Collections


*** Keywords ***
Setup GPS Connection
    [Documentation]    Establish connection to GPSD daemon
    Connect To GPSD
    GPSD Should Be Connected

Teardown GPS Connection
    [Documentation]    Clean disconnect from GPSD
    Disconnect From GPSD

Verify GPS Report Contains Data
    [Documentation]    Get GPS report and verify it contains data
    [Arguments]    ${timeout}=10
    ${report}=    Get GPS Report    timeout=${timeout}
    Should Not Be Empty    ${report}
    Report Should Have Class Field    ${report}
    RETURN    ${report}

Verify GPS Receives All Report Types
    [Documentation]    Verify GPS receives TPV and SKY reports
    [Arguments]    ${timeout}=10
    ${types}=    Get GPS Report Types    timeout=${timeout}
    Should Contain    ${types}    TPV
    Should Contain    ${types}    SKY
    RETURN    ${types}

Get TPV Report
    [Documentation]    Get TPV (Time-Position-Velocity) report
    [Arguments]    ${timeout}=10
    ${report}=    Get Report Of Type    TPV    timeout=${timeout}
    Should Not Be Equal    ${report}    ${None}
    RETURN    ${report}

Get SKY Report
    [Documentation]    Get SKY (satellite) report
    [Arguments]    ${timeout}=10
    ${report}=    Get Report Of Type    SKY    timeout=${timeout}
    Should Not Be Equal    ${report}    ${None}
    RETURN    ${report}

Verify TPV Report Structure
    [Documentation]    Verify TPV report has required fields
    [Arguments]    ${report}
    Should Be Equal    ${report}[class]    TPV
    Dictionary Should Contain Key    ${report}    device
    Dictionary Should Contain Key    ${report}    mode

Verify SKY Report Structure
    [Documentation]    Verify SKY report has required fields
    [Arguments]    ${report}
    Should Be Equal    ${report}[class]    SKY
    Dictionary Should Contain Key    ${report}    device

Verify Satellite Count
    [Documentation]    Get and verify satellite data
    [Arguments]    ${timeout}=15
    ${sats}=    Get Satellite Data    timeout=${timeout}
    Should Not Be Equal    ${sats}    ${None}
    Should Be True    ${sats}[total] >= 0
    Should Be True    ${sats}[used] >= 0
    Log    Satellites: ${sats}[used] used / ${sats}[total] total
    RETURN    ${sats}

Verify Speed Conversion Accuracy
    [Documentation]    Test speed conversion from m/s to km/h
    [Arguments]    ${speed_ms}    ${expected_kmh}    ${tolerance}=0.1
    ${calculated_kmh}=    Convert Speed MS To KMH    ${speed_ms}
    ${diff}=    Evaluate    abs(${calculated_kmh} - ${expected_kmh})
    Should Be True    ${diff} <= ${tolerance}
    Log    ${speed_ms} m/s = ${calculated_kmh} km/h (expected ${expected_kmh})

Verify Coordinate Formatting
    [Documentation]    Test coordinate formatting precision
    [Arguments]    ${coordinate}    ${decimal_places}=6
    ${formatted}=    Format Coordinate    ${coordinate}    ${decimal_places}
    ${parts}=    Split String    ${formatted}    .
    ${decimals}=    Get From List    ${parts}    1
    ${length}=    Get Length    ${decimals}
    Should Be Equal As Integers    ${length}    ${decimal_places}
    Log    Coordinate formatted: ${formatted}
    RETURN    ${formatted}

Verify GPS Mode
    [Documentation]    Get and verify GPS mode
    [Arguments]    ${timeout}=10
    ${mode}=    Get GPS Mode    timeout=${timeout}
    Should Be True    ${mode} >= 0 and ${mode} <= 3
    ${mode_desc}=    Set Variable If
    ...    ${mode} == 0    No mode value seen yet
    ...    ${mode} == 1    No fix
    ...    ${mode} == 2    2D fix (lat/lon only)
    ...    ${mode} == 3    3D fix (lat/lon/alt)
    Log    GPS Mode: ${mode} (${mode_desc})
    RETURN    ${mode}

Verify Device Path Format
    [Documentation]    Get and validate GPS device path
    [Arguments]    ${timeout}=10
    ${device}=    Get Device Path    timeout=${timeout}
    Should Not Be Equal    ${device}    ${None}
    Should Match Regexp    ${device}    ^/dev/(tty|gps)
    Log    Device path: ${device}
    RETURN    ${device}

Wait For GPS Fix
    [Documentation]    Wait for GPS to obtain position fix
    [Arguments]    ${timeout}=30
    ${pos}=    Get Position Data    timeout=${timeout}
    Should Not Be Equal    ${pos}    ${None}    msg=No GPS fix obtained within ${timeout}s
    Coordinate Should Be Valid    ${pos}[lat]    latitude
    Coordinate Should Be Valid    ${pos}[lon]    longitude
    Log    Position: ${pos}[lat], ${pos}[lon]
    RETURN    ${pos}

GPS Should Have Fix
    [Documentation]    Verify GPS has valid position fix
    [Arguments]    ${timeout}=15
    ${pos}=    Wait For GPS Fix    timeout=${timeout}
    RETURN    ${pos}

GPS Should Not Have Fix
    [Documentation]    Verify GPS does not have position fix (mode 0 or 1)
    [Arguments]    ${timeout}=10
    ${mode}=    Get GPS Mode    timeout=${timeout}
    Should Be True    ${mode} <= 1    msg=GPS unexpectedly has fix (mode=${mode})
    Log    GPS correctly has no fix (mode=${mode})
