import time
from collections import deque

import cv2
from ultralytics import YOLO

# Optional serial (only used if USE_ARDUINO=True)
try:
    import serial
except ImportError:
    serial = None

# -----------------------------
# CONFIGURATION
# -----------------------------
MODEL_PATH = "models/yolo/best.pt"

USE_ARDUINO = False
SERIAL_PORT = "/dev/tty.usbmodemXXXX"  # update later
BAUD_RATE = 9600

WEBCAM_INDEX = 0
FRAME_WIDTH = 640
FRAME_HEIGHT = 480

CONF_THRESHOLD = 0.5
MAX_MISSED_FRAMES = 3

WINDOW_NAME = "Traffic Light Detection (press Q to quit)"

CLASS_TO_ARDUINO = {
    "red": "ACTIVE_RED",
    "yellow": "ACTIVE_YELLOW",
    "green": "ACTIVE_GREEN",
}

CLASS_PRIORITY = {"red": 3, "yellow": 2, "green": 1}

# -----------------------------
# MAIN FUNCTION
# -----------------------------
def live_traffic_light_detection():
    model = YOLO(MODEL_PATH)

    cap = cv2.VideoCapture(WEBCAM_INDEX)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open webcam at index {WEBCAM_INDEX}")

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)

    # Arduino (optional)
    ser = None
    if USE_ARDUINO:
        if serial is None:
            raise RuntimeError("pyserial not installed. Run: pip install pyserial")
        try:
            ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
            time.sleep(2)
            print(f"✅ Arduino connected on {SERIAL_PORT}")
        except Exception as e:
            print(f"⚠️ Could not open Arduino serial port ({SERIAL_PORT}): {e}")
            print("   Continuing WITHOUT Arduino...")
            ser = None
    else:
        print("⚠️ Arduino disabled (USE_ARDUINO=False). Running webcam-only.")

    fps_times = deque(maxlen=30)
    prev_time = time.time()

    current_state = "IDLE"
    missed_frames = 0

    print("🚦 Webcam YOLO system started (press Q to quit, Ctrl+C also works)")

    try:
        while True:
            ret, frame_bgr = cap.read()
            if not ret:
                print("⚠️ Failed to read frame from webcam")
                time.sleep(0.05)
                continue

            # FPS calc
            now = time.time()
            dt = now - prev_time
            prev_time = now
            if dt > 0:
                fps_times.append(1.0 / dt)
            avg_fps = sum(fps_times) / len(fps_times) if fps_times else 0.0

            # YOLO expects RGB arrays
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

            # Inference
            results = model.predict(frame_rgb, conf=CONF_THRESHOLD, verbose=False)

            detected = []  # (class_name, confidence)
            for result in results:
                if result.boxes is None or len(result.boxes) == 0:
                    continue
                scores = result.boxes.conf.detach().cpu().numpy()
                class_ids = result.boxes.cls.detach().cpu().numpy()

                for score, cls_id in zip(scores, class_ids):
                    class_name = model.names[int(cls_id)]
                    if class_name in CLASS_TO_ARDUINO:
                        detected.append((class_name, float(score)))

            # State machine
            if detected:
                missed_frames = 0
                detected_class = max(detected, key=lambda x: (CLASS_PRIORITY[x[0]], x[1]))[0]
                new_state = CLASS_TO_ARDUINO[detected_class]
            else:
                missed_frames += 1
                new_state = "IDLE" if missed_frames >= MAX_MISSED_FRAMES else current_state

            # Send to Arduino only on change (optional)
            if new_state != current_state:
                current_state = new_state
                if ser is not None:
                    ser.write((current_state + "\n").encode())
                print(f"[{time.strftime('%H:%M:%S')}] State → {current_state}")

            # ---- DISPLAY ----
            display = frame_bgr.copy()

            # draw YOLO boxes (optional): use Ultralytics' built-in plotting
            # (This plots on an RGB image, so we convert back)
            try:
                plotted_rgb = results[0].plot()  # returns RGB image with boxes
                display = cv2.cvtColor(plotted_rgb, cv2.COLOR_RGB2BGR)
            except Exception:
                # If plotting fails, still show raw frame
                pass

            cv2.putText(display, f"STATE: {current_state}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2, cv2.LINE_AA)
            cv2.putText(display, f"FPS: {avg_fps:.1f}", (10, 65),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)

            cv2.imshow(WINDOW_NAME, display)

            # Press Q to quit
            if cv2.waitKey(1) & 0xFF in (ord('q'), ord('Q')):
                break

            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\n🛑 Stopping system...")

    finally:
        try:
            if ser is not None:
                ser.close()
        except Exception:
            pass
        cap.release()
        cv2.destroyAllWindows()
        print("✅ Clean shutdown complete")


if __name__ == "__main__":
    live_traffic_light_detection()