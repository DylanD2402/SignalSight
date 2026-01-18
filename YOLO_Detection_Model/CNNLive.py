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

SERIAL_PORT = "/dev/tty.usbmodem1101"
BAUD_RATE = 9600

CONF_THRESHOLD = 0.5
MAX_MISSED_FRAMES = 3   # tolerate CNN flicker

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
    model = YOLO(MODEL_PATH)

    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        raise RuntimeError("Could not open camera")

    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    time.sleep(2)

    fps_times = deque(maxlen=30)
    prev_time = time.time()

    current_state = "IDLE"
    last_detected_class = None
    missed_frames = 0

    print("Live CNN → Arduino traffic light detection started")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # FPS
        current_time = time.time()
        fps_times.append(1.0 / (current_time - prev_time))
        prev_time = current_time
        avg_fps = sum(fps_times) / len(fps_times)

        # YOLO inference
        results = model.predict(frame, conf=CONF_THRESHOLD, verbose=False)

        detected = []  # (class_name, confidence)

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
            last_detected_class = detected_class

        else:
            missed_frames += 1

            if missed_frames >= MAX_MISSED_FRAMES:
                new_state = "IDLE"
                last_detected_class = None
            else:
                new_state = current_state

        # Send to Arduino only on change
        if new_state != current_state:
            current_state = new_state
            ser.write((current_state + "\n").encode())
            print(f"Sent → {current_state}")

        # Overlays
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
