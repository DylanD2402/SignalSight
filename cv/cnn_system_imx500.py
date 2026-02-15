import time
import serial
import os
import sys
import cv2
import argparse
from collections import deque

from picamera2 import Picamera2
from picamera2.devices import IMX500
from picamera2.devices.imx500 import (NetworkIntrinsics,
                                      postprocess_nanodet_detection)

# -----------------------------
# CONFIGURATION
# -----------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(SCRIPT_DIR, "models", "imx500", "ash.rpk")
LABELS_PATH = os.path.join(SCRIPT_DIR, "models", "imx500", "labels.txt")

SERIAL_PORT = "/dev/ttyACM0"
BAUD_RATE = 115200

CONF_THRESHOLD = 0.5
IOU_THRESHOLD = 0.65
MAX_DETECTIONS = 10
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
# IMX500 DETECTION HELPERS
# -----------------------------

class Detection:
    def __init__(self, coords, category, conf, metadata, imx500_dev, picam2_dev):
        """Create a Detection object, recording the bounding box, category and confidence."""
        self.category = category
        self.conf = conf
        self.box = imx500_dev.convert_inference_coords(coords, metadata, picam2_dev)


def parse_detections(metadata, imx500_dev, picam2_dev, intrinsics, labels, last_detections):
    """Parse the output tensor into detected objects, scaled to the ISP output."""
    bbox_normalization = intrinsics.bbox_normalization
    bbox_order = intrinsics.bbox_order
    threshold = CONF_THRESHOLD
    iou = IOU_THRESHOLD
    max_detections = MAX_DETECTIONS

    np_outputs = imx500_dev.get_outputs(metadata, add_batch=True)
    input_w, input_h = imx500_dev.get_input_size()
    if np_outputs is None:
        return last_detections

    if intrinsics.postprocess == "nanodet":
        boxes, scores, classes = \
            postprocess_nanodet_detection(outputs=np_outputs[0], conf=threshold, iou_thres=iou,
                                          max_out_dets=max_detections)[0]
        from picamera2.devices.imx500.postprocess import scale_boxes
        boxes = scale_boxes(boxes, 1, 1, input_h, input_w, False, False)
    else:
        boxes, scores, classes = np_outputs[0][0], np_outputs[1][0], np_outputs[2][0]
        if bbox_normalization:
            boxes = boxes / input_h
        if bbox_order == "xy":
            boxes = boxes[:, [1, 0, 3, 2]]

    detections = [
        Detection(box, category, score, metadata, imx500_dev, picam2_dev)
        for box, score, category in zip(boxes, scores, classes)
        if score > threshold
    ]
    return detections


# -----------------------------
# HELPER FUNCTIONS
# -----------------------------

def has_display():
    """Detect if a display is available."""
    return bool(os.environ.get('DISPLAY'))


# -----------------------------
# MAIN FUNCTION
# -----------------------------

def live_traffic_light_detection(state_callback=None, no_arduino=True, no_display=True,
                                 stop_event=None, debug=False, stream=False,
                                 bbox_normalization=None, bbox_order="yx",
                                 postprocess=None, preserve_aspect_ratio=False):
    # -----------------------------
    # IMX500 setup (must be before Picamera2)
    # -----------------------------
    imx500 = IMX500(MODEL_PATH)
    intrinsics = imx500.network_intrinsics
    if not intrinsics:
        intrinsics = NetworkIntrinsics()
        intrinsics.task = "object detection"
    elif intrinsics.task != "object detection":
        print("Network is not an object detection task", file=sys.stderr)
        return

    # Load labels
    with open(LABELS_PATH, 'r') as f:
        intrinsics.labels = f.read().splitlines()

    # Apply overrides
    if bbox_normalization is not None:
        intrinsics.bbox_normalization = bbox_normalization
    if bbox_order is not None:
        intrinsics.bbox_order = bbox_order
    if postprocess is not None:
        intrinsics.postprocess = postprocess
    if preserve_aspect_ratio:
        intrinsics.preserve_aspect_ratio = preserve_aspect_ratio

    intrinsics.update_with_defaults()

    labels = intrinsics.labels
    if intrinsics.ignore_dash_labels:
        labels = [label for label in labels if label and label != "-"]

    # -----------------------------
    # Pi Camera setup
    # -----------------------------
    picam2 = Picamera2(imx500.camera_num)
    config = picam2.create_preview_configuration(
        main={"format": "RGB888", "size": (640, 480)},
        controls={"FrameRate": intrinsics.inference_rate},
        buffer_count=12
    )

    imx500.show_network_fw_progress_bar()

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

    # Never use show_preview (Qt conflicts with OpenCV's bundled Qt in venv).
    # Display is handled manually via OpenCV imshow below.
    picam2.start(config)

    if intrinsics.preserve_aspect_ratio:
        imx500.set_auto_aspect_ratio()

    # -----------------------------
    # MJPEG stream server (optional)
    # -----------------------------
    streaming = False
    if stream:
        import stream_server
        streaming = stream_server.start()

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
    last_detections = []

    if not no_arduino or not no_display or debug:
        print("Traffic light detection started (IMX500 on-sensor inference)")

    try:
        while True:
            # Check stop event if provided
            if stop_event and stop_event.is_set():
                break

            # Capture request gives us both metadata (inference) and frame (display)
            request = picam2.capture_request()
            try:
                metadata = request.get_metadata()

                # FPS calculation
                current_time = time.time()
                fps_times.append(1.0 / max(current_time - prev_time, 1e-6))
                prev_time = current_time
                avg_fps = sum(fps_times) / len(fps_times)

                # Parse IMX500 on-sensor inference results
                inference_start = time.perf_counter() if debug else None
                detections = parse_detections(metadata, imx500, picam2, intrinsics, labels, last_detections)
                last_detections = detections
                inference_time = (time.perf_counter() - inference_start) * 1000 if debug else 0

                # Filter detections to traffic light classes we care about
                detected = []
                for det in detections:
                    class_idx = int(det.category)
                    if class_idx < len(labels):
                        class_name = labels[class_idx]
                        if class_name in CLASS_TO_ARDUINO:
                            detected.append((class_name, det.conf, det.box))

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

                # Debug output: in-place for IDLE, new line for active detections
                if debug:
                    detection_str = ", ".join([f"{c}:{s:.2f}" for c, s, _ in detected]) if detected else "None"
                    line = f"[{time.strftime('%H:%M:%S')}] State: {current_state:15s} | Detected: {detection_str:30s} | FPS: {avg_fps:5.1f} | Parse: {inference_time:5.1f}ms"
                    if current_state == "IDLE":
                        sys.stdout.write(f"\r\033[K{line}")
                    else:
                        sys.stdout.write(f"\r\033[K{line}\n")
                    sys.stdout.flush()

                # Call callback if provided (for integration mode)
                if state_callback:
                    confidence = max((s for c, s, _ in detected if c == detected_class), default=0.0) if detected and detected_class else 0.0
                    state_callback({
                        'state': current_state,
                        'confidence': confidence,
                        'fps': avg_fps
                    })

                # Send to Arduino if standalone mode
                if not no_arduino and ser is not None:
                    message = f"STATE={current_state} SPEED=0 DIST=0\n"
                    ser.write(message.encode())
                    if not debug:
                        line = f"[{time.strftime('%H:%M:%S')}] Sent -> {message.strip()}"
                        sys.stdout.write(f"\r\033[K{line}")
                        sys.stdout.flush()

                # Display with OpenCV (no Qt preview - avoids Qt plugin conflicts)
                if display_available:
                    frame = request.make_array("main")

                    # Draw bounding boxes for ALL detections from IMX500
                    traffic_color_map = {"red": (0, 0, 255), "yellow": (0, 255, 255), "green": (0, 255, 0)}
                    for det in detections:
                        class_idx = int(det.category)
                        class_name = labels[class_idx] if class_idx < len(labels) else f"class_{class_idx}"
                        conf = det.conf
                        x, y, w, h = det.box

                        if class_name in traffic_color_map:
                            color = traffic_color_map[class_name]
                            thickness = 2
                        else:
                            color = (200, 200, 200)
                            thickness = 1

                        cv2.rectangle(frame, (x, y), (x + w, y + h), color, thickness)
                        cv2.putText(frame, f"{class_name} {conf:.2f}",
                                    (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, thickness)

                    cv2.putText(frame, f"STATE: {current_state}", (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                    cv2.putText(frame, f"FPS: {avg_fps:.1f}", (10, 60),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

                    cv2.imshow("Traffic Light Detection (IMX500)", frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break

                # Feed MJPEG stream (annotated frame if display is on, raw otherwise)
                if streaming:
                    if display_available:
                        stream_server.update_frame(frame)
                    else:
                        stream_server.update_frame(request.make_array("main"))

            finally:
                request.release()

    except KeyboardInterrupt:
        print("\n\nStopping system...")

    finally:
        if ser is not None:
            ser.close()
        if display_available:
            cv2.destroyAllWindows()
        picam2.stop()
        if not state_callback:
            print("Clean shutdown complete")


# -----------------------------
# RUN
# -----------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Traffic Light Detection System (IMX500)")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--display", action="store_true", help="Show video display (if available)")
    parser.add_argument("--bbox-normalization", action=argparse.BooleanOptionalAction,
                        help="Normalize bbox coordinates")
    parser.add_argument("--bbox-order", choices=["yx", "xy"], default="yx",
                        help="Bbox order: yx -> (y0,x0,y1,x1) xy -> (x0,y0,x1,y1)")
    parser.add_argument("--postprocess", choices=["", "nanodet"], default=None,
                        help="Post-processing type")
    parser.add_argument("--preserve-aspect-ratio", action=argparse.BooleanOptionalAction,
                        help="Preserve pixel aspect ratio of input tensor")
    parser.add_argument("--stream", action="store_true",
                        help="Enable MJPEG stream server for remote viewing (VLC)")
    parser.add_argument("--threshold", type=float, default=None,
                        help=f"Detection confidence threshold (default: {CONF_THRESHOLD})")
    parser.add_argument("--iou", type=float, default=None,
                        help=f"IOU threshold (default: {IOU_THRESHOLD})")

    args = parser.parse_args()

    # Allow threshold/iou override from CLI
    if args.threshold is not None:
        CONF_THRESHOLD = args.threshold
    if args.iou is not None:
        IOU_THRESHOLD = args.iou

    live_traffic_light_detection(
        no_arduino=False,
        no_display=not args.display,
        debug=args.debug,
        stream=args.stream,
        bbox_normalization=args.bbox_normalization,
        bbox_order=args.bbox_order,
        postprocess=args.postprocess,
        preserve_aspect_ratio=args.preserve_aspect_ratio or False,
    )
