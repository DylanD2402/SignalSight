import time
import serial
import cv2
from collections import deque
from ultralytics import YOLO
from picamera2 import Picamera2

# -----------------------------
# CONFIGURATION
# -----------------------------

MODEL_PATH = "best.pt"

SERIAL_PORT = "/dev/ttyACM0"   # Arduino on Pi
BAUD_RATE = 9600

CONF_THRESHOLD = 0.5
MAX_MISSED_FRAMES = 3

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
# MAIN FUNCTION
# -----------------------------

def live_traffic_light_detection():
    # Load YOLO model
    model = YOLO(MODEL_PATH)

    # -----------------------------
    # Pi Camera setup
    # -----------------------------
    picam2 = Picamera2()
    picam2.configure(
        picam2.create_preview_configuration(
            main={"format": "RGB888", "size": (640, 480)}
        )
    )
    picam2.start()
    time.sleep(1)

    # -----------------------------
    # Arduino serial
    # -----------------------------
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    time.sleep(2)

    fps_times = deque(maxlen=30)
    prev_time = time.time()

    current_state = "IDLE"
    missed_frames = 0

    print("Raspberry Pi CNN -> Arduino traffic light system started")

    while True:
        # Capture frame
        frame = picam2.capture_array()

        # FPS
        current_time = time.time()
        fps_times.append(1.0 / (current_time - prev_time))
        prev_time = current_time
        avg_fps = sum(fps_times) / len(fps_times)

        # YOLO inference
        results = model.predict(frame, conf=CONF_THRESHOLD, verbose=False)

        detected = []  # (class, confidence)

        for result in results:
            boxes = result.boxes.xyxy.cpu().numpy()
            scores = result.boxes.conf.cpu().numpy()
            class_ids = result.boxes.cls.cpu().numpy()

            for box, score, cls_id in zip(boxes, scores, class_ids):
                class_name = model.names[int(cls_id)]

                if class_name in CLASS_TO_ARDUINO:
                    detected.append((class_name, score))

                xmin, ymin, xmax, ymax = map(int, box)
                label = f"{class_name} {score:.2f}"

                cv2.rectangle(frame, (xmin, ymin), (xmax, ymax), (0, 255, 0), 2)
                cv2.putText(frame, label, (xmin, ymin - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        # -----------------------------
        # STATE MACHINE (NO STABILITY)
        # -----------------------------
        if detected:
            missed_frames = 0

            detected_class = max(
                detected,
                key=lambda x: (CLASS_PRIORITY[x[0]], x[1])
            )[0]

            new_state = CLASS_TO_ARDUINO[detected_class]

        else:
            missed_frames += 1
            new_state = "IDLE" if missed_frames >= MAX_MISSED_FRAMES else current_state

        # Send to Arduino on change
        if new_state != current_state:
            current_state = new_state
            ser.write((current_state + "\n").encode())
            print(f"Sent to Arduino: {current_state}")

        # Debug display (optional – disable for headless)
        cv2.putText(frame, f"FPS: {avg_fps:.2f}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        cv2.putText(frame, f"STATE: {current_state}", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)

        cv2.imshow("Pi Traffic Light Detection", frame)
        if cv2.waitKey(1) & 0xFF == 27:
            break

    ser.close()
    picam2.stop()
    cv2.destroyAllWindows()

# -----------------------------
# RUN
# -----------------------------
live_traffic_light_detection()
