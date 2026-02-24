#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import os

class StatusMonitor(Node):

    def __init__(self):
        super().__init__('status_monitor')

        self.create_subscription(
            String,
            '/butler_status',
            self.callback,
            10
        )
    
    def callback(self, msg):
        os.system('clear')
        print(msg.data)
    
def main(args=None):
    rclpy.init(args=args)
    node = StatusMonitor()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()