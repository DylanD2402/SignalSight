import cv2
import numpy as np
from ultralytics import YOLO

# Load the YOLO model (pretrained on COCO, includes traffic light class)
model = YOLO('yolov8n.pt')

def get_light_state(cropped_img):
    """
    Detects the light color (red, yellow, or green) from a cropped traffic light image.
    Uses HSV color space with brightness filtering to avoid casing influence.
    """

    # Convert to HSV
    hsv = cv2.cvtColor(cropped_img, cv2.COLOR_BGR2HSV)

    # Define HSV ranges for bright colors
    red_lower1 = np.array([0, 80, 150])
    red_upper1 = np.array([10, 255, 255])
    red_lower2 = np.array([160, 80, 150])
    red_upper2 = np.array([179, 255, 255])

    yellow_lower = np.array([15, 80, 150])
    yellow_upper = np.array([35, 255, 255])

    green_lower = np.array([40, 80, 150])
    green_upper = np.array([90, 255, 255])

    # Create masks
    mask_red = cv2.bitwise_or(cv2.inRange(hsv, red_lower1, red_upper1),
                              cv2.inRange(hsv, red_lower2, red_upper2))
    mask_yellow = cv2.inRange(hsv, yellow_lower, yellow_upper)
    mask_green = cv2.inRange(hsv, green_lower, green_upper)

    # Focus only on bright circular zones (reduce background/casing noise)
    brightness = cv2.split(hsv)[2]
    bright_mask = cv2.inRange(brightness, 180, 255)

    mask_red = cv2.bitwise_and(mask_red, bright_mask)
    mask_yellow = cv2.bitwise_and(mask_yellow, bright_mask)
    mask_green = cv2.bitwise_and(mask_green, bright_mask)

    # Count non-zero pixels (intensity of each color)
    red_pixels = cv2.countNonZero(mask_red)
    yellow_pixels = cv2.countNonZero(mask_yellow)
    green_pixels = cv2.countNonZero(mask_green)

    # Determine which color dominates
    max_val = max(red_pixels, yellow_pixels, green_pixels)

    if max_val < 30:  # No strong light detected
        return "Unknown"
    elif max_val == red_pixels:
        return "Red Light"
    elif max_val == yellow_pixels:
        return "Yellow Light"
    else:
        return "Green Light"


def detect_traffic_lights(image_path):
    # Load the input image
    img = cv2.imread(image_path)
    if img is None:
        print("Error: Could not load image.")
        return

    results = model(img)
    annotated_img = img.copy()

    for box in results[0].boxes:
        cls = int(box.cls[0])
        if model.names[cls] == 'traffic light':
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            cropped_light = img[y1:y2, x1:x2]
            light_state = get_light_state(cropped_light)

            # Draw bounding box and label
            color = (0, 255, 0) if "Green" in light_state else (0, 255, 255) if "Yellow" in light_state else (0, 0, 255)
            cv2.rectangle(annotated_img, (x1, y1), (x2, y2), color, 2)
            cv2.putText(annotated_img, light_state, (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

            print(f"Detected: {light_state}")

    cv2.imshow("Traffic Light Detection", annotated_img)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


# Example usage
detect_traffic_lights("../images/red.jpg")  # Replace with your image path

