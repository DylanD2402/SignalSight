import cv2
import time
from collections import deque
from ultralytics import YOLO

def live_traffic_light_detection(
    model_path: str,
    camera_index: int = 0,
    conf_threshold: float = 0.5
):
    """
    Run live traffic light detection using a camera feed and display inference FPS.

    Args:
        model_path (str): Path to trained YOLO model (.pt)
        camera_index (int): Camera index (0 = default webcam)
        conf_threshold (float): Confidence threshold
    """

    # Load YOLO model
    model = YOLO(model_path)

    # Open camera
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise RuntimeError("Could not open camera")

    # FPS tracking
    fps_times = deque(maxlen=30)
    prev_time = time.time()

    print("Live traffic light detection started. Press ESC to quit.")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # FPS calculation
        current_time = time.time()
        fps_times.append(1.0 / (current_time - prev_time))
        prev_time = current_time
        avg_fps = sum(fps_times) / len(fps_times)

        # Run YOLO inference
        results = model.predict(frame, conf=conf_threshold, verbose=False)

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

    cap.release()
    cv2.destroyAllWindows()

live_traffic_light_detection(
    model_path="best.pt",
    camera_index=0,   # change to 1,2 if using external camera
    conf_threshold=0.5
)