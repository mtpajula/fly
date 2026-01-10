import argparse
import asyncio

from mavsdk import System


async def hop(system_address: str, hover_seconds: float) -> None:
    drone = System()
    await drone.connect(system_address=system_address)

    async for state in drone.core.connection_state():
        if state.is_connected:
            print("Connected")
            break

    async for health in drone.telemetry.health():
        if health.is_global_position_ok and health.is_home_position_ok:
            print("Ready")
            break

    await drone.action.arm()
    await drone.action.takeoff()

    await asyncio.sleep(hover_seconds)

    await drone.action.land()

    async for in_air in drone.telemetry.in_air():
        if not in_air:
            break

    await drone.action.disarm()
    print("Done")


def main() -> None:
    parser = argparse.ArgumentParser(description="Simple MAVSDK hop: arm, takeoff, wait, land, disarm.")
    parser.add_argument(
        "--system-address",
        default="udpin://0.0.0.0:14540",
        help='MAVSDK system address (e.g. "udp://:14540", "udpin://0.0.0.0:14540", "serial:///dev/ttyS0:57600")',
    )
    parser.add_argument("--hover-seconds", type=float, default=5.0, help="Seconds to wait after takeoff before landing")
    args = parser.parse_args()

    asyncio.run(hop(system_address=args.system_address, hover_seconds=args.hover_seconds))


if __name__ == "__main__":
    main()