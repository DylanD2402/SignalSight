import time
import os
import cv2
from collections import deque
from ultralytics import YOLO

# -----------------------------
# CONFIGURATION
# -----------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(SCRIPT_DIR, "models", "yolo", "best.pt")

CONF_THRESHOLD = 0.25
MAX_MISSED_FRAMES = 3
INFERENCE_SIZE = 640  # smaller = faster, less accurate

CLASS_TO_STATE = {
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

def live_traffic_light_detection(state_callback=None, no_display=False, stop_event=None, debug=False, camera_index=0):
    # Load YOLO model
    model = YOLO(MODEL_PATH)

    # -----------------------------
    # Webcam setup (macOS-friendly backend)
    # -----------------------------
    cap = cv2.VideoCapture(camera_index, cv2.CAP_AVFOUNDATION)
    if not cap.isOpened():
        raise RuntimeError(
            f"Could not open webcam (index={camera_index}). "
            f"Try --cam 1 or 2, and make sure Camera permission is enabled for your app."
        )

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    time.sleep(0.2)

    # -----------------------------
    # Display (always show if no_display=False)
    # -----------------------------
    display_available = not no_display
    if display_available:
        print("CV Module: Display ON - showing live feed (press q to quit)")
        cv2.namedWindow("Traffic Light Detection (Webcam)", cv2.WINDOW_NORMAL)
        cv2.startWindowThread()
    else:
        if debug:
            print("CV Module: Headless mode (no display output)")

    fps_times = deque(maxlen=30)
    prev_time = time.time()

    current_state = "IDLE"
    missed_frames = 0

    print("Traffic light detection started (webcam mode)")

    try:
        while True:
            if stop_event and stop_event.is_set():
                break

            ok, frame = cap.read()
            if not ok or frame is None:
                if debug:
                    print("WARNING: Failed to read frame from webcam")
                # Still pump waitKey so windows can update/respond
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
                continue

            # FPS calculation
            current_time = time.time()
            dt = current_time - prev_time
            prev_time = current_time
            if dt > 0:
                fps_times.append(1.0 / dt)
            avg_fps = (sum(fps_times) / len(fps_times)) if fps_times else 0.0

            # ROI optimization: Only process top 75% of frame
            h, w, _ = frame.shape

            # Top portion (where traffic lights usually are)
            roi_h = int(h * 0.60)
            roi_top = frame[0:roi_h, :]

            # Center crop to "zoom in" (keep middle 70% width)
            x_offset = int(w * 0.15)
            x_end = int(w * 0.85)
            roi = roi_top[:, x_offset:x_end]

            # YOLO inference
            inference_start = time.perf_counter() if debug else None
            results = model.predict(
                roi,
                conf=CONF_THRESHOLD,
                imgsz=INFERENCE_SIZE,
                verbose=False,
                device="cpu",
                half=False
            )
            inference_time = (time.perf_counter() - inference_start) * 1000 if debug else 0.0

            detected = []  # (class_name, confidence)
            annotated_frame = frame.copy() if display_available else None

            for result in results:
                if result.boxes is None or len(result.boxes) == 0:
                    continue

                scores = result.boxes.conf.cpu().numpy()
                class_ids = result.boxes.cls.cpu().numpy()
                boxes = result.boxes.xyxy.cpu().numpy()

                for score, cls_id, box in zip(scores, class_ids, boxes):
                    class_name = model.names[int(cls_id)]
                    if class_name in CLASS_TO_STATE:
                        detected.append((class_name, float(score)))

                        if display_available:
                            x1, y1, x2, y2 = map(int, box)
                            # Box coords are relative to ROI (top of frame), so y is correct already
                            color_map = {
                                "red": (0, 0, 255),
                                "yellow": (0, 255, 255),
                                "green": (0, 255, 0)
                            }
                            color = color_map.get(class_name, (255, 255, 255))
                            cv2.rectangle(annotated_frame, (x1 + x_offset, y1), (x2 + x_offset, y2), color, 2)
                            cv2.putText(
                                annotated_frame,
                                f"{class_name.upper()} {score:.2f}",
                                (x1 + x_offset, max(20, y1 - 10)),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.6,
                                color,
                                2
                            )

            # -----------------------------
            # STATE MACHINE
            # -----------------------------
            detected_class = None
            if detected:
                missed_frames = 0
                detected_class = max(detected, key=lambda x: (CLASS_PRIORITY[x[0]], x[1]))[0]
                new_state = CLASS_TO_STATE[detected_class]
            else:
                missed_frames += 1
                new_state = "IDLE" if missed_frames >= MAX_MISSED_FRAMES else current_state

            if new_state != current_state:
                current_state = new_state

            # Debug output
            if debug:
                detection_str = ", ".join([f"{c}:{s:.2f}" for c, s in detected]) if detected else "None"
                print(
                    f"[{time.strftime('%H:%M:%S')}] State: {current_state:15s} | "
                    f"Detected: {detection_str:30s} | FPS: {avg_fps:5.1f} | "
                    f"Inference: {inference_time:5.1f}ms"
                )

            # Callback (optional integration)
            if state_callback:
                confidence = max((s for c, s in detected if c == detected_class), default=0.0) if detected_class else 0.0
                state_callback({"state": current_state, "confidence": confidence, "fps": avg_fps})

            # Display overlay + show
            if display_available:
                cv2.putText(annotated_frame, f"STATE: {current_state}", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                cv2.putText(annotated_frame, f"FPS: {avg_fps:.1f}", (10, 60),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

                cv2.imshow("Traffic Light Detection (Webcam)", annotated_frame)

            # IMPORTANT: always pump waitKey (even if not displaying) so UI stays responsive
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    except KeyboardInterrupt:
        print("\nStopping system...")

    finally:
        cap.release()
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass
        print("Clean shutdown complete")

# -----------------------------
# RUN
# -----------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Traffic Light Detection System (Webcam)")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--no-display", action="store_true", help="Run headless (no window)")
    parser.add_argument("--cam", type=int, default=0, help="Webcam index (0, 1, 2...)")

    args = parser.parse_args()

    live_traffic_light_detection(
        no_display=args.no_display,
        debug=args.debug,
        camera_index=args.cam
    )