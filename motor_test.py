#!/usr/bin/env python3
"""
Native ArduCopter Motor Test from Raspberry Pi using MAV_CMD_DO_MOTOR_TEST.

- Does NOT require arming
- Spins ONE motor at a percentage for a duration
- Uses correct throttle type (0 = percentage)

USE ONLY WITH PROPS REMOVED.
"""

from pymavlink import mavutil
import argparse
import sys
import time

def main():
    parser = argparse.ArgumentParser(description="ArduCopter Native Motor Test (fixed)")
    parser.add_argument("--port", default="/dev/ttyS0")
    parser.add_argument("--baud", type=int, default=57600)
    parser.add_argument("--motor", type=int, default=1, help="Motor number (1..4 for quad)")
    parser.add_argument("--percent", type=float, default=20.0, help="Power % (1–100)")
    parser.add_argument("--duration", type=float, default=3.0, help="Seconds to spin motor")
    args = parser.parse_args()

    if not (1 <= args.percent <= 100):
        print("[ERROR] percent must be between 1 and 100")
        sys.exit(1)

    print(f"Connecting to {args.port} @ {args.baud}")
    try:
        master = mavutil.mavlink_connection(args.port, baud=args.baud)
    except Exception as e:
        print(f"[ERROR] Failed to open port: {e}")
        sys.exit(1)

    print("Waiting for heartbeat…")
    hb = master.wait_heartbeat(timeout=10)
    if hb is None:
        print("[ERROR] No heartbeat — aborting")
        sys.exit(1)

    print(f"✅ Heartbeat from system {hb.get_srcSystem()}, component {hb.get_srcComponent()}")

    # Most GCSs send this to the autopilot component (1), so let's do the same.
    target_system = master.target_system
    target_component = master.target_component  # usually MAV_COMP_ID_AUTOPILOT1

    print(
        f"Requesting motor test: motor={args.motor}, "
        f"power={args.percent}%, duration={args.duration}s"
    )

    # Throttle type 0 = percentage (correct)
    THROTTLE_TYPE_PERCENT = 0

    master.mav.command_long_send(
        target_system,
        target_component,
        mavutil.mavlink.MAV_CMD_DO_MOTOR_TEST,
        0,
        args.motor,                # param1: motor number (1..N)
        THROTTLE_TYPE_PERCENT,     # param2: throttle type (0 = percentage)
        args.percent,              # param3: throttle % (0–100)
        args.duration,             # param4: timeout (seconds)
        0,                         # param5: motor_count (0 = 1 motor)
        0,                         # param6: test_order (0 = default)
        0                          # param7: test_flags (0 = default)
    )

    print("Command sent. Listening for feedback…\n")

    end_time = time.time() + args.duration + 5
    while time.time() < end_time:
        msg = master.recv_match(type=["STATUSTEXT", "COMMAND_ACK"], blocking=True, timeout=1)
        if msg is None:
            continue

        if msg.get_type() == "STATUSTEXT":
            text = getattr(msg, "text", "")
            print(f"[STATUSTEXT] {msg.severity}: {text}")

        elif msg.get_type() == "COMMAND_ACK":
            print(f"[COMMAND_ACK] command={msg.command}, result={msg.result}")

    print("\nDone. If you didn't have props on, you should have HEARD/SEEN the motor spin.")


if __name__ == "__main__":
    main()
