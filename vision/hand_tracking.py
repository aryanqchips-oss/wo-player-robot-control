import cv2
import mediapipe as mp
import socket
import json
import time

CAMERA_INDEX = 0
UDP_ADDRESS = ("127.0.0.1", 5005)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
mp_hands = mp.solutions.hands
draw = mp.solutions.drawing_utils

camera = cv2.VideoCapture(CAMERA_INDEX)
camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

if not camera.isOpened():
    raise RuntimeError("Cannot open webcam. Try CAMERA_INDEX = 1.")

def classify(hand):
    lm = hand.landmark

    # Four fingers: tip above the PIP joint means extended.
    tips = [8, 12, 16, 20]
    pips = [6, 10, 14, 18]
    extended = sum(lm[t].y < lm[p].y for t, p in zip(tips, pips))

    if extended >= 4:
        return "FORWARD"
    if extended == 0:
        return "STOP"

    # One extended index finger: point left or right.
    if (lm[8].y < lm[6].y and
            all(lm[t].y >= lm[p].y for t, p in [(12, 10), (16, 14), (20, 18)])):
        delta_x = lm[8].x - lm[0].x
        if delta_x < -0.12:
            return "LEFT"
        if delta_x > 0.12:
            return "RIGHT"

    return "STOP"

def send_command(player, gesture):
    payload = {"player": player, "gesture": gesture, "time": time.time()}
    sock.sendto(json.dumps(payload).encode(), UDP_ADDRESS)

try:
    with mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=2,
        model_complexity=0,
        min_detection_confidence=0.6,
        min_tracking_confidence=0.6,
    ) as hands:
        while True:
            ok, frame = camera.read()
            if not ok:
                break

            frame = cv2.flip(frame, 1)
            h, w = frame.shape[:2]
            midpoint = w // 2
            cv2.line(frame, (midpoint, 0), (midpoint, h), (255, 255, 255), 2)
            cv2.putText(frame, "PLAYER 1 - BLUE", (20, 35),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 140, 40), 2)
            cv2.putText(frame, "PLAYER 2 - GREEN", (midpoint + 20, 35),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (60, 230, 90), 2)

            result = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            gestures = {"blue": "STOP", "green": "STOP"}

            if result.multi_hand_landmarks:
                for hand in result.multi_hand_landmarks:
                    draw.draw_landmarks(frame, hand, mp_hands.HAND_CONNECTIONS)
                    wrist = hand.landmark[0]
                    x = int(wrist.x * w)
                    y = int(wrist.y * h)
                    player = "blue" if x < midpoint else "green"
                    gesture = classify(hand)
                    gestures[player] = gesture
                    color = (255, 140, 40) if player == "blue" else (60, 230, 90)
                    cv2.putText(frame, f"{player.upper()}: {gesture}",
                                (max(10, x - 60), max(70, y - 20)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

            # Send explicit STOP for any player whose hand is not detected.
            send_command("blue", gestures["blue"])
            send_command("green", gestures["green"])

            cv2.imshow("Two-Player Gesture Rover (Q to quit)", frame)
            if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                break
finally:
    # Tell both robots to stop when the vision app exits.
    send_command("blue", "STOP")
    send_command("green", "STOP")
    camera.release()
    cv2.destroyAllWindows()
    sock.close()
