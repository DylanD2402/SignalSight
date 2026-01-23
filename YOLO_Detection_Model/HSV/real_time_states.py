import serial
from ultralytics import YOLO
import cv2
import numpy as np
import time
from enum import Enum, auto

# -----------------------------
# System State Definition
# -----------------------------
class SystemState(Enum):
    IDLE = auto()
    ACTIVE_RED = auto()
    ACTIVE_YELLOW = auto()
    ACTIVE_GREEN = auto()
    FAULT = auto()

# -----------------------------
# YOLO + HSV Config
# -----------------------------
model = YOLO("yolov8n.pt")  # replace with your trained model later

# HSV ranges copied / adapted from detection_modelv2.py
COLOR_RANGES = {
    "red": [(0, 100, 120), (10, 255, 255), (160, 100, 120), (179, 255, 255)],
    "yellow": [(25, 180, 200), (35, 255, 255)],
    "green": [(35, 40, 120), (90, 255, 255)]
}

CONF_THRESH = 0.5      # YOLO confidence threshold for "traffic light"
LOST_TIMEOUT = 1.0     # seconds with no detection → go IDLE
PRINT_INTERVAL = 2.0   # print stats every 2 seconds

# -----------------------------
# HSV Color Detection
# -----------------------------
def detect_light_color(light_roi):
    """Detects dominant light color inside cropped traffic light ROI."""
    if light_roi is None or light_roi.size == 0:
        return "none", {"red": 0, "yellow": 0, "green": 0}, 0.0

    hsv = cv2.cvtColor(light_roi, cv2.COLOR_BGR2HSV)

    # --- Brightness mask ---
    v_channel = hsv[:, :, 2]
    bright_mask = cv2.inRange(v_channel, 180, 255)

    # --- Color masks ---
    mask_red1 = cv2.inRange(hsv, COLOR_RANGES["red"][0], COLOR_RANGES["red"][1])
    mask_red2 = cv2.inRange(hsv, COLOR_RANGES["red"][2], COLOR_RANGES["red"][3])
    mask_red = cv2.bitwise_or(mask_red1, mask_red2)
    mask_red = cv2.bitwise_and(mask_red, bright_mask)

    mask_yellow = cv2.inRange(hsv, COLOR_RANGES["yellow"][0], COLOR_RANGES["yellow"][1])
    mask_yellow = cv2.bitwise_and(mask_yellow, bright_mask)

    mask_green = cv2.inRange(hsv, COLOR_RANGES["green"][0], COLOR_RANGES["green"][1])
    mask_green = cv2.bitwise_and(mask_green, bright_mask)

    counts = {
        "red": cv2.countNonZero(mask_red),
        "yellow": cv2.countNonZero(mask_yellow),
        "green": cv2.countNonZero(mask_green),
    }

    total = counts["red"] + counts["yellow"] + counts["green"]
    if total == 0:
        return "none", counts, 0.0

    # For debugging:
    print("R:", counts["red"], "Y:", counts["yellow"], "G:", counts["green"])

    active_color = max(counts, key=counts.get)
    confidence = counts[active_color] / float(total)

    # --- Improved yellow logic ---
    if active_color == "yellow":
        dominance = counts["yellow"] / max(counts["red"], counts["green"], 1)

        # If yellow isn't clearly dominant, choose between red and green
        if confidence < 0.4 or dominance < 1.5:
            if counts["green"] >= counts["red"]:
                active_color = "green"
                confidence = counts["green"] / float(total)
            else:
                active_color = "red"
                confidence = counts["red"] / float(total)

    return active_color, counts, confidence

# -----------------------------
# State Update Logic
# -----------------------------
def update_state(prev_state, color, color_conf, time_since_last_detection, has_detection):
    """
    Returns new_state based on:
      - detected color
      - color_conf: 0-1
      - time_since_last_detection
      - has_detection: whether YOLO found a traffic light box this frame
    """
    # Simple fault example: (you can add real checks for camera/model errors)
    # if some_error_condition:
    #     return SystemState.FAULT

    # No detection or low confidence
    if not has_detection or color == "none" or color_conf < 0.2:
        if time_since_last_detection > LOST_TIMEOUT:
            return SystemState.IDLE
        else:
            # Briefly keep last valid state so it doesn't flicker
            return prev_state

    # Map color → ACTIVE state
    if color == "red":
        return SystemState.ACTIVE_RED
    elif color == "yellow":
        return SystemState.ACTIVE_YELLOW
    elif color == "green":
        return SystemState.ACTIVE_GREEN
    else:
        # unknown color string
        if time_since_last_detection > LOST_TIMEOUT:
            return SystemState.IDLE
        return prev_state

import serial
from ultralytics import YOLO
import cv2
import numpy as np
import time
from enum import Enum, auto

# -----------------------------
# System State Definition
# -----------------------------
class SystemState(Enum):
    IDLE = auto()
    ACTIVE_RED = auto()
    ACTIVE_YELLOW = auto()
    ACTIVE_GREEN = auto()
    FAULT = auto()

# -----------------------------
# YOLO + HSV Config
# -----------------------------
model = YOLO("yolov8n.pt")  # replace with your trained model later

# HSV ranges copied / adapted from detection_modelv2.py
COLOR_RANGES = {
    "red": [(0, 100, 120), (10, 255, 255), (160, 100, 120), (179, 255, 255)],
    "yellow": [(25, 180, 200), (35, 255, 255)],
    "green": [(35, 40, 120), (90, 255, 255)]
}

CONF_THRESH = 0.5      # YOLO confidence threshold for "traffic light"
LOST_TIMEOUT = 1.0     # seconds with no detection → go IDLE
PRINT_INTERVAL = 2.0   # print stats every 2 seconds

# -----------------------------
# HSV Color Detection
# -----------------------------
def detect_light_color(light_roi):
    """Detects dominant light color inside cropped traffic light ROI."""
    if light_roi is None or light_roi.size == 0:
        return "none", {"red": 0, "yellow": 0, "green": 0}, 0.0

    hsv = cv2.cvtColor(light_roi, cv2.COLOR_BGR2HSV)

    # --- Brightness mask ---
    v_channel = hsv[:, :, 2]
    bright_mask = cv2.inRange(v_channel, 180, 255)

    # --- Color masks ---
    mask_red1 = cv2.inRange(hsv, COLOR_RANGES["red"][0], COLOR_RANGES["red"][1])
    mask_red2 = cv2.inRange(hsv, COLOR_RANGES["red"][2], COLOR_RANGES["red"][3])
    mask_red = cv2.bitwise_or(mask_red1, mask_red2)
    mask_red = cv2.bitwise_and(mask_red, bright_mask)

    mask_yellow = cv2.inRange(hsv, COLOR_RANGES["yellow"][0], COLOR_RANGES["yellow"][1])
    mask_yellow = cv2.bitwise_and(mask_yellow, bright_mask)

    mask_green = cv2.inRange(hsv, COLOR_RANGES["green"][0], COLOR_RANGES["green"][1])
    mask_green = cv2.bitwise_and(mask_green, bright_mask)

    counts = {
        "red": cv2.countNonZero(mask_red),
        "yellow": cv2.countNonZero(mask_yellow),
        "green": cv2.countNonZero(mask_green),
    }

    total = counts["red"] + counts["yellow"] + counts["green"]
    if total == 0:
        return "none", counts, 0.0

    # For debugging:
    print("R:", counts["red"], "Y:", counts["yellow"], "G:", counts["green"])

    active_color = max(counts, key=counts.get)
    confidence = counts[active_color] / float(total)

    # --- Improved yellow logic ---
    if active_color == "yellow":
        dominance = counts["yellow"] / max(counts["red"], counts["green"], 1)

        # If yellow isn't clearly dominant, choose between red and green
        if confidence < 0.4 or dominance < 1.5:
            if counts["green"] >= counts["red"]:
                active_color = "green"
                confidence = counts["green"] / float(total)
            else:
                active_color = "red"
                confidence = counts["red"] / float(total)

    return active_color, counts, confidence

# -----------------------------
# State Update Logic
# -----------------------------
def update_state(prev_state, color, color_conf, time_since_last_detection, has_detection):
    """
    Returns new_state based on:
      - detected color
      - color_conf: 0-1
      - time_since_last_detection
      - has_detection: whether YOLO found a traffic light box this frame
    """
    # Simple fault example: (you can add real checks for camera/model errors)
    # if some_error_condition:
    #     return SystemState.FAULT

    # No detection or low confidence
    if not has_detection or color == "none" or color_conf < 0.2:
        if time_since_last_detection > LOST_TIMEOUT:
            return SystemState.IDLE
        else:
            # Briefly keep last valid state so it doesn't flicker
            return prev_state

    # Map color → ACTIVE state
    if color == "red":
        return SystemState.ACTIVE_RED
    elif color == "yellow":
        return SystemState.ACTIVE_YELLOW
    elif color == "green":
        return SystemState.ACTIVE_GREEN
    else:
        # unknown color string
        if time_since_last_detection > LOST_TIMEOUT:
            return SystemState.IDLE
        return prev_state

# -----------------------------
# Main Real-Time Loop
# -----------------------------
def main():
    cam = cv2.VideoCapture(0)  # adjust index for Pi camera if needed

    if not cam.isOpened():
        print("ERROR: Could not open camera.")
        return

    current_state = SystemState.IDLE
    last_detection_time = 0.0
    last_print_time = time.time()

    frame_count = 0
    total_latency = 0.0

    print("Starting real-time detection with state machine... Press 'q' to quit.")

    while True:
        loop_start = time.time()
        ret, frame = cam.read()
        if not ret:
            print("Camera read failed.")
            current_state = SystemState.FAULT
            break

        # YOLO inference (you can set verbose=False for speed)
        results = model(frame, verbose=False)

        # Find best traffic light box (highest confidence)
        best_box = None
        best_conf = 0.0
        for r in results:
            for box in r.boxes:
                cls_id = int(box.cls[0])
                label = model.names[cls_id]
                conf = float(box.conf[0])

                if "traffic light" in label.lower() and conf > best_conf:
                    best_conf = conf
                    best_box = box

        has_detection = best_box is not None and best_conf >= CONF_THRESH

        color = "none"
        color_conf = 0.0

        annotated_frame = frame.copy()

        if has_detection:
            # Crop ROI
            x1, y1, x2, y2 = map(int, best_box.xyxy[0])
            cropped = frame[y1:y2, x1:x2]
            h, w = cropped.shape[:2]

            # Inner region to ignore casing edges
            margin_x, margin_y = int(w * 0.25), int(h * 0.25)
            inner_crop = cropped[margin_y:h - margin_y, margin_x:w - margin_x]

            # HSV-based color detection
            color, counts, color_conf = detect_light_color(inner_crop)

            # Draw bounding box with color
            color_map = {
                "red": (0, 0, 255),
                "yellow": (0, 255, 255),
                "green": (0, 255, 0),
                "none": (255, 255, 255)
            }
            box_color = color_map.get(color, (255, 255, 255))
            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), box_color, 3)
            cv2.putText(
                annotated_frame,
                f"{color.upper()} ({color_conf:.2f})",
                (x1, max(0, y1 - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                box_color,
                2,
            )

            last_detection_time = loop_start  # update when we have a valid detection

        time_since_last_det = loop_start - last_detection_time

        # Update system state
        new_state = update_state(
            prev_state=current_state,
            color=color,
            color_conf=color_conf,
            time_since_last_detection=time_since_last_det,
            has_detection=has_detection
        )
        current_state = new_state

        loop_end = time.time()
        latency_ms = (loop_end - loop_start) * 1000.0
        total_latency += latency_ms
        frame_count += 1

        # FPS estimate (instant)
        fps = 1.0 / max((loop_end - loop_start), 1e-6)

        # Overlay state + metrics on frame
        cv2.putText(
            annotated_frame,
            f"STATE: {current_state.name}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0) if "ACTIVE" in current_state.name else (255, 255, 255),
            2,
        )
        cv2.putText(
            annotated_frame,
            f"FPS: {fps:.1f}  Latency: {latency_ms:.1f} ms",
            (10, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 0),
            2,
        )

        cv2.imshow("Traffic Light State Machine", annotated_frame)

        # Periodic console log for NFR analysis
        now = time.time()
        if now - last_print_time >= PRINT_INTERVAL:
            avg_latency = total_latency / max(frame_count, 1)
            yolo_conf_val = best_conf if has_detection else 0.0
            print(
            f"[{time.strftime('%H:%M:%S')}] "
            f"State={current_state.name}, "
            f"Color={color}, "
            f"YOLO_conf={yolo_conf_val:.2f}, "
            f"Color_conf={color_conf:.2f}, "
            f"FPS~{fps:.1f}, "
            f"AvgLatency={avg_latency:.1f} ms"
            )
            last_print_time = now

        # Quit
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cam.release()
    cv2.destroyAllWindows()
    print("Exited real-time loop. Final state:", current_state.name)

def send_state_to_arduino(ser, state: SystemState):
    if ser is None:
        return
    try:
        msg = f"{state.name}\n"
        ser.write(msg.encode("utf-8"))
        ser.flush()
        print(f"[SERIAL] Sent → {state.name}")
    except serial.SerialException as e:
        print("[SERIAL ERROR]", e)

# -----------------------------
# Main Real-Time Loop
# -----------------------------
def main():
    # -----------------------------
    # SERIAL SETUP
    # -----------------------------
    try:
        ser = serial.Serial(
            port="/dev/ttyACM0",  # 🔁 CHANGE THIS
            baudrate=115200,
            timeout=1
        )
        time.sleep(2)  # allow Arduino reset
        print("Serial connected.")
    except serial.SerialException:
        ser = None
        print("WARNING: Serial not available. Running without Arduino.")

    cam = cv2.VideoCapture(0)  # adjust index for Pi camera if needed

    if not cam.isOpened():
        print("ERROR: Could not open camera.")
        return

    current_state = SystemState.IDLE
    prev_state = current_state
    last_detection_time = 0.0
    last_print_time = time.time()

    frame_count = 0
    total_latency = 0.0

    print("Starting real-time detection with state machine... Press 'q' to quit.")

    while True:
        loop_start = time.time()
        ret, frame = cam.read()
        if not ret:
            print("Camera read failed.")
            current_state = SystemState.FAULT
            break

        # YOLO inference (you can set verbose=False for speed)
        results = model(frame, verbose=False)

        # Find best traffic light box (highest confidence)
        best_box = None
        best_conf = 0.0
        for r in results:
            for box in r.boxes:
                cls_id = int(box.cls[0])
                label = model.names[cls_id]
                conf = float(box.conf[0])

                if "traffic light" in label.lower() and conf > best_conf:
                    best_conf = conf
                    best_box = box

        has_detection = best_box is not None and best_conf >= CONF_THRESH

        color = "none"
        color_conf = 0.0

        annotated_frame = frame.copy()

        if has_detection:
            # Crop ROI
            x1, y1, x2, y2 = map(int, best_box.xyxy[0])
            cropped = frame[y1:y2, x1:x2]
            h, w = cropped.shape[:2]

            # Inner region to ignore casing edges
            margin_x, margin_y = int(w * 0.25), int(h * 0.25)
            inner_crop = cropped[margin_y:h - margin_y, margin_x:w - margin_x]

            # HSV-based color detection
            color, counts, color_conf = detect_light_color(inner_crop)

            # Draw bounding box with color
            color_map = {
                "red": (0, 0, 255),
                "yellow": (0, 255, 255),
                "green": (0, 255, 0),
                "none": (255, 255, 255)
            }
            box_color = color_map.get(color, (255, 255, 255))
            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), box_color, 3)
            cv2.putText(
                annotated_frame,
                f"{color.upper()} ({color_conf:.2f})",
                (x1, max(0, y1 - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                box_color,
                2,
            )

            last_detection_time = loop_start  # update when we have a valid detection

        time_since_last_det = loop_start - last_detection_time

        # Update system state
        new_state = update_state(
            prev_state=current_state,
            color=color,
            color_conf=color_conf,
            time_since_last_detection=time_since_last_det,
            has_detection=has_detection
        )
        if new_state != current_state:
            current_state = new_state
            send_state_to_arduino(ser, current_state)
        else:
            current_state = new_state

        loop_end = time.time()
        latency_ms = (loop_end - loop_start) * 1000.0
        total_latency += latency_ms
        frame_count += 1

        # FPS estimate (instant)
        fps = 1.0 / max((loop_end - loop_start), 1e-6)

        # Overlay state + metrics on frame
        cv2.putText(
            annotated_frame,
            f"STATE: {current_state.name}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0) if "ACTIVE" in current_state.name else (255, 255, 255),
            2,
        )
        cv2.putText(
            annotated_frame,
            f"FPS: {fps:.1f}  Latency: {latency_ms:.1f} ms",
            (10, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 0),
            2,
        )

        cv2.imshow("Traffic Light State Machine", annotated_frame)

        # Periodic console log for NFR analysis
        now = time.time()
        if now - last_print_time >= PRINT_INTERVAL:
            avg_latency = total_latency / max(frame_count, 1)
            yolo_conf_val = best_conf if has_detection else 0.0
            print(  
            f"[{time.strftime('%H:%M:%S')}] "
            f"State={current_state.name}, "
            f"Color={color}, "
            f"YOLO_conf={yolo_conf_val:.2f}, "
            f"Color_conf={color_conf:.2f}, "
            f"FPS~{fps:.1f}, "
            f"AvgLatency={avg_latency:.1f} ms"
            )
            last_print_time = now

        # Quit
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cam.release()
    cv2.destroyAllWindows()

    if ser is not None:
        ser.close()

    print("Exited real-time loop. Final state:", current_state.name)

def process_image(img_path: str):
    """
    Single-image version of the pipeline.
    Uses YOLO + HSV + state update on one photo,
    then shows the annotated result.
    """
    img = cv2.imread(img_path)
    if img is None:
        print(f"ERROR: Could not read image at '{img_path}'")
        return

    current_state = SystemState.IDLE
    last_detection_time = time.time()

    # Run YOLO on the image
    results = model(img, verbose=False)

    # Find best traffic light box
    best_box = None
    best_conf = 0.0
    for r in results:
        for box in r.boxes:
            cls_id = int(box.cls[0])
            label = model.names[cls_id]
            conf = float(box.conf[0])

            if "traffic light" in label.lower() and conf > best_conf:
                best_conf = conf
                best_box = box

    has_detection = best_box is not None and best_conf >= CONF_THRESH

    color = "none"
    color_conf = 0.0
    annotated = img.copy()

    if has_detection:
        x1, y1, x2, y2 = map(int, best_box.xyxy[0])
        cropped = img[y1:y2, x1:x2]
        h, w = cropped.shape[:2]

        # Inner region to ignore casing edges
        margin_x, margin_y = int(w * 0.15), int(h * 0.15)
        inner_crop = cropped[margin_y:h - margin_y, margin_x:w - margin_x]

        color, counts, color_conf = detect_light_color(inner_crop)

        color_map = {
            "red": (0, 0, 255),
            "yellow": (0, 255, 255),
            "green": (0, 255, 0),
            "none": (255, 255, 255),
        }
        box_color = color_map.get(color, (255, 255, 255))

        cv2.rectangle(annotated, (x1, y1), (x2, y2), box_color, 3)
        cv2.putText(
            annotated,
            f"{color.upper()} ({color_conf:.2f})",
            (x1, max(0, y1 - 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            box_color,
            2,
        )

        last_detection_time = time.time()

    time_since_last_det = time.time() - last_detection_time

    # Update state using same logic as real-time
    new_state = update_state(
        prev_state=current_state,
        color=color,
        color_conf=color_conf,
        time_since_last_detection=time_since_last_det,
        has_detection=has_detection,
    )
    current_state = new_state

    # Overlay state text
    cv2.putText(
        annotated,
        f"STATE: {current_state.name}",
        (10, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 0) if "ACTIVE" in current_state.name else (255, 255, 255),
        2,
    )

    yolo_conf_val = best_conf if has_detection else 0.0
    print(
        f"Image: {img_path}\n"
        f"  Detected color: {color} (conf={color_conf:.2f})\n"
        f"  YOLO_conf={yolo_conf_val:.2f}\n"
        f"  Final STATE={current_state.name}"
    )

    print("R:", counts["red"], "Y:", counts["yellow"], "G:", counts["green"])
    cv2.imshow("Traffic Light - Single Image", annotated)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

def process_video(video_path: str):
    """
    Video version of the pipeline.
    Reuses the SAME logic as process_image(),
    but runs it frame-by-frame with persistent state.
    """

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"ERROR: Could not open video '{video_path}'")
        return

    current_state = SystemState.IDLE
    last_detection_time = time.time()
    last_print_time = time.time()

    frame_count = 0
    total_latency = 0.0

    print("Starting VIDEO-based traffic light detection. Press 'q' to quit.")

    while True:
        loop_start = time.time()
        ret, frame = cap.read()
        if not ret:
            print("End of video reached.")
            break


        # ---- YOLO inference (SAME as your code) ----
        results = model(frame, verbose=False)

        best_box = None
        best_conf = 0.0
        for r in results:
            for box in r.boxes:
                cls_id = int(box.cls[0])
                label = model.names[cls_id]
                conf = float(box.conf[0])

                if "traffic light" in label.lower() and conf > best_conf:
                    best_conf = conf
                    best_box = box

        has_detection = best_box is not None and best_conf >= CONF_THRESH

        color = "none"
        color_conf = 0.0
        annotated = frame.copy()

        if has_detection:
            x1, y1, x2, y2 = map(int, best_box.xyxy[0])
            cropped = frame[y1:y2, x1:x2]
            h, w = cropped.shape[:2]

            margin_x, margin_y = int(w * 0.15), int(h * 0.15)
            inner_crop = cropped[margin_y:h - margin_y, margin_x:w - margin_x]

            color, counts, color_conf = detect_light_color(inner_crop)

            color_map = {
                "red": (0, 0, 255),
                "yellow": (0, 255, 255),
                "green": (0, 255, 0),
                "none": (255, 255, 255),
            }
            box_color = color_map.get(color, (255, 255, 255))

            cv2.rectangle(annotated, (x1, y1), (x2, y2), box_color, 3)
            cv2.putText(
                annotated,
                f"{color.upper()} ({color_conf:.2f})",
                (x1, max(0, y1 - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                box_color,
                2,
            )

            last_detection_time = loop_start

        # ---- STATE UPDATE (UNCHANGED) ----
        time_since_last_det = loop_start - last_detection_time
        current_state = update_state(
            prev_state=current_state,
            color=color,
            color_conf=color_conf,
            time_since_last_detection=time_since_last_det,
            has_detection=has_detection,
        )

        # ---- METRICS ----
        loop_end = time.time()
        latency_ms = (loop_end - loop_start) * 1000.0
        total_latency += latency_ms
        frame_count += 1
        fps = 1.0 / max((loop_end - loop_start), 1e-6)

        # ---- OVERLAY ----
        cv2.putText(
            annotated,
            f"STATE: {current_state.name}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0) if "ACTIVE" in current_state.name else (255, 255, 255),
            2,
        )
        cv2.putText(
            annotated,
            f"FPS: {fps:.1f}  Latency: {latency_ms:.1f} ms",
            (10, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 0),
            2,
        )

        cv2.imshow("Traffic Light - VIDEO", annotated)

        # ---- PERIODIC LOG ----
        now = time.time()
        if now - last_print_time >= PRINT_INTERVAL:
            avg_latency = total_latency / max(frame_count, 1)
            print(
                f"[{time.strftime('%H:%M:%S')}] "
                f"State={current_state.name}, "
                f"Color={color}, "
                f"YOLO_conf={best_conf:.2f}, "
                f"Color_conf={color_conf:.2f}, "
                f"FPS~{fps:.1f}, "
                f"AvgLatency={avg_latency:.1f} ms"
            )
            last_print_time = now

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
    print("Video processing finished. Final state:", current_state.name)

process_video("../images/20251119_073415A.mp4")
