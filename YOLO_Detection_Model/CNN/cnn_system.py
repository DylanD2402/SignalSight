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

MODEL_PATH = "best.pt"  # Model is in same directory

SERIAL_PORT = "/dev/ttyACM0"   # Arduino on Pi
BAUD_RATE = 115200

CONF_THRESHOLD = 0.5
MAX_MISSED_FRAMES = 3
INFERENCE_SIZE = 320  # YOLO inference image size (smaller = faster, less accurate)

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
    # Don't try to create test windows as this can interfere with OpenCV initialization
    return bool(os.environ.get('DISPLAY'))

# -----------------------------
# MAIN FUNCTION
# -----------------------------

def live_traffic_light_detection(state_callback=None, no_arduino=True, no_display=True, stop_event=None, debug=False):
    # Load YOLO model
    model = YOLO(MODEL_PATH)

    # -----------------------------
    # Pi Camera setup (optimized for Pi 5)
    # -----------------------------
    picam2 = Picamera2()
    config = picam2.create_preview_configuration(
        main={"format": "RGB888", "size": (640, 480)},
        buffer_count=4  # Reduce buffer count for lower latency
    )
    picam2.configure(config)
    picam2.start()
    time.sleep(0.5)  # Reduced warmup time

    # -----------------------------
    # Display detection
    # -----------------------------
    if no_display:
        display_available = False
        if debug:
            print("CV Module: Running in headless mode (no display output)")
    else:
        display_available = has_display()
        if display_available:
            print("CV Module: Display detected - showing live feed")
        else:
            print("CV Module: No display detected - running in headless mode")

    # -----------------------------
    # Arduino serial (auto-detect)
    # -----------------------------
    ser = None
    if not no_arduino and os.path.exists(SERIAL_PORT):
        try:
            ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
            time.sleep(2)
            print(f"Arduino connected on {SERIAL_PORT}")
        except Exception as e:
            print(f"WARNING: Could not open Arduino: {e}")
            print("Running without Arduino")
    elif not no_arduino:
        print(f"Arduino not detected ({SERIAL_PORT} not found)")

    fps_times = deque(maxlen=30)
    prev_time = time.time()

    current_state = "IDLE"
    missed_frames = 0

    if not no_arduino or not no_display or debug:
        print("Traffic light detection started")

    try:
        while True:
            # Check stop event if provided
            if stop_event and stop_event.is_set():
                break
            # Capture frame
            frame = picam2.capture_array()

            # FPS calculation (optional logging)
            current_time = time.time()
            fps_times.append(1.0 / (current_time - prev_time))
            prev_time = current_time
            avg_fps = sum(fps_times) / len(fps_times)

            # ROI optimization: Only process top 75% of frame (traffic lights are in upper portion)
            h, w, _ = frame.shape
            roi = frame[0:int(h * 0.75), :]

            # YOLO inference (optimized for speed)
            inference_start = time.perf_counter() if debug else None
            results = model.predict(
                roi,
                conf=CONF_THRESHOLD,
                imgsz=INFERENCE_SIZE,
                verbose=False,
                device='cpu',
                half=False,  # Full precision (half-precision not supported on CPU)
                # max_det=10   # Max 10 detections (traffic lights) - reduces processing
            )
            inference_time = (time.perf_counter() - inference_start) * 1000 if debug else 0

            detected = []  # (class_name, confidence)
            annotated_frame = None
            if display_available:
                annotated_frame = frame.copy()

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
            detected_class = None
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

            # Update state
            if new_state != current_state:
                current_state = new_state

            # Debug output
            if debug:
                detection_str = ", ".join([f"{c}:{s:.2f}" for c, s in detected]) if detected else "None"
                print(f"[{time.strftime('%H:%M:%S')}] State: {current_state:15s} | Detected: {detection_str:30s} | FPS: {avg_fps:5.1f} | Inference: {inference_time:5.1f}ms")

            # Call callback if provided (for integration mode)
            if state_callback:
                confidence = max((s for c, s in detected if c == detected_class), default=0.0) if detected and detected_class else 0.0
                state_callback({
                    'state': current_state,
                    'confidence': confidence,
                    'fps': avg_fps
                })

            # Send to Arduino if standalone mode (no GPS data in standalone)
            if not no_arduino and ser is not None:
                message = f"STATE={current_state} SPEED=0 DIST=0\n"
                ser.write(message.encode())
                if not debug:  # Only print if not in debug mode (debug shows more info)
                    print(f"[{time.strftime('%H:%M:%S')}] Sent → {message.strip()}")

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
            # No display output in headless mode - frames are processed but not shown

            # Optional: throttle loop slightly to stabilize CPU usage
            # removed for testing purposes
            # time.sleep(0.01)

    except KeyboardInterrupt:
        print("\nStopping system...")

    finally:
        if ser is not None:
            ser.close()
        picam2.stop()
        if display_available:
            cv2.destroyAllWindows()
        print("Clean shutdown complete")

# -----------------------------
# RUN
# -----------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Traffic Light Detection System")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--display", action="store_true", help="Show video display (if available)")

    args = parser.parse_args()

    live_traffic_light_detection(
        no_arduino=False,  # Auto-detect Arduino
        no_display=not args.display,
        debug=args.debug
    )

