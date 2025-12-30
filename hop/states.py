# first_hop/states.py

import time
from abc import ABC, abstractmethod
from typing import Optional

from . import config


class State(ABC):
    """Base class for all states."""

    name: str = "BASE"

    def on_enter(self, ctx) -> None:
        """Called once when the state becomes active."""
        pass

    @abstractmethod
    def step(self, ctx) -> "State":
        """
        Called every tick.
        Return:
          - self to stay in the same state
          - a new State instance to transition
        """
        raise NotImplementedError

    def hint(self, ctx) -> str:
        """Short instruction for the user."""
        return ""


# ---------- Concrete states ----------


class WaitHeartbeatState(State):
    name = "WAIT_HEARTBEAT"

    def on_enter(self, ctx) -> None:
        ctx.log("[FSM] Waiting for heartbeat...")
        ctx.log(">> Power Pixhawk and ensure telemetry link is connected.")

    def step(self, ctx) -> State:
        ok = ctx.drone.wait_heartbeat(timeout=1.0)
        if ok:
            ctx.log("[FSM] Heartbeat OK. Requesting telemetry streams.")
            ctx.drone.request_basic_data_streams()
            return SetModeGuidedNogpsState()
        return self

    def hint(self, ctx) -> str:
        return "Power Pixhawk and wait for connection."


class SetModeGuidedNogpsState(State):
    name = "SET_MODE_GUIDED_NOGPS"

    def __init__(self) -> None:
        self.mode_sent = False

    def on_enter(self, ctx) -> None:
        ctx.log("[FSM] Entering SET_MODE_GUIDED_NOGPS")

    def step(self, ctx) -> State:
        if not self.mode_sent:
            ctx.log("[FSM] Sending mode GUIDED_NOGPS (mode_id=%d)", config.GUIDED_NOGPS_MODE)
            ctx.drone.set_mode_custom(config.GUIDED_NOGPS_MODE)
            self.mode_sent = True
            return self

        current_mode = ctx.drone.get_mode()
        if current_mode == str(config.GUIDED_NOGPS_MODE):
            ctx.log("[FSM] Mode confirmed: %s", current_mode)
            return ArmState()

        if ctx.elapsed >= config.MODE_CHANGE_WAIT:
            ctx.log("[FSM] Mode change timeout (current=%s), proceeding anyway...", current_mode)
            return ArmState()

        return self

    def hint(self, ctx) -> str:
        return "Waiting for mode to switch to GUIDED_NOGPS."


class ArmState(State):
    name = "ARM"

    def __init__(self) -> None:
        self.arm_sent = False

    def on_enter(self, ctx) -> None:
        ctx.log("[FSM] Entering ARM")
        ctx.log(">> PROPS OFF for initial tests.")

    def step(self, ctx) -> State:
        if not self.arm_sent:
            ctx.log("[FSM] Sending ARM command")
            ctx.drone.arm()
            self.arm_sent = True

            # NEW: read whatever the FC says right after arm request
            ctx.drone.read_status_messages(duration=1.0)
            return self

        # Poll armed flag each loop
        if ctx.drone.is_armed():
            ctx.log("[FSM] Vehicle reports ARMED")
            return SpinMotorsState()

        # Also periodically read status while waiting
        ctx.drone.read_status_messages(duration=0.1)

        if ctx.elapsed > config.ARMING_TIMEOUT:
            ctx.log("[FSM] Arming timeout -> ABORT")
            return AbortState()

        return self

    def hint(self, ctx) -> str:
        return "Vehicle is arming. Keep props OFF and wait."


class SpinMotorsState(State):
    name = "SPIN_MOTORS"

    def __init__(self):
        self.start = None

    def on_enter(self, ctx) -> None:
        self.start = time.time()
        ctx.log("[FSM] Entering SPIN_MOTORS")
        ctx.log(">> Props OFF. Motors will spin using SET_ATTITUDE_TARGET thrust.")
        ctx.log(
            f"[FSM] Spin thrust={config.SPIN_THRUST:.2f}, "
            f"duration={config.SPIN_DURATION:.1f}s"
        )
        ctx.log(f"[FSM] is_armed at SPIN_MOTORS entry: {ctx.drone.is_armed()}")

    def step(self, ctx) -> State:
        # If not armed, we can't spin. Check + show why.
        if not ctx.drone.is_armed():
            ctx.log("[FSM] WARNING: Vehicle is NOT ARMED during SPIN_MOTORS")
            ctx.drone.read_status_messages(duration=0.2)
            return self

        # Send SET_ATTITUDE_TARGET thrust
        ctx.drone.set_thrust(config.SPIN_THRUST)

        # Optional: read any status text while spinning
        ctx.drone.read_status_messages(duration=0.05)

        # Stop after configured duration
        if time.time() - self.start > config.SPIN_DURATION:
            ctx.log("[FSM] Spin test complete")
            # Clear thrust by sending 0
            ctx.drone.set_thrust(0.0)
            return WaitForAscentState()

        return self

    def hint(self, ctx) -> str:
        return (
            "Motors should be spinning at low power (props OFF). "
            "Keep the drone firmly restrained and the area clear."
        )


class WaitForAscentState(State):
    name = "WAIT_FOR_ASCENT"

    def on_enter(self, ctx) -> None:
        ctx.log("[FSM] Entering WAIT_FOR_ASCENT")

        # Capture baseline altitude once when we enter this state
        alt = ctx.drone.get_relative_alt(timeout=1.0)
        ctx.ascent_baseline_alt = alt
        if alt is None:
            ctx.log(
                "[FSM] Baseline altitude is unknown (None). "
                "Will still wait for a positive change if data appears."
            )
        else:
            ctx.log(
                f"[FSM] Baseline altitude set to {alt:.3f} m. "
                f"Will detect ascent after +{config.ASCENT_DELTA:.2f} m."
            )

        ctx.log(
            ">> Manually lift drone by about "
            f"{config.ASCENT_DELTA:.2f} m from current height."
        )

    def step(self, ctx) -> State:
        alt = ctx.alt
        base = ctx.ascent_baseline_alt

        if alt is None or base is None:
            # No valid data yet; stay in this state
            return self

        delta = alt - base

        if delta >= config.ASCENT_DELTA:
            ctx.log(
                f"[FSM] Ascent detected: baseline={base:.3f} m, "
                f"current={alt:.3f} m, delta={delta:.3f} m >= "
                f"{config.ASCENT_DELTA:.2f} m"
            )
            ctx.hover_start_time = time.time()
            return HoverState()

        return self

    def hint(self, ctx) -> str:
        return (
            f"Manually lift drone about {config.ASCENT_DELTA:.2f} m "
            "above its starting height."
        )


class HoverState(State):
    name = "HOVER"

    def on_enter(self, ctx) -> None:
        ctx.log("[FSM] Entering HOVER")
        if ctx.hover_start_time is None:
            ctx.hover_start_time = time.time()
        ctx.log(">> Hold the drone at roughly the same height.")

    def step(self, ctx) -> State:
        if ctx.hover_start_time is None:
            ctx.hover_start_time = time.time()

        if time.time() - ctx.hover_start_time >= config.HOVER_TIME:
            ctx.log(
                f"[FSM] Hover time {config.HOVER_TIME:.1f}s reached -> LAND mode"
            )
            return LandState()

        return self

    def hint(self, ctx) -> str:
        return "Hold the drone at roughly the same height for a few seconds."


class LandState(State):
    name = "LAND"

    def __init__(self) -> None:
        self.mode_sent = False

    def on_enter(self, ctx) -> None:
        ctx.log("[FSM] Entering LAND")
        ctx.log(">> Requesting LAND mode; gently bring drone towards ground.")

    def step(self, ctx) -> State:
        if not self.mode_sent:
            ctx.log("[FSM] Setting mode LAND")
            ctx.drone.set_mode_custom(config.LAND_MODE)
            self.mode_sent = True
            return self

        if ctx.elapsed >= config.MODE_CHANGE_WAIT:
            return WaitForGroundedState()

        return self

    def hint(self, ctx) -> str:
        return "LAND mode requested. Gently bring the drone back towards the ground."


class WaitForGroundedState(State):
    name = "WAIT_FOR_GROUNDED"

    def on_enter(self, ctx) -> None:
        ctx.log("[FSM] Entering WAIT_FOR_GROUNDED")
        ctx.log(
            ">> Keep drone descending gently until it is actually on the ground. "
            "FSM will detect when descent stops and altitude is stable."
        )

        # Initialize candidate ground altitude with current reading
        alt = ctx.alt
        ctx.ground_candidate_alt = alt
        ctx.ground_below_threshold_since = None

        if alt is not None:
            ctx.log(
                f"[FSM] Initial ground candidate altitude: {alt:.3f} m "
                f"(will look for stable min within ±{config.GROUND_EPSILON:.2f} m)"
            )
        else:
            ctx.log("[FSM] Altitude unknown on entry; will wait for valid readings.")

    def step(self, ctx) -> State:
        alt = ctx.alt
        cand = ctx.ground_candidate_alt

        if alt is None:
            # no data, can't decide
            return self

        # If we don't have a candidate yet, set one
        if cand is None:
            ctx.ground_candidate_alt = alt
            ctx.ground_below_threshold_since = time.time()
            ctx.log(
                f"[FSM] New ground candidate altitude: {alt:.3f} m "
                f"(starting stability timer)"
            )
            return self

        # If we’ve gone noticeably LOWER than candidate (continuing descent)
        if alt < cand - config.GROUND_EPSILON:
            ctx.ground_candidate_alt = alt
            ctx.ground_below_threshold_since = time.time()
            ctx.log(
                f"[FSM] New lower ground candidate: {alt:.3f} m "
                "(resetting stability timer)"
            )
            return self

        # If we’re within the small band around candidate (not moving much)
        if abs(alt - cand) <= config.GROUND_EPSILON:
            if ctx.ground_below_threshold_since is None:
                ctx.ground_below_threshold_since = time.time()
                ctx.log(
                    f"[FSM] Altitude ~ground candidate ({alt:.3f} m), "
                    "starting stability timer"
                )
            else:
                dt = time.time() - ctx.ground_below_threshold_since
                if dt >= config.GROUND_STABLE_TIME:
                    ctx.log(
                        f"[FSM] Altitude stable near candidate {cand:.3f} m "
                        f"for {dt:.2f}s -> DONE"
                    )
                    return DoneState()
            return self

        # Else: we are above candidate + epsilon (moved up again), reset timer
        ctx.ground_below_threshold_since = None
        ctx.log(
            f"[FSM] Altitude {alt:.3f} m above candidate {cand:.3f} m "
            "(not stable on ground yet)"
        )
        return self

    def hint(self, ctx) -> str:
        return (
            "Keep lowering the drone until it's clearly on the ground, "
            "then hold it there briefly. The FSM will detect stable minimum altitude."
        )


class DoneState(State):
    name = "DONE"

    def on_enter(self, ctx) -> None:
        ctx.log("[FSM] Entering DONE")

        if config.DISARM_ON_DONE:
            if ctx.drone.is_armed():
                ctx.log("[FSM] DISARM_ON_DONE=True and vehicle is armed -> sending DISARM")
                ctx.drone.disarm()

                # If you have read_status_messages() implemented, this will
                # print COMMAND_ACK + any STATUSTEXT about disarm.
                try:
                    ctx.drone.read_status_messages(duration=config.DISARM_WAIT_TIME)
                except AttributeError:
                    # read_status_messages not present; ignore
                    pass
            else:
                ctx.log("[FSM] DISARM_ON_DONE=True but vehicle is already disarmed")
        else:
            ctx.log("[FSM] DISARM_ON_DONE=False -> leaving motors state as-is")

    def step(self, ctx) -> State:
        # Nothing more to do here; FSM will stop after this state.
        return self

    def hint(self, ctx) -> str:
        return "Test finished (DONE). Vehicle should now be disarming."


class AbortState(State):
    name = "ABORT"

    def step(self, ctx) -> State:
        return self

    def hint(self, ctx) -> str:
        return "Test aborted due to error or timeout. Check logs and setup."
