import cv2
import time
from collections import deque
from ultralytics import YOLO
from picamera2 import Picamera2

def live_traffic_light_detection(
    model_path: str,
    camera_index: int = 0,
    conf_threshold: float = 0.5
):
    """
    Run live traffic light detection using Raspberry Pi camera and display inference FPS.

    Args:
        model_path (str): Path to trained YOLO model (.pt)
        camera_index (int): Not used (kept for compatibility)
        conf_threshold (float): Confidence threshold
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

    print("Live traffic light detection started. Press ESC to quit.")

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

        for result in results:
            boxes = result.boxes.xyxy.cpu().numpy()
            scores = result.boxes.conf.cpu().numpy()
            class_ids = result.boxes.cls.cpu().numpy()

            for box, score, cls_id in zip(boxes, scores, class_ids):
                xmin, ymin, xmax, ymax = map(int, box)
                label = f"{model.names[int(cls_id)]} {score:.2f}"

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

        cv2.imshow("Live Traffic Light Detection", frame)

        if cv2.waitKey(1) & 0xFF == 27:  # ESC
            break

    picam2.stop()
    cv2.destroyAllWindows()

live_traffic_light_detection(
    model_path="best.pt",
    camera_index=0,   # parameter not used for Pi camera
    conf_threshold=0.5
)