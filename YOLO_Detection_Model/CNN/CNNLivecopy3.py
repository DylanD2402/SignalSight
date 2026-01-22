import time
import serial
import os
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
# HELPER FUNCTIONS
# -----------------------------

def has_display():
    """Detect if a display is available."""
    # Check DISPLAY environment variable (Linux/Unix)
    if os.environ.get('DISPLAY'):
        try:
            # Try to create a window to verify display actually works
            test_img = cv2.imread('/dev/null')  # Create dummy image
            if test_img is None:
                test_img = [[0]]
            cv2.namedWindow('test', cv2.WINDOW_NORMAL)
            cv2.destroyWindow('test')
            return True
        except:
            return False
    return False

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
    # Display detection
    # -----------------------------
    display_available = has_display()
    if display_available:
        print("🖥️  Display detected - showing live feed")
    else:
        print("🔲 No display detected - running in headless mode")

    # -----------------------------
    # Arduino serial (optional)
    # -----------------------------
    ser = None
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        time.sleep(2)
        print("✅ Arduino serial connected")
    except Exception as e:
        print(f"⚠️  Could not connect to Arduino: {e}")
        print("Running without Arduino")

    fps_times = deque(maxlen=30)
    prev_time = time.time()

    current_state = "IDLE"
    missed_frames = 0

    print("🚦 Headless Raspberry Pi CNN → Arduino system started")

    try:
        while True:
            # Capture frame
            frame = picam2.capture_array()

            # FPS calculation (optional logging)
            current_time = time.time()
            fps_times.append(1.0 / (current_time - prev_time))
            prev_time = current_time
            avg_fps = sum(fps_times) / len(fps_times)

            # YOLO inference
            results = model.predict(frame, conf=CONF_THRESHOLD, verbose=False)

            detected = []  # (class_name, confidence)
            annotated_frame = frame.copy() if display_available else None

            for result in results:
                scores = result.boxes.conf.cpu().numpy()
                class_ids = result.boxes.cls.cpu().numpy()
                boxes = result.boxes.xyxy.cpu().numpy()

                for score, cls_id, box in zip(scores, class_ids, boxes):
                    class_name = model.names[int(cls_id)]
                    if class_name in CLASS_TO_ARDUINO:
                        detected.append((class_name, score))

                        # Draw bounding box if display is available
                        if display_available:
                            x1, y1, x2, y2 = map(int, box)
                            color_map = {"red": (0, 0, 255), "yellow": (0, 255, 255), "green": (0, 255, 0)}
                            color = color_map.get(class_name, (255, 255, 255))
                            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)
                            cv2.putText(annotated_frame, f"{class_name.upper()} {score:.2f}",
                                       (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

            # -----------------------------
            # STATE MACHINE
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

            # Send to Arduino only on change
            if new_state != current_state:
                current_state = new_state
                if ser is not None:
                    ser.write((current_state + "\n").encode())
                    print(f"[{time.strftime('%H:%M:%S')}] Sent → {current_state}")
                else:
                    print(f"[{time.strftime('%H:%M:%S')}] State → {current_state} (FPS: {avg_fps:.1f})")

            # Display annotated frame if display is available
            if display_available:
                # Add state and FPS overlay
                cv2.putText(annotated_frame, f"STATE: {current_state}", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                cv2.putText(annotated_frame, f"FPS: {avg_fps:.1f}", (10, 60),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

                cv2.imshow("Traffic Light Detection", annotated_frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

            # Optional: throttle loop slightly to stabilize CPU usage
            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\n🛑 Stopping system...")

    finally:
        if ser is not None:
            ser.close()
        picam2.stop()
        if display_available:
            cv2.destroyAllWindows()
        print("✅ Clean shutdown complete")

# -----------------------------
# RUN
# -----------------------------
if __name__ == "__main__":
    live_traffic_light_detection()

