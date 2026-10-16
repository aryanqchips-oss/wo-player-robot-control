import json
import socket
import time

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist


class GestureBridge(Node):
    def __init__(self):
        super().__init__("two_player_gesture_bridge")

        self.robot_publishers = {
            "blue": self.create_publisher(
                Twist, "/model/vehicle_blue/cmd_vel", 10
            ),
            "green": self.create_publisher(
                Twist, "/model/vehicle_green/cmd_vel", 10
            ),
        }
        self.latest = {
            "blue": ("STOP", time.monotonic()),
            "green": ("STOP", time.monotonic()),
        }

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 5005))
        self.sock.setblocking(False)
        self.timer = self.create_timer(0.05, self.update)
        self.get_logger().info("Gesture bridge ready; both robots start stopped.")

    def update(self):
        while True:
            try:
                raw, _ = self.sock.recvfrom(2048)
            except BlockingIOError:
                break
            try:
                data = json.loads(raw.decode())
                player, gesture = data["player"], data["gesture"]
                if player in self.latest and gesture in {
                    "FORWARD", "LEFT", "RIGHT", "STOP"
                }:
                    self.latest[player] = (gesture, time.monotonic())
            except (ValueError, KeyError, TypeError):
                continue

        now = time.monotonic()
        for player, (gesture, timestamp) in self.latest.items():
            cmd = Twist()

            # Fail-safe: stop if gesture updates stop arriving.
            if now - timestamp < 0.5:
                if gesture == "FORWARD":
                    cmd.linear.x = 0.35
                elif gesture == "LEFT":
                    cmd.angular.z = 0.8
                elif gesture == "RIGHT":
                    cmd.angular.z = -0.8

            self.robot_publishers[player].publish(cmd)

    def destroy_node(self):
        for publisher in self.robot_publishers.values():
            publisher.publish(Twist())
        self.sock.close()
        super().destroy_node()


def main():
    rclpy.init()
    node = GestureBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
