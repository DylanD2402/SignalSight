# SignalSight

![SignalSight](./images/SignalSight.png)

AI-powered traffic light detection system using YOLOv8 and HSV color classification. Provides real-time driver alerts via audio-visual cues based on traffic light state, distance, and speed. Built with Raspberry Pi 5 and Arduino Uno R3 to enhance driver safety and combat distracted driving.

## Features

- **Real-time Traffic Light Detection**: YOLO-based CNN model for accurate traffic light detection
- **Color Classification**: HSV-based color analysis for red, yellow, and green light states
- **GPS Integration**: Location-aware traffic light database for enhanced accuracy
- **Hardware Integration**: Arduino-based alert system for driver notifications
- **Adaptive Display**: Automatically detects display availability and runs headless when needed
- **State Machine**: Robust state management for reliable detection across varying conditions

## Hardware Requirements

- Raspberry Pi 5 (or Raspberry Pi 4)
- Raspberry Pi Camera Module
- GPS Module (optional)
- Arduino Uno R3 (optional, for alert system)
- MicroSD card (16GB+ recommended)

## Quick Installation

Run the automated setup script to install all dependencies and configure the system:

```bash
cd SignalSight
./setup.sh
```

This will:
- Install system dependencies (OpenCV, build tools, etc.)
- Set up serial port permissions
- Create a Python virtual environment
- Install all Python packages
- Configure the GPS subsystem

**Note:** After installation, you may need to log out and log back in for serial port permissions to take effect.

## Quick Start

### 1. Activate Virtual Environment

```bash
source venv/bin/activate
```

### 2. Run Traffic Light Detection

```bash
cd YOLO_Detection_Model/CNN
python CNNLivecopy3.py
```

The system will automatically:
- Detect if a display is available (runs headless if not)
- Connect to Arduino if available (runs without if not)
- Use camera for live detection

Press 'q' to quit (when display is available) or Ctrl+C for headless mode.

### 3. Run GPS System

```bash
cd GPS
python gps_system.py
```

For debug output:
```bash
python gps_system.py --debug
```

## Project Structure

```
SignalSight/
├── YOLO_Detection_Model/     # Traffic light detection models
│   ├── CNN/                  # CNN-based detection (YOLO)
│   ├── HSV/                  # HSV color-based detection
│   ├── images/               # Test images
│   ├── best.pt               # Trained YOLO model
│   └── yolov8n.pt            # Base YOLO model
├── GPS/                      # GPS and traffic light database
│   ├── setup/                # GPS setup scripts and database
│   ├── gps_system.py         # Main GPS system
│   └── traffic_light_db.py   # Traffic light database interface
├── tests/                    # Robot Framework test suite
│   ├── unit/                 # Unit tests
│   ├── integration/          # Integration tests
│   ├── e2e/                  # End-to-end tests
│   └── run_all_tests.sh      # Test runner
├── setup.sh                  # Main setup script
├── requirements.txt          # Python dependencies
├── INSTALL.md                # Detailed installation guide
└── README.md                 # This file
```

## Usage

### Traffic Light Detection

**CNN-based detection** (recommended):
```bash
cd YOLO_Detection_Model/CNN
python CNNLivecopy3.py
```

**HSV-based detection**:
```bash
cd YOLO_Detection_Model/HSV
python detection_modelv2.py
```

**Real-time state machine** (with Arduino integration):
```bash
cd YOLO_Detection_Model/HSV
python real_time_states.py
```

### Running Tests

Run all tests:
```bash
cd tests
./run_all_tests.sh
```

Run specific test suites:
```bash
./run_unit_tests.sh           # Unit tests
./run_integration_tests.sh    # Integration tests
./run_e2e_tests.sh            # End-to-end tests
./run_gps_tests.sh            # GPS-specific tests
```

Test reports are generated in `tests/reports/`.

## Development

### Activate Development Environment

```bash
source venv/bin/activate
```

### Deactivate When Done

```bash
deactivate
```

### Update Dependencies

```bash
source venv/bin/activate
pip install --upgrade -r requirements.txt
```

## Detection Methods

SignalSight uses two complementary approaches:

### 1. CNN-based Detection (YOLO)
- Uses YOLOv8 for object detection
- Detects traffic light bounding boxes
- Classifies light color using trained model
- Location: `YOLO_Detection_Model/CNN/`

### 2. HSV-based Detection
- Uses YOLO for traffic light localization
- Applies HSV color space analysis for state detection
- More robust to lighting variations
- Location: `YOLO_Detection_Model/HSV/`

## Troubleshooting

### Camera Not Working

Enable camera interface on Raspberry Pi:
```bash
sudo raspi-config
# Navigate to Interface Options > Camera > Enable
sudo reboot
```

### Serial Port Permission Denied

Add user to dialout group:
```bash
sudo usermod -a -G dialout $USER
```
**Important:** Log out and log back in for changes to take effect.

### Model Files Missing

Ensure you're in the correct directory when running detection scripts. Model files (`best.pt`, `yolov8n.pt`) should be in `YOLO_Detection_Model/`.

## License

This project is part of an academic assignment for traffic safety enhancement.
