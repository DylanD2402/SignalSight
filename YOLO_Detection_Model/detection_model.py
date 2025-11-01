from ultralytics import YOLO
import cv2

# Loading a pretrained YOLO model
model = YOLO("yolov8n.pt")

# image to use for testing traffic light detection
image_path = "../images/ontario_traffic_light.jpg"

# check results
results = model(image_path, show=True)

input("Press Enter to close the window...")


for result in results:
    for box in result.boxes:
        cls = model.names[int(box.cls)]
        conf = float(box.conf)
        print(f"Detected: {cls} with confidence {conf:.2f}")