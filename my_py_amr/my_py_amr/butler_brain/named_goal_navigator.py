#!/usr/bin/env python3

import math
from enum import Enum
from collections import deque

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient

from std_msgs.msg import String
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose
from action_msgs.msg import GoalStatus


# =====================================================
# STATES
# =====================================================
class State(Enum):
    IDLE = 0
    GO_KITCHEN = 1
    WAIT_KITCHEN = 2
    GO_TABLE = 3
    WAIT_TABLE = 4
    RETURN_TO_KITCHEN_AFTER_CANCEL = 5
    GO_DOCK = 6


# =====================================================
# BUTLER NODE
# =====================================================
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

        # ---------------- State Variables ----------------
        self.state = State.IDLE
        self.current_table = None
        self.queue = deque()
        self.goal_handle = None
        self.wait_timer = None
        self.cancel_pending = False

        # ---------------- Nav2 Client ----------------
        self.action_client = ActionClient(
            self, NavigateToPose, 'navigate_to_pose'
        )

        # ---------------- Subscribers ----------------
        self.create_subscription(
            String, '/go_to_location',
            self.order_callback, 10)

        self.create_subscription(
            String, '/cancel_order',
            self.cancel_callback, 10)

        # ---------------- Status Publisher ----------------
        self.status_pub = self.create_publisher(
            String, '/butler_status', 10)

        self.create_timer(0.5, self.publish_status)

        self.get_logger().info("✅ Butler - Fully Stable Version Running")

    # =====================================================
    # STATUS PUBLISHER
    # =====================================================
    def publish_status(self):

        msg = String()
        msg.data = (
            f"\n========== BUTLER STATUS ==========\n"
            f"State          : {self.state.name}\n"
            f"Current Table  : {self.current_table}\n"
            f"Queue          : {list(self.queue)}\n"
            f"Goal Active    : {self.goal_handle is not None}\n"
            f"Cancel Pending : {self.cancel_pending}\n"
            f"===================================\n"
        )

        self.status_pub.publish(msg)

    # =====================================================
    # ORDER CALLBACK
    # =====================================================
    def order_callback(self, msg):
        table = msg.data.strip().lower()

        if table not in self.valid_tables:
            self.get_logger().error(f"Invalid table: {table}")
            return

        if self.state == State.IDLE:
            self.start_order(table)
        else:
            self.queue.append(table)
            self.get_logger().info(f"Queued: {table}")

    # =====================================================
    # CANCEL CALLBACK
    # =====================================================
    def cancel_callback(self, msg):

        if self.state == State.IDLE:
            return

        self.get_logger().warn("⚠ Cancel requested")

        self.cancel_pending = True

        if self.wait_timer:
            self.wait_timer.cancel()
            self.wait_timer = None

        if self.goal_handle:
            self.goal_handle.cancel_goal_async()

    # =====================================================
    # START ORDER
    # =====================================================
    def start_order(self, table):
        self.current_table = table
        self.state = State.GO_KITCHEN
        self.send_goal("kitchen")

    # =====================================================
    # SEND NAV GOAL
    # =====================================================
    def send_goal(self, location_name):

        if self.goal_handle:
            return

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

        self.get_logger().info(f"➡ Navigating to {location_name}")

        future = self.action_client.send_goal_async(goal)
        future.add_done_callback(self.goal_response)

    def goal_response(self, future):
        self.goal_handle = future.result()

        if not self.goal_handle.accepted:
            self.get_logger().error("Goal rejected")
            self.goal_handle = None
            return

        result_future = self.goal_handle.get_result_async()
        result_future.add_done_callback(self.goal_result)

    # =====================================================
    # GOAL RESULT HANDLER
    # =====================================================
    def goal_result(self, future):

        result = future.result()
        status = result.status
        self.goal_handle = None

        # ---------------- Handle Cancel ----------------
        if status == GoalStatus.STATUS_CANCELED:

            self.get_logger().info("Goal was canceled")

            if self.state in [State.GO_TABLE, State.WAIT_TABLE]:
                self.state = State.RETURN_TO_KITCHEN_AFTER_CANCEL
                self.send_goal("kitchen")
                return

            if self.state in [State.GO_KITCHEN, State.WAIT_KITCHEN]:
                self.current_table = None
                self.cancel_pending = False
                self.check_queue_or_idle()
                return

        # ---------------- Handle Success ----------------
        if status == GoalStatus.STATUS_SUCCEEDED:

            if self.state == State.GO_KITCHEN:
                self.state = State.WAIT_KITCHEN
                self.wait_timer = self.create_timer(5.0, self.after_kitchen)
                return

            if self.state == State.GO_TABLE:
                self.state = State.WAIT_TABLE
                self.wait_timer = self.create_timer(5.0, self.after_table)
                return

            if self.state == State.RETURN_TO_KITCHEN_AFTER_CANCEL:
                self.current_table = None
                self.cancel_pending = False
                self.check_queue_or_idle()
                return

            if self.state == State.GO_DOCK:
                self.state = State.IDLE
                return

    # =====================================================
    # WAIT CALLBACKS
    # =====================================================
    def after_kitchen(self):

        if self.wait_timer:
            self.wait_timer.cancel()
            self.wait_timer = None

        if self.cancel_pending:
            self.current_table = None
            self.cancel_pending = False
            self.check_queue_or_idle()
            return

        self.state = State.GO_TABLE
        self.send_goal(self.current_table)

    def after_table(self):

        if self.wait_timer:
            self.wait_timer.cancel()
            self.wait_timer = None

        self.current_table = None
        self.check_queue_or_idle()

    # =====================================================
    # QUEUE HANDLER
    # =====================================================
    def check_queue_or_idle(self):

        if self.queue:
            next_table = self.queue.popleft()
            self.start_order(next_table)
        else:
            self.state = State.GO_DOCK
            self.send_goal("dock")


# =====================================================
# MAIN
# =====================================================
def main(args=None):
    rclpy.init(args=args)
    node = Butler()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()