import cv2
import time
import serial
from collections import deque
from ultralytics import YOLO

# -----------------------------
# CONFIGURATION
# -----------------------------

MODEL_PATH = "best.pt"
CAMERA_INDEX = 0

SERIAL_PORT = "/dev/tty.usbmodem1101"   # CHANGE THIS
BAUD_RATE = 9600

CONF_THRESHOLD = 0.5
STABILITY_FRAMES = 5

CLASS_TO_ARDUINO = {
    "red": "ACTIVE_RED",
    "yellow": "ACTIVE_YELLOW",
    "green": "ACTIVE_GREEN"
}

CLASS_PRIORITY = {
    "red": 3,
    "yellow": 2,
    "green": 1
}

# -----------------------------
# LIVE DETECTION
# -----------------------------

def live_traffic_light_detection():
    # Load model
    model = YOLO(MODEL_PATH)

    # Open camera
    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        raise RuntimeError("Could not open camera")

    # Open serial connection
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    time.sleep(2)  # Allow Arduino to reset

    # FPS tracking
    fps_times = deque(maxlen=30)
    prev_time = time.time()

    # State machine
    current_state = "IDLE"
    last_detected_class = None
    stable_count = 0

    print("Live CNN → Arduino traffic light detection started")
    print("Press ESC to quit")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # FPS calculation
        current_time = time.time()
        fps_times.append(1.0 / (current_time - prev_time))
        prev_time = current_time
        avg_fps = sum(fps_times) / len(fps_times)

        # YOLO inference
        results = model.predict(frame, conf=CONF_THRESHOLD, verbose=False)

        detected_classes = []

        for result in results:
            boxes = result.boxes.xyxy.cpu().numpy()
            scores = result.boxes.conf.cpu().numpy()
            class_ids = result.boxes.cls.cpu().numpy()

            for box, score, cls_id in zip(boxes, scores, class_ids):
                class_name = model.names[int(cls_id)]

                if class_name in CLASS_TO_ARDUINO:
                    detected_classes.append(class_name)

                xmin, ymin, xmax, ymax = map(int, box)
                label = f"{class_name} {score:.2f}"

                cv2.rectangle(frame, (xmin, ymin), (xmax, ymax), (0, 255, 0), 2)
                cv2.putText(frame, label, (xmin, ymin - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        # State machine
        if detected_classes:
            detected_class = max(detected_classes, key=lambda c: CLASS_PRIORITY[c])

            if detected_class == last_detected_class:
                stable_count += 1
            else:
                stable_count = 1
                last_detected_class = detected_class

            new_state = (
                CLASS_TO_ARDUINO[detected_class]
                if stable_count >= STABILITY_FRAMES
                else current_state
            )
        else:
            stable_count = 0
            last_detected_class = None
            new_state = "IDLE"

        # Send to Arduino ONLY on change
        if new_state != current_state:
            current_state = new_state
            ser.write((current_state + "\n").encode())
            print(f"Sent to Arduino → {current_state}")

        # Display overlays
        cv2.putText(frame, f"FPS: {avg_fps:.2f}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        cv2.putText(frame, f"STATE: {current_state}", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)

        cv2.imshow("Live Traffic Light Detection (CNN)", frame)

        if cv2.waitKey(1) & 0xFF == 27:
            break

    ser.close()
    cap.release()
    cv2.destroyAllWindows()

# -----------------------------
# RUN
# -----------------------------

live_traffic_light_detection()
