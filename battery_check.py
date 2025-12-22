#!/usr/bin/env python3
"""
Read Pixhawk battery status via MAVLink (ArduPilot).
Shows:
 - Battery voltage (V)
 - Battery current (A)
 - Estimated remaining (%)

Requires pymavlink + pyserial
"""

from pymavlink import mavutil
import argparse
import sys

parser = argparse.ArgumentParser(description="Pixhawk battery monitor")
parser.add_argument("--port", default="/dev/ttyS0", help="Serial device")
parser.add_argument("--baud", type=int, default=57600, help="Baud rate")
parser.add_argument("--count", type=int, default=20, help="Number of updates to print")
args = parser.parse_args()

print(f"Connecting to {args.port} @ {args.baud}...")
try:
    master = mavutil.mavlink_connection(args.port, baud=args.baud)
except Exception as e:
    print(f"[ERROR] Failed to open port: {e}")
    sys.exit(1)

print("Waiting for heartbeat...")
hb = master.wait_heartbeat(timeout=10)
if hb is None:
    print("[ERROR] No heartbeat received")
    sys.exit(1)

print("Heartbeat OK — reading battery values\n")

count = 0
while count < args.count:
    msg = master.recv_match(type="SYS_STATUS", blocking=True, timeout=5)
    if msg is None:
        print("No battery data (timeout)")
        continue

    voltage_mv = msg.voltage_battery     # millivolts
    current_cA = msg.current_battery     # centi-amps
    remaining = msg.battery_remaining    # percent (−1 if unknown)

    voltage_v = voltage_mv / 1000.0
    current_a = current_cA / 100.0 if current_cA != -1 else None

    out = f"Voltage: {voltage_v:.2f} V"
    if current_a is not None:
        out += f" | Current: {current_a:.2f} A"
    if remaining != -1:
        out += f" | Remaining: {remaining}%"

    print(out)
    count += 1
