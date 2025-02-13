import cv2 as cv
from PIL import Image

from ultralytics import YOLO

model = YOLO("yolov8m.pt")

cap = cv.VideoCapture(0)

COLORS = {
    "person": (255, 0, 0),  # Blue
    "chair": (0, 0, 255),     # Red
    "cell phone": (0, 255, 255),   # Yellow
    "bottle": (128, 0, 128),   # Purple
    "tv": (128, 128, 0),   # Orange
    "default": (0, 255, 0)  # Green (for unlisted classes)
}

# Check if the camera opened successfully
if cap.isOpened():
    print("ready")
else:
    raise IOError("Cannot open webcam")

while(True):
    # Capture frame-by-frame
    ret, frame = cap.read()

    # Run YOLO detection
    results = model(frame)  # Detect objects
        

    # Draw detections
    for result in results:
        for box in result.boxes:  # Iterate over detected objects
            x1, y1, x2, y2 = map(int, box.xyxy[0])  # Get bounding box
            conf = box.conf[0].item()  # Confidence score
            cls = int(box.cls[0].item())  # Class ID

            label = model.names[cls]

            # Choose color based on detected class
            color = COLORS.get(label, COLORS["default"])

            # Draw bounding box
            cv.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            label = f"{model.names[cls]}: {conf:.2f}"
            cv.putText(frame, label, (x1, y1 - 10), cv.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    cv.namedWindow("YOLO Webcam", cv.WND_PROP_FULLSCREEN)
    cv.setWindowProperty("YOLO Webcam", cv.WND_PROP_FULLSCREEN, cv.WINDOW_FULLSCREEN)

    cv.imshow("YOLO Webcam", frame)
    if cv.waitKey(1) & 0xFF == ord("q"):  # Press 'q' to exit
        break


cap.release()
cv.destroyAllWindows()