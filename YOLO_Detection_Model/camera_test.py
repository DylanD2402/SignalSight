import cv2
from picamera2 import Picamera2

def test_camera():
    """Simple test to verify Raspberry Pi camera is working."""

    # Initialize Raspberry Pi camera
    print("Initializing Raspberry Pi camera...")
    picam2 = Picamera2()

    # Configure camera
    config = picam2.create_preview_configuration(main={"format": "RGB888", "size": (640, 480)})
    picam2.configure(config)

    # Start camera
    picam2.start()
    print("Camera started successfully!")
    print("Press 'q' to quit")

    try:
        while True:
            # Capture frame
            frame = picam2.capture_array()

            # Display frame
            cv2.imshow("Pi Camera Test", frame)

            # Check for quit key
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    except KeyboardInterrupt:
        print("\nInterrupted by user")

    finally:
        # Cleanup
        picam2.stop()
        cv2.destroyAllWindows()
        print("Camera stopped")

if __name__ == "__main__":
    test_camera()
