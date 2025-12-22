#!/usr/bin/env python3
"""
Pixhawk 6C <-> Raspberry Pi link test (ArduPilot, MAVLink over TELEM).

- Connects to Pixhawk via serial
- Waits for MAVLink heartbeat
- Prints basic autopilot/system info
- Reads some ArduPilot params (SERIAL1_PROTOCOL / SERIAL1_BAUD)
- Streams a few MAVLink messages to verify link health

Test with e.g.:
    uv run pixhawk_link_test.py --port /dev/ttyS0 --baud 57600
or:
    uv run pixhawk_link_test.py --port /dev/ttyS0 --baud 921600
depending on how TELEM1 is configured in ArduPilot.
"""

from pymavlink import mavutil
import argparse
import sys
import time


def request_param(master, sys_id, comp_id, name: str, timeout: float = 3.0):
    """
    Request a single ArduPilot parameter by name and wait for PARAM_VALUE.

    Returns the PARAM_VALUE message or None on timeout.
    """
    # param_id must be max 16 chars, padded with null bytes
    param_id_bytes = name.encode("ascii")
    if len(param_id_bytes) > 16:
        param_id_bytes = param_id_bytes[:16]
    param_id_bytes = param_id_bytes.ljust(16, b"\x00")

    master.mav.param_request_read_send(
        sys_id,
        comp_id,
        param_id_bytes,
        -1,  # param_index = -1 means "use param_id"
    )

    start = time.time()
    while time.time() - start < timeout:
        msg = master.recv_match(type="PARAM_VALUE", blocking=True, timeout=timeout)
        if msg is None:
            continue
        if msg.param_id.decode(errors="ignore").strip("\x00") == name:
            return msg
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Test MAVLink connection to ArduPilot (Pixhawk 6C) from Raspberry Pi"
    )
    parser.add_argument(
        "--port",
        default="/dev/ttyS0",  # on your Pi: serial0 -> ttyS0
        help="Serial device (e.g. /dev/ttyS0, /dev/ttyAMA0, /dev/ttyUSB0)",
    )
    parser.add_argument(
        "--baud",
        type=int,
        default=57600,  # very common default for ArduPilot TELEM ports
        help="Baud rate (e.g. 57600, 115200, 921600)",
    )
    parser.add_argument(
        "--messages",
        type=int,
        default=20,
        help="Number of MAVLink messages to print after heartbeat",
    )

    args = parser.parse_args()

    print(f"Opening MAVLink on {args.port} @ {args.baud} baud")

    try:
        master = mavutil.mavlink_connection(
            args.port,
            baud=args.baud,
            autoreconnect=False,
        )
    except Exception as e:
        print(f"[ERROR] Failed to open serial port: {e}")
        sys.exit(1)

    print("Waiting for heartbeat (10s timeout)...")
    try:
        hb = master.wait_heartbeat(timeout=10)
    except Exception as e:
        print(f"[ERROR] Exception while waiting for heartbeat: {e}")
        sys.exit(1)

    if hb is None:
        print(
            "[ERROR] No heartbeat received.\n"
            "- Check TX/RX are crossed (Pixhawk TX -> Pi RX, Pixhawk RX -> Pi TX)\n"
            "- Check GND is common between Pixhawk and Pi\n"
            "- Confirm TELEM1 is configured for MAVLink (ArduPilot SERIALx_PROTOCOL=1 or 2)\n"
            "- Confirm TELEM1 baud (SERIALx_BAUD) matches the --baud you used\n"
            "- Make sure Pixhawk is fully powered and ArduPilot is running"
        )
        sys.exit(1)

    sys_id = hb.get_srcSystem()
    comp_id = hb.get_srcComponent()

    print("✅ Heartbeat received")
    print(f"  System ID:    {sys_id}")
    print(f"  Component ID: {comp_id}")
    print(f"  Heartbeat type: {hb.type}, autopilot: {hb.autopilot}, base_mode: {hb.base_mode}")

    # Optional: ask ArduPilot for some key SERIAL1 params, useful to verify config
    print("\nQuerying ArduPilot serial params (for TELEM1 = SERIAL1_*)...")

    for pname in ("SERIAL1_PROTOCOL", "SERIAL1_BAUD"):
        try:
            pmsg = request_param(master, sys_id, comp_id, pname, timeout=3.0)
            if pmsg is None:
                print(f"  {pname}: <no response>")
            else:
                print(
                    f"  {pname}: value={pmsg.param_value} index={pmsg.param_index} type={pmsg.param_type}"
                )
        except Exception as e:
            print(f"  {pname}: error requesting param: {e}")

    # Request data stream (ArduPilot will usually send useful data anyway, but this is fine)
    print("\nRequesting data stream at ~10 Hz...")
    try:
        master.mav.request_data_stream_send(
            sys_id,
            comp_id,
            mavutil.mavlink.MAV_DATA_STREAM_ALL,
            10,  # Hz
            1,   # start
        )
    except Exception as e:
        print(f"Warning: failed to request data stream: {e}")

    print(f"\nReading {args.messages} MAVLink messages… (Ctrl+C to abort)\n")

    count = 0
    try:
        while count < args.messages:
            msg = master.recv_match(blocking=True, timeout=5)
            if msg is None:
                print("[WARN] Timeout waiting for message")
                continue
            # Print simple timestamped message
            print(f"[{time.strftime('%H:%M:%S')}] {msg.get_type()}: {msg.to_dict()}")
            count += 1
    except KeyboardInterrupt:
        print("\nInterrupted by user.")

    print("\n✅ Link test finished. If you saw regular messages, the Pi <-> Pixhawk MAVLink link is working.")


if __name__ == "__main__":
    main()
