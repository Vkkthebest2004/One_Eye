import cv2

print("Python started")

camera = cv2.VideoCapture(0)

print("Camera opened:", camera.isOpened())

if not camera.isOpened():
    print("❌ Camera could not be opened")
    exit()

while True:
    ret, frame = camera.read()

    print("Frame:", ret)

    if not ret:
        print("❌ Could not read frame")
        break

    cv2.imshow("My Camera", frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

camera.release()
cv2.destroyAllWindows()

print("Camera closed")