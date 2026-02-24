#!/usr/bin/env python3

import math
from enum import Enum
from collections import deque

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient

from std_msgs.msg import String
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped
from nav2_msgs.action import NavigateToPose


# =========================================================
# FSM STATES
# =========================================================
class State(Enum):
    IDLE = 0
    GO_KITCHEN = 1
    WAIT_KITCHEN = 2
    GO_TABLE = 3
    WAIT_TABLE = 4
    GO_HOME = 5
    RETURNING_TO_KITCHEN_CANCELLED = 6


# =========================================================
# BUTLER NODE
# =========================================================
class Butler(Node):

    def __init__(self):
        super().__init__('butler')

        # ---------------- Locations ----------------
        self.locations = {
            "table1": (5.49883, 2.91867, -2.80273),
            "table2": (-0.496256, -3.01488, 1.54884),
            "table3": (-5.88464, 1.55979, 0.0465815),
            "dock": (0.0349911, 0.030797, 1.56418),
            "kitchen": (-5.85907, -8.76311, 1.63093),
        }

        self.valid_tables = ["table1", "table2", "table3"]

        # ---------------- Robot State ----------------
        self.state = State.IDLE
        self.current_table = None
        self.queue = deque()
        self.goal_handle = None
        self.wait_timer = None
        self.current_pose = None
        self.current_target = None

        # ---------------- Nav2 Action Client ----------------
        self.action_client = ActionClient(
            self, NavigateToPose, 'navigate_to_pose'
        )

        # ---------------- Subscribers ----------------
        self.create_subscription(
            String,
            '/go_to_location',
            self.order_callback,
            10
        )

        self.create_subscription(
            String,
            '/cancel_order',
            self.cancel_callback,
            10
        )

        # Robot pose from AMCL
        self.create_subscription(
            PoseWithCovarianceStamped,
            '/amcl_pose',
            self.pose_callback,
            10
        )

        # ---------------- Status Publisher ----------------
        self.status_pub = self.create_publisher(
            String,
            '/butler_status',
            10
        )

        self.create_timer(0.5, self.publish_status)

        self.get_logger().info("✅ Butler Ready - Full Status Enabled")

    # =========================================================
    # POSE CALLBACK
    # =========================================================
    def pose_callback(self, msg):
        self.current_pose = msg.pose.pose

    # =========================================================
    # STATUS PUBLISHER (FULL VERSION)
    # =========================================================
    def publish_status(self):

        if self.current_pose:
            x = round(self.current_pose.position.x, 2)
            y = round(self.current_pose.position.y, 2)
            position_text = f"({x}, {y})"
        else:
            position_text = "Unknown"

        msg = String()
        msg.data = (
            f"\n========== BUTLER STATUS ==========\n"
            f"State        : {self.state.name}\n"
            f"Action       : {self.get_action_description()}\n"
            f"Current Order: {self.current_table if self.current_table else 'None'}\n"
            f"Target       : {self.current_target if self.current_target else 'None'}\n"
            f"Position     : {position_text}\n"
            f"Queue        : {list(self.queue)}\n"
            f"===================================\n"
        )

        self.status_pub.publish(msg)

    # =========================================================
    # ACTION DESCRIPTION
    # =========================================================
    def get_action_description(self):

        if self.state == State.IDLE:
            return "Idle at Dock"

        elif self.state == State.GO_KITCHEN:
            return "Moving to Kitchen"

        elif self.state == State.WAIT_KITCHEN:
            return "Loading items at Kitchen"

        elif self.state == State.GO_TABLE:
            return f"Delivering to {self.current_table}"

        elif self.state == State.WAIT_TABLE:
            return f"Handing over order at {self.current_table}"

        elif self.state == State.GO_HOME:
            return "Returning to Dock"

        elif self.state == State.RETURNING_TO_KITCHEN_CANCELLED:
            return "Returning to Kitchen (Cancelled Order)"

        return "Unknown"

    # =========================================================
    # ORDER RECEIVED
    # =========================================================
    def order_callback(self, msg):
        table = msg.data.strip().lower()

        if table not in self.valid_tables:
            self.get_logger().error(f"❌ Invalid table: {table}")
            return

        if self.state == State.IDLE:
            self.start_order(table)
        else:
            self.queue.append(table)
            self.get_logger().info(f"📌 Order queued: {table}")

    # =========================================================
    # CANCEL ORDER
    # =========================================================
    def cancel_callback(self, msg):
        self.get_logger().warn("⚠️ CANCEL REQUEST RECEIVED")

        if self.state in [State.IDLE, State.GO_HOME]:
            self.get_logger().info("Nothing to cancel.")
            return

        if self.goal_handle:
            self.goal_handle.cancel_goal_async()

        if self.wait_timer:
            self.wait_timer.cancel()
            self.wait_timer = None

        self.current_table = None
        self.state = State.RETURNING_TO_KITCHEN_CANCELLED
        self.send_goal("kitchen")

    # =========================================================
    # START ORDER
    # =========================================================
    def start_order(self, table):
        self.current_table = table
        self.state = State.GO_KITCHEN
        self.get_logger().info(f"🚀 Starting order for {table}")
        self.send_goal("kitchen")

    # =========================================================
    # SEND NAVIGATION GOAL
    # =========================================================
    def send_goal(self, location_name):

        self.current_target = location_name

        self.action_client.wait_for_server()

        x, y, yaw = self.locations[location_name]

        goal = NavigateToPose.Goal()
        goal.pose = PoseStamped()
        goal.pose.header.frame_id = "map"
        goal.pose.header.stamp = self.get_clock().now().to_msg()

        goal.pose.pose.position.x = x
        goal.pose.pose.position.y = y
        goal.pose.pose.orientation.z = math.sin(yaw / 2.0)
        goal.pose.pose.orientation.w = math.cos(yaw / 2.0)

        self.get_logger().info(f"➡️ Navigating to {location_name}")

        future = self.action_client.send_goal_async(goal)
        future.add_done_callback(self.goal_response)

    # =========================================================
    # GOAL RESPONSE
    # =========================================================
    def goal_response(self, future):

        self.goal_handle = future.result()

        if not self.goal_handle.accepted:
            self.get_logger().error("❌ Goal rejected by Nav2")
            return

        result_future = self.goal_handle.get_result_async()
        result_future.add_done_callback(self.goal_reached)

    # =========================================================
    # GOAL REACHED
    # =========================================================
    def goal_reached(self, future):

        self.goal_handle = None

        self.get_logger().info(f"✅ Goal reached in state: {self.state.name}")

        if self.state == State.GO_KITCHEN:
            self.state = State.WAIT_KITCHEN
            self.wait_timer = self.create_timer(5.0, self.after_kitchen)

        elif self.state == State.GO_TABLE:
            self.state = State.WAIT_TABLE
            self.wait_timer = self.create_timer(5.0, self.after_table)

        elif self.state == State.RETURNING_TO_KITCHEN_CANCELLED:
            self.check_queue_or_home()

        elif self.state == State.GO_HOME:
            self.state = State.IDLE
            self.current_table = None

    # =========================================================
    # AFTER KITCHEN WAIT
    # =========================================================
    def after_kitchen(self):
        if self.wait_timer:
            self.wait_timer.cancel()
            self.wait_timer = None

        if self.state == State.WAIT_KITCHEN:
            self.state = State.GO_TABLE
            self.send_goal(self.current_table)

    # =========================================================
    # AFTER TABLE WAIT
    # =========================================================
    def after_table(self):
        if self.wait_timer:
            self.wait_timer.cancel()
            self.wait_timer = None

        if self.state == State.WAIT_TABLE:
            self.current_table = None
            self.check_queue_or_home()

    # =========================================================
    # CHAINING LOGIC
    # =========================================================
    def check_queue_or_home(self):

        if self.queue:
            next_table = self.queue.popleft()
            self.start_order(next_table)
        else:
            self.state = State.GO_HOME
            self.send_goal("dock")


# =========================================================
# MAIN
# =========================================================
def main(args=None):
    rclpy.init(args=args)
    node = Butler()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()