import cv2
import pandas as pd
import time
from collections import deque
from ultralytics import YOLO

def detect_traffic_lights_video(
    model_path: str,
    video_path: str,
    output_csv: str = "detections.csv",
    conf_threshold: float = 0.5,
    show_video: bool = True
):
    """
    Detect traffic lights in a video using a trained YOLO model and export results to a CSV.
    """

    # Load model
    model = YOLO(model_path)

    # Open video
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video {video_path}")

    # Prepare DataFrame
    columns = ["frame", "class", "confidence", "xmin", "ymin", "xmax", "ymax"]
    df = pd.DataFrame(columns=columns)

    frame_num = 0

    # FPS tracking
    fps_times = deque(maxlen=30)
    prev_time = time.time()

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_num += 1

        # FPS calculation
        current_time = time.time()
        fps_times.append(1.0 / (current_time - prev_time))
        prev_time = current_time
        avg_fps = sum(fps_times) / len(fps_times)

        # Run YOLO prediction
        h, w, _ = frame.shape
        roi = frame[0:int(h * 0.75), :]

        # YOLO inference
        results = model.predict(roi, imgsz=320, conf=0.5, verbose=False)

        for result in results:
            boxes = result.boxes.xyxy.cpu().numpy()
            scores = result.boxes.conf.cpu().numpy()
            class_ids = result.boxes.cls.cpu().numpy()

            for box, score, cls_id in zip(boxes, scores, class_ids):
                xmin, ymin, xmax, ymax = map(int, box)

                df = pd.concat([df, pd.DataFrame([[
                    frame_num,
                    model.names[int(cls_id)],
                    float(score),
                    xmin, ymin, xmax, ymax
                ]], columns=columns)], ignore_index=True)

                if show_video:
                    cv2.rectangle(frame, (xmin, ymin), (xmax, ymax), (0, 255, 0), 2)
                    cv2.putText(
                        frame,
                        f"{model.names[int(cls_id)]} {score:.2f}",
                        (xmin, ymin - 5),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (0, 255, 0),
                        1
                    )

        # Display FPS
        if show_video:
            cv2.putText(
                frame,
                f"FPS: {avg_fps:.2f}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 255),
                2
            )

            cv2.imshow("Traffic Light Detection", frame)
            if cv2.waitKey(1) & 0xFF == 27:
                break

    cap.release()
    if show_video:
        cv2.destroyAllWindows()

    df.to_csv(output_csv, index=False)
    print(f"CSV export complete: {output_csv}")


detect_traffic_lights_video(
    model_path="best.pt",
    video_path="../images/20251119_073415A.mp4",
    output_csv="traffic_light_detections.csv",
    conf_threshold=0.5,
    show_video=True
)
