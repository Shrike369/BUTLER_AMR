#!/usr/bin/env python3

import math
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient

from std_msgs.msg import String
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose


class NamedGoalNavigator(Node):

    def __init__(self):
        super().__init__('named_goal_navigator')

        # ---- Predefined Locations (x, y, yaw) ----
        self.locations = {
            "table1": (5.49883, 2.91867, -2.80273),
            "table2": (-0.496256, -3.01488, 1.54884),
            "table3": (-5.88464, 1.55979, 0.0465815),
            "dock": (0.0349911, 0.030797, 1.56418),
            "kitchen": (-5.85907, -8.76311, 1.63093),
        }

        # ---- Nav2 Action Client ----
        self._action_client = ActionClient(
            self,
            NavigateToPose,
            'navigate_to_pose'
        )

        # ---- Subscriber for location commands ----
        self.create_subscription(
            String,
            '/go_to_location',
            self.command_callback,
            10
        )

        self.get_logger().info("Named Goal Navigator Ready")
        self.get_logger().info("Waiting for commands on /go_to_location")

    # --------------------------------------------------
    # Callback when a location name is received
    # --------------------------------------------------
    def command_callback(self, msg: String):
        location_name = msg.data.strip().lower()

        if location_name not in self.locations:
            self.get_logger().warn(f"Unknown location: {location_name}")
            return

        self.get_logger().info(f"Received command: {location_name}")
        self.send_goal(location_name)

    # --------------------------------------------------
    # Send goal to Nav2
    # --------------------------------------------------
    def send_goal(self, location_name):

        # Wait for Nav2 server
        if not self._action_client.wait_for_server(timeout_sec=5.0):
            self.get_logger().error("Nav2 action server not available!")
            return

        x, y, yaw = self.locations[location_name]

        goal_msg = NavigateToPose.Goal()
        goal_msg.pose = PoseStamped()
        goal_msg.pose.header.frame_id = "map"
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()

        goal_msg.pose.pose.position.x = x
        goal_msg.pose.pose.position.y = y
        goal_msg.pose.pose.position.z = 0.0

        # Convert yaw → quaternion
        goal_msg.pose.pose.orientation.z = math.sin(yaw / 2.0)
        goal_msg.pose.pose.orientation.w = math.cos(yaw / 2.0)

        self.get_logger().info(f"Navigating to {location_name}...")

        send_goal_future = self._action_client.send_goal_async(
            goal_msg,
            feedback_callback=self.feedback_callback
        )

        send_goal_future.add_done_callback(self.goal_response_callback)

    # --------------------------------------------------
    # Goal accepted/rejected
    # --------------------------------------------------
    def goal_response_callback(self, future):
        goal_handle = future.result()

        if not goal_handle.accepted:
            self.get_logger().error("Goal rejected!")
            return

        self.get_logger().info("Goal accepted!")

        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self.get_result_callback)

    # --------------------------------------------------
    # Feedback from Nav2
    # --------------------------------------------------
    def feedback_callback(self, feedback_msg):
        feedback = feedback_msg.feedback
        self.get_logger().info(
            f"Distance remaining: {feedback.distance_remaining:.2f} m"
        )

    # --------------------------------------------------
    # Final result
    # --------------------------------------------------
    def get_result_callback(self, future):
        result = future.result().result
        self.get_logger().info("Goal completed!")


# ------------------------------------------------------
# Main
# ------------------------------------------------------
def main(args=None):
    rclpy.init(args=args)
    node = NamedGoalNavigator()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()