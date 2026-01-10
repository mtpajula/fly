import argparse
import asyncio

from mavsdk import System
try:
    from mavsdk.action import ActionError
except Exception:  # pragma: no cover
    ActionError = Exception  # type: ignore[misc,assignment]


async def _print_status_text(drone: System, stop: asyncio.Event) -> None:
    """Print STATUSTEXT messages (PX4 prearm/arming-check hints show up here)."""
    try:
        async for st in drone.telemetry.status_text():
            if stop.is_set():
                return
            text = getattr(st, "text", "")
            stype = getattr(st, "type", "")
            if text:
                prefix = f"[STATUSTEXT] {stype}".strip()
                print(f"{prefix} {text}".strip())
    except Exception:
        # Best-effort only; telemetry stream may not be available in some setups.
        return


async def _print_health_once(drone: System) -> None:
    """Print one health snapshot (field names can vary by MAVSDK version)."""
    try:
        async for health in drone.telemetry.health():
            fields = [
                "is_gyrometer_calibration_ok",
                "is_accelerometer_calibration_ok",
                "is_magnetometer_calibration_ok",
                "is_level_calibration_ok",
                "is_local_position_ok",
                "is_global_position_ok",
                "is_home_position_ok",
            ]
            parts: list[str] = []
            for f in fields:
                if hasattr(health, f):
                    parts.append(f"{f.replace('is_', '').replace('_', ' ')}={getattr(health, f)}")
            if parts:
                print("[HEALTH] " + " | ".join(parts))
            break
    except Exception:
        return


async def _wait_until_in_air(drone: System, timeout_s: float) -> bool:
    """Return True once telemetry reports in_air=True, else False on timeout."""
    start = asyncio.get_event_loop().time()
    async for in_air in drone.telemetry.in_air():
        if in_air:
            return True
        if asyncio.get_event_loop().time() - start >= timeout_s:
            return False


async def hop(system_address: str, hover_seconds: float, takeoff_alt_m: float) -> None:
    drone = System()
    await drone.connect(system_address=system_address)

    async for state in drone.core.connection_state():
        if state.is_connected:
            print("Connected")
            break

    stop_status = asyncio.Event()
    status_task = asyncio.create_task(_print_status_text(drone, stop_status))

    async for health in drone.telemetry.health():
        if health.is_global_position_ok and health.is_home_position_ok:
            print("Ready")
            break

    await _print_health_once(drone)

    # Indoors: set a low takeoff altitude explicitly (PX4 otherwise uses its own default).
    takeoff_alt_m = max(0.3, float(takeoff_alt_m))
    try:
        await drone.action.set_takeoff_altitude(takeoff_alt_m)
        print(f"[INFO] Takeoff altitude set to {takeoff_alt_m:.2f} m")
    except Exception as e:
        print(f"[WARN] Failed to set takeoff altitude ({takeoff_alt_m:.2f} m): {e}")

    try:
        await drone.action.arm()
    except ActionError as e:
        print(f"[ERROR] arm() failed: {e}")
        print(
            "[HINT] PX4 denied arming. Common causes:\n"
            "- Safety switch still ON (press safety button / disable safety)\n"
            "- Prearm checks failing (watch [STATUSTEXT] lines above for the exact reason)\n"
            "- RC requirements / arming checks / EKF not ready"
        )
        # Give status_text a moment to flush any last prearm messages
        await asyncio.sleep(2.0)
        stop_status.set()
        await status_task
        raise

    await drone.action.takeoff()

    # Don't start the hover timer until PX4 actually considers the vehicle airborne.
    in_air = await _wait_until_in_air(drone, timeout_s=10.0)
    if not in_air:
        print("[ERROR] takeoff() sent, but vehicle never became 'in_air' within 10s.")
        print("[HINT] Indoors this is commonly thrust/props/motor-direction or land-detector tuning.")
        try:
            await drone.action.disarm()
        except Exception:
            pass
        stop_status.set()
        await status_task
        return

    await asyncio.sleep(hover_seconds)

    await drone.action.land()

    async for in_air in drone.telemetry.in_air():
        if not in_air:
            break

    await drone.action.disarm()
    print("Done")
    stop_status.set()
    await status_task


def main() -> None:
    parser = argparse.ArgumentParser(description="Simple MAVSDK hop: arm, takeoff, wait, land, disarm.")
    parser.add_argument(
        "--system-address",
        default="serial:///dev/ttyS0:57600",
        help='MAVSDK system address (e.g. "udp://:14540", "udpin://0.0.0.0:14540", "serial:///dev/ttyS0:57600")',
    )
    parser.add_argument("--hover-seconds", type=float, default=5.0, help="Seconds to wait after takeoff before landing")
    parser.add_argument(
        "--takeoff-alt-m",
        type=float,
        default=0.5,
        help="Takeoff altitude in meters (indoors default: 0.5m). Will be clamped to >= 0.3m.",
    )
    args = parser.parse_args()

    asyncio.run(
        hop(
            system_address=args.system_address,
            hover_seconds=args.hover_seconds,
            takeoff_alt_m=args.takeoff_alt_m,
        )
    )


if __name__ == "__main__":
    main()