#!/usr/bin/env python3
"""
MAVSDK link test (PX4-friendly).

What it does:
- Connects to the vehicle
- Waits for connection
- Prints basic info (if available)
- Prints a few telemetry samples to prove the link is alive

Example:
  uv run pixhawk_link_test.py --system-address udpin://0.0.0.0:14540 --samples 20
"""

import argparse
import asyncio

from mavsdk import System


async def main_async(system_address: str, samples: int) -> None:
    drone = System()
    await drone.connect(system_address=system_address)

    async for state in drone.core.connection_state():
        if state.is_connected:
            print("Connected")
            break

    # Best-effort: some stacks/links may not provide everything.
    try:
        version = await drone.info.get_version()
        print(
            "Autopilot: "
            f"{version.flight_sw_major}.{version.flight_sw_minor}.{version.flight_sw_patch} "
            f"(vendor={version.vendor_version})"
        )
    except Exception as e:
        print(f"Info/version not available: {e}")

    try:
        ident = await drone.info.get_identification()
        print(f"Identification: hw_uid={getattr(ident, 'hardware_uid', '<unknown>')}")
    except Exception as e:
        print(f"Info/identification not available: {e}")

    # Telemetry samples
    got = 0
    async for attitude in drone.telemetry.attitude_euler():
        print(
            f"ATT r={attitude.roll_deg:.1f} p={attitude.pitch_deg:.1f} y={attitude.yaw_deg:.1f}"
        )
        got += 1
        if got >= samples:
            break

    print("✅ Link test finished")


def main() -> None:
    parser = argparse.ArgumentParser(description="MAVSDK link test")
    parser.add_argument(
        "--system-address",
        default="udpin://0.0.0.0:14540",
        help='MAVSDK system address (e.g. "udp://:14540", "udpin://0.0.0.0:14540", "serial:///dev/ttyS0:57600")',
    )
    parser.add_argument("--samples", type=int, default=20, help="Number of telemetry samples to print")
    args = parser.parse_args()

    asyncio.run(main_async(system_address=args.system_address, samples=args.samples))


if __name__ == "__main__":
    main()


