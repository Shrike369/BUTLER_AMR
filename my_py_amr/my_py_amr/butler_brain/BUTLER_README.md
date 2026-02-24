# 🤖 Goat Robotics Butler Robot project – Autonomous Restaurant Delivery System 

This Butler Robot project was developed as part of my technical interview process with Goat Robotics. The goal was to design a simple, reliable autonomous delivery system using ROS 2 and and showcase with Simulation.

Within three focused days, I built a structured solution that handles order requests, manages a queue, supports safe cancellation, and maintains clear state transitions. My main focus was to ensure the system is clean, logical, and robust rather than overcomplicated.

## Core Function

The Butler Robot:
- Accepts table orders
- Navigates to the kitchen
- Picks up items
- Delivers to tables
- Handles order cancellation safely
- Manages multiple queued orders
- Returns to dock when idle
- Publishes real-time system status

---

## 📌 Table of Contents

1. Project Overview  
2. System Architecture  
3. Features  
4. Finite State Machine (FSM) Design  
5. Workflow  
6. Topics  
7. Nodes  
8. Order Handling Logic  
9. Cancellation Logic  
10. Status Monitoring  
11. Usage
12. Example Commands  
13. Project Structure  
  

---

## 1️⃣ Project Overview

The Butler Robot is a ROS 2-based autonomous delivery robot that simulates restaurant service automation.

It operates using:
- Event-driven architecture
- Finite State Machine control logic
- Order queue management
- Safe cancellation handling
- Real-time status broadcasting

The system ensures:
- Deterministic behavior
- Robust handling of multiple orders
- Safe interruption and recovery
- Clear state tracking

---

## 2️⃣ System Architecture

```
To Order User uses → /go_to_location topic
To cancel User uses → /cancel_order topic

butler Node (FSM Controller)
        ↓
Nav2 Action Client (NavigateToPose)
        ↓
Robot Movement

status_monitor Node
        ↓
/butler_status topic
        ↓
Status Monitor 
```

---

## 3️⃣ Features

- ✅ Autonomous kitchen-to-table delivery
- ✅ Multiple order queue support
- ✅ Safe order cancellation at any state
- ✅ Automatic return to dock when idle
- ✅ Real-time status publishing
- ✅ Deterministic Finite State Machine

---

## 4️⃣ Finite State Machine (FSM)

### States

- `IDLE`
- `GO_KITCHEN`
- `WAIT_KITCHEN`
- `GO_TABLE`
- `WAIT_TABLE`
- `GO_HOME`
- `RETURNING_TO_KITCHEN_CANCELLED`

#### State Transition Overview

```
IDLE
  ↓ Order Received
GO_KITCHEN
  ↓
WAIT_KITCHEN
  ↓
GO_TABLE
  ↓
WAIT_TABLE
  ↓
Check Queue
  ↓
GO_HOME (if no Queue)
```

Cancel Event (from any active state):

```
Cancel
  ↓
RETURNING_TO_KITCHEN_CANCELLED
  ↓
Check Queue
```

---

## 5️⃣ Operational Workflow

### Normal Delivery

1. Order received
2. Navigate to kitchen
3. Wait (loading simulation)
4. Navigate to table
5. Wait (delivery simulation)
6. Check queue
7. Go home if no pending orders

### Multiple Orders

- If robot is busy:  
  New orders are added to a queue  
  After current delivery, next order automatically starts

### Cancellation

- If cancel is received:  
  Current navigation is stopped  
  Wait timers are cancelled  
  Robot safely returns to kitchen  
  If queue exists → continues with next order  
  If no queue → returns to dock

---

## 6️⃣ ROS Topics

### Subscribed Topics

#### `/go_to_location`
Type: `std_msgs/String`  
Example:
```
table1
```

#### `/cancel_order`
Type: `std_msgs/String`  
Example:
```
cancel
```

### Published Topics

#### `/butler_status`
Type: `std_msgs/String`  
Published every 0.5 seconds.  
Example:
```
STATE: GO_TABLE | CURRENT: table2 | QUEUE: ['table3']
```

---

## 7️⃣ Nodes

### Butler Node

Main controller node.

Responsibilities:
- Manages FSM
- Handles order queue
- Sends navigation goals
- Handles cancellation
- Publishes system status

### Optional Status Monitor Node

Subscribes to `/butler_status` and displays current robot activity.

---

## 8️⃣ Order Handling Logic

If robot is:
- `IDLE` → Start immediately
- Busy → Add to queue

Queue uses FIFO (First-In-First-Out) policy.

---

## 9️⃣ Cancellation Logic

Cancel can occur during:
- Navigation to kitchen
- Waiting in kitchen
- Navigation to table
- Waiting at table

System guarantees:
- Safe interruption
- No partial delivery
- Controlled state recovery

---

## 🔟 Status Monitoring

The robot continuously publishes:
- Current state
- Active order
- Pending queue

This ensures:
- Transparency
- Debugging support
- Real-time monitoring
- Easy integration with dashboards

---

## 1️⃣1️⃣ Usage

Launch the system:
```bash
ros2 launch my_py_amr camera_bridge_launch.py
```

Send an order:
```bash
ros2 topic pub --once /go_to_location std_msgs/String "data: 'table1'"
```
just change the table number for differnt table order

Cancel order:
```bash
ros2 topic pub --once /cancel_order std_msgs/String "data: 'cancel'"
```

Monitor status:
```bash
ros2 run my_py_amr status_monitor
```

---

## 1️⃣2️⃣ Example Scenario

Example:
1. Send order: table1
2. Send order: table2
3. Robot delivers table1
4. Automatically continues to table2
5. No more orders
6. Returns to dock

---

## 1️⃣3️⃣ Project Structure

```
my_py_amr/
│
├── launch/
│   └── camera_bridge_launch.py
│
├── my_py_amr/
│   ├── butler_brain/
│   │   ├── __init__.py
│   │   ├── named_goal_navigator.py
│   │   ├── status_monitor.py
│   │   └── README.md
│   │
│   ├── camera_bridge_node.py
│   ├── image_to_occupancy.py
│   ├── republish_cmd_vel.py
│   ├── republish_joint_states.py
│   ├── republish_odometry.py
│   ├── top_down_marker_tf.py
│   └── __init__.py
│
├── params/
│   └── nav2_params.yaml
│
├── resource/
│
├── package.xml
├── setup.py
├── setup.cfg
├── requirement.txt
├── README.md
└── .gitignore
```

## 🎯 Conclusion

I developed this project over three dedicated days, giving it my full focus and effort. My priority was to meet the problem statement clearly and build a system that is stable, understandable, and well-structured.

There are certainly more features that could be added with more time, but within the given timeframe, I aimed to deliver a solid foundation that reflects my approach to robotics system design.

I hope you find this project interesting, and I genuinely enjoyed working on this challenge.

Thank you for your time and consideration🙂.