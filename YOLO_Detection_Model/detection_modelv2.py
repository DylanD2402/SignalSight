from ultralytics import YOLO
import cv2
import numpy as np

# Load YOLOv8 model
model = YOLO("yolov8n.pt")  # general pretrained model

# --- Tuned HSV color ranges for outdoor Ontario-style lights ---
COLOR_RANGES = {
    "red": [(0, 100, 120), (10, 255, 255), (160, 100, 120), (179, 255, 255)],
    # Yellow narrowed and made more demanding
    "yellow": [(22, 130, 180), (35, 255, 255)],
    "green": [(40, 60, 100), (90, 255, 255)]
}

def detect_light_color(light_roi):
    """Detects dominant light color inside cropped traffic light ROI."""
    hsv = cv2.cvtColor(light_roi, cv2.COLOR_BGR2HSV)

    # --- Brightness mask to isolate illuminated areas ---
    v_channel = hsv[:, :, 2]
    bright_mask = cv2.inRange(v_channel, 180, 255)  # keep only bright regions

    # --- Create color masks and apply brightness filtering ---
    mask_red1 = cv2.inRange(hsv, COLOR_RANGES["red"][0], COLOR_RANGES["red"][1])
    mask_red2 = cv2.inRange(hsv, COLOR_RANGES["red"][2], COLOR_RANGES["red"][3])
    mask_red = cv2.bitwise_or(mask_red1, mask_red2)
    mask_red = cv2.bitwise_and(mask_red, bright_mask)

    mask_yellow = cv2.inRange(hsv, COLOR_RANGES["yellow"][0], COLOR_RANGES["yellow"][1])
    mask_yellow = cv2.bitwise_and(mask_yellow, bright_mask)

    mask_green = cv2.inRange(hsv, COLOR_RANGES["green"][0], COLOR_RANGES["green"][1])
    mask_green = cv2.bitwise_and(mask_green, bright_mask)

    # Count bright color pixels
    counts = {
        "red": cv2.countNonZero(mask_red),
        "yellow": cv2.countNonZero(mask_yellow),
        "green": cv2.countNonZero(mask_green)
    }

    # Decide the dominant color
    active_color = max(counts, key=counts.get)
    # --- Bias to suppress false yellows ---
    if active_color == "yellow":
        # If yellow count isn’t clearly dominant, demote it to red
        total_pixels = sum(counts.values()) + 1e-6
        yellow_ratio = counts["yellow"] / total_pixels
        dominance = counts["yellow"] / (max(counts["red"], counts["green"], 1))

        # Require strong dominance and high yellow ratio
        if yellow_ratio < 0.4 or dominance < 1.5:
            active_color = "red"

    return active_color, counts


def process_image(img_path):
    """Runs YOLO + ROI + color detection."""
    img = cv2.imread(img_path)
    results = model(img, verbose=False)

    for r in results:
        for box in r.boxes:
            cls = int(box.cls[0])
            label = model.names[cls]

            if "traffic light" in label.lower():
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cropped = img[y1:y2, x1:x2]
                h, w = cropped.shape[:2]

                # --- Focus on inner circular bulb area (ignore casing edges) ---
                margin_x, margin_y = int(w * 0.15), int(h * 0.15)
                inner_crop = cropped[margin_y:h - margin_y, margin_x:w - margin_x]

                # Detect active light color
                color, counts = detect_light_color(inner_crop)

                # Draw visualization
                color_map = {"red": (0, 0, 255), "yellow": (0, 255, 255), "green": (0, 255, 0)}
                cv2.rectangle(img, (x1, y1), (x2, y2), color_map[color], 3)
                cv2.putText(img, f"{color.upper()} LIGHT", (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, color_map[color], 2)

                print(f"Detected traffic light at ({x1},{y1}) — {color.upper()} "
                      f"[R:{counts['red']} Y:{counts['yellow']} G:{counts['green']}]")

    cv2.imshow("Traffic Light Detection", img)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


# --- Run on your test image ---
process_image("../images/multi.jpg")  # replace with your file name
