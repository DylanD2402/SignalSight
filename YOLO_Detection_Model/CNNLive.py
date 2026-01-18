import cv2
import time
import argparse
from collections import deque
from ultralytics import YOLO
from picamera2 import Picamera2


def live_traffic_light_detection(
        model_path: str,
        camera_index: int = 0,
        conf_threshold: float = 0.5,
        headless: bool = False,  # Added headless parameter
        save_interval: int = 30  # Save every N frames when headless
):
    """
    Run live traffic light detection using Raspberry Pi camera and display inference FPS.

    Args:
        model_path (str): Path to trained YOLO model (.pt)
        camera_index (int): Not used (kept for compatibility)
        conf_threshold (float): Confidence threshold
        headless (bool): Run without display (for headless operation)
        save_interval (int): Save frame every N frames when in headless mode
    """

    # Load YOLO model
    model = YOLO(model_path)

    # Initialize Raspberry Pi camera
    picam2 = Picamera2()
    config = picam2.create_preview_configuration(main={"format": "RGB888", "size": (640, 480)})
    picam2.configure(config)
    picam2.start()

    # FPS tracking
    fps_times = deque(maxlen=30)
    prev_time = time.time()
    frame_count = 0  # Added frame counter

    if headless:
        print("Live traffic light detection started in HEADLESS mode. Press Ctrl+C to quit.")
    else:
        print("Live traffic light detection started. Press ESC to quit.")

    try:
        while True:
            # Capture frame from Pi camera
            frame = picam2.capture_array()
            h, w, _ = frame.shape
            roi = frame[0:int(h * 0.75), :]

            # FPS calculation
            current_time = time.time()
            fps_times.append(1.0 / (current_time - prev_time))
            prev_time = current_time
            avg_fps = sum(fps_times) / len(fps_times)

            # Run YOLO inference
            results = model.predict(roi, imgsz=320, conf=conf_threshold, verbose=False)

            detections = []  # Store detection info for logging

            for result in results:
                boxes = result.boxes.xyxy.cpu().numpy()
                scores = result.boxes.conf.cpu().numpy()
                class_ids = result.boxes.cls.cpu().numpy()

                for box, score, cls_id in zip(boxes, scores, class_ids):
                    xmin, ymin, xmax, ymax = map(int, box)
                    label = f"{model.names[int(cls_id)]} {score:.2f}"

                    # Store detection info
                    detections.append({
                        'class': model.names[int(cls_id)],
                        'confidence': score,
                        'bbox': (xmin, ymin, xmax, ymax)
                    })

                    cv2.rectangle(frame, (xmin, ymin), (xmax, ymax), (0, 255, 0), 2)
                    cv2.putText(
                        frame,
                        label,
                        (xmin, ymin - 5),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (0, 255, 0),
                        1
                    )

            # Draw FPS
            cv2.putText(
                frame,
                f"Inference FPS: {avg_fps:.2f}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 255),
                2
            )

            # Log detections to console in headless mode
            if headless:
                if detections:
                    print(f"[Frame {frame_count}] FPS: {avg_fps:.2f} | Detections: {len(detections)}")
                    for det in detections:
                        print(f"  -> {det['class']}: {det['confidence']:.2f} at {det['bbox']}")

                # Save annotated frame periodically for debugging
                if frame_count % save_interval == 0:
                    filename = f"/tmp/detection_{frame_count}.jpg"
                    cv2.imwrite(filename, frame)
                    print(f"[Frame {frame_count}] Saved to {filename}")

                frame_count += 1
            else:
                # Display mode - show window
                cv2.imshow("Live Traffic Light Detection", frame)

                if cv2.waitKey(1) & 0xFF == 27:  # ESC
                    break

    except KeyboardInterrupt:
        print("\nStopping detection...")
    finally:
        picam2.stop()
        if not headless:
            cv2.destroyAllWindows()
        print("Detection stopped.")


# Add argument parser for command-line options
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Traffic Light Detection')
    parser.add_argument('--headless', action='store_true',
                        help='Run without display (for headless operation)')
    parser.add_argument('--model', type=str, default='best.pt',
                        help='Path to YOLO model')
    parser.add_argument('--conf', type=float, default=0.5,
                        help='Confidence threshold')
    parser.add_argument('--save-interval', type=int, default=30,
                        help='Save frame every N frames in headless mode')

    args = parser.parse_args()

    live_traffic_light_detection(
        model_path=args.model,
        camera_index=0,
        conf_threshold=args.conf,
        headless=args.headless,
        save_interval=args.save_interval
    )
