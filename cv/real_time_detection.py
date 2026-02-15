from ultralytics import YOLO
import cv2

model = YOLO("yolov8n.pt")

cam = cv2.VideoCapture(0)

while True:
    ret, frame = cam.read()
    if not ret:
        break

    #run detection
    results = model(frame)

    # Plot detections on the frame
    annotated_frame = results[0].plot()

    #show frame
    cv2.imshow("Traffic Light Detection", annotated_frame)

    # Press q to quit
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cam.release()
cv2.destroyAllWindows()


