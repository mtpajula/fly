#!/usr/bin/env python3
"""
Battery status via MAVSDK.

Example:
  uv run battery_check.py --system-address udpin://0.0.0.0:14540 --count 20
"""

import argparse
import asyncio

from mavsdk import System


async def main_async(system_address: str, count: int) -> None:
    drone = System()
    await drone.connect(system_address=system_address)

    async for state in drone.core.connection_state():
        if state.is_connected:
            print("Connected")
            break

    printed = 0
    try:
        async with asyncio.timeout(10):
            async for batt in drone.telemetry.battery():
                voltage_v = getattr(batt, "voltage_v", None)
                remaining_percent = getattr(batt, "remaining_percent", None)

                parts: list[str] = []
                if voltage_v is not None:
                    parts.append(f"Voltage: {voltage_v:.2f} V")
                    if 6.0 <= voltage_v <= 26.0:
                        cells = max(1, min(8, round(voltage_v / 4.2)))
                        per_cell = voltage_v / cells
                        parts.append(f"~{cells}S ({per_cell:.2f} V/cell)")
                if remaining_percent is not None:
                    if remaining_percent <= 1.0:
                        pct = remaining_percent * 100.0
                    else:
                        pct = remaining_percent
                        if pct > 100.0 and pct <= 10000.0:
                            pct = pct / 100.0
                    pct = max(0.0, min(100.0, pct))
                    parts.append(f"Remaining: {pct:.0f}%")

                if not parts:
                    print("Battery: <no data>")
                else:
                    print(" | ".join(parts))

                printed += 1
                if printed >= count:
                    break
    except TimeoutError:
        print("Timed out waiting for BATTERY_STATUS — autopilot may not be streaming it on this link.")
        print("Check ArduPilot stream rate: set SRx_EXT_STAT >= 1 (x = serial port number, e.g. SR2_EXT_STAT=2 for SERIAL2).")


def main() -> None:
    parser = argparse.ArgumentParser(description="Battery monitor via MAVSDK")
    parser.add_argument(
        "--system-address",
        default="serial:///dev/ttyS0:57600",
        help='MAVSDK system address (e.g. "udp://:14540", "udpin://0.0.0.0:14540", "serial:///dev/ttyS0:57600")',
    )
    parser.add_argument("--count", type=int, default=20, help="Number of updates to print")
    args = parser.parse_args()

    asyncio.run(main_async(system_address=args.system_address, count=args.count))


if __name__ == "__main__":
    main()
