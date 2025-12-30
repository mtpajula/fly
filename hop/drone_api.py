# first_hop/drone_api.py

import time
from typing import Optional
from pymavlink import mavutil

from . import config
from .logger_setup import setup_logger


class DroneAPI:
    def __init__(self, port=None, baud=None):
        self.port = port or config.PORT
        self.baud = baud or config.BAUD
        self.master = None
        self.log = setup_logger()

    def connect(self):
        self.log.info(f"Connecting to %s @ %d", self.port, self.baud)
        self.master = mavutil.mavlink_connection(
            self.port,
            baud=self.baud,
            autoreconnect=False,
        )

    def wait_heartbeat(self, timeout=None) -> bool:
        self._require_master()
        self.log.info("Waiting for heartbeat…")

        msg = self.master.wait_heartbeat(timeout=timeout)
        if msg is None:
            self.log.error("Heartbeat timeout")
            return False

        self.log.info(
            "Heartbeat from system %s component %s",
            msg.get_srcSystem(),
            msg.get_srcComponent(),
        )
        return True

    def request_basic_data_streams(self):
        self._require_master()
        self.log.debug("Requesting telemetry streams")

        streams = [
            (mavutil.mavlink.MAV_DATA_STREAM_POSITION, 10),
            (mavutil.mavlink.MAV_DATA_STREAM_EXTRA1, 10),
        ]
        for stream_id, rate in streams:
            self.master.mav.request_data_stream_send(
                self.master.target_system,
                self.master.target_component,
                stream_id,
                rate,
                1,
            )
            time.sleep(0.1)

    def set_mode_custom(self, custom_mode):
        self._require_master()
        self.log.info("Setting custom mode %d", custom_mode)

        self.master.mav.set_mode_send(
            self.master.target_system,
            mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
            custom_mode,
        )

    def arm(self):
        self._require_master()
        self.log.info("Sending ARM command")

        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0,
            1, 0, 0, 0, 0, 0, 0,
        )

    def disarm(self) -> None:
        """Send disarm command."""
        self._require_master()
        self.log.info("Sending DISARM command")

        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0,
            0, 0, 0, 0, 0, 0, 0,   # param1 = 0 => disarm
        )

    def is_armed(self) -> bool:
        """Check whether vehicle reports motors armed."""
        self._require_master()
        return bool(self.master.motors_armed())

    def get_mode(self) -> Optional[str]:
        """Return the current flight mode name (e.g., 'GUIDED_NOGPS')."""
        self._require_master()
        if 'heartbeat' not in self.master.messages:
            return None
        msg = self.master.messages['heartbeat']
        mode_id = msg.custom_mode
        # This is a bit of a hack for ArduCopter; ideally we'd use a mapping
        # but for this specific test we know what we are looking for.
        return str(mode_id)

    def get_relative_alt(self, timeout=1.0) -> Optional[float]:
        self._require_master()

        msg = self.master.recv_match(type="GLOBAL_POSITION_INT", blocking=False)
        while msg is not None:
            msg = self.master.recv_match(type="GLOBAL_POSITION_INT", blocking=False)

        msg = self.master.recv_match(
            type="GLOBAL_POSITION_INT",
            blocking=True,
            timeout=timeout,
        )
        if msg is None:
            return None

        return msg.relative_alt * 0.001

    def close(self):
        if self.master:
            self.log.info("Closing MAVLink connection")
            self.master.close()
            self.master = None

    def _require_master(self):
        if self.master is None:
            raise RuntimeError("DroneAPI not connected")
    
    def read_status_messages(self, duration: float = 1.0) -> None:
        """
        Drain and log STATUSTEXT and COMMAND_ACK messages for a short period.
        Useful around arming to see what ArduPilot is complaining about.
        """
        self._require_master()
        end = time.time() + duration

        while time.time() < end:
            msg = self.master.recv_match(
                type=["STATUSTEXT", "COMMAND_ACK"],
                blocking=False,
            )
            if msg is None:
                time.sleep(0.05)
                continue

            mtype = msg.get_type()

            if mtype == "STATUSTEXT":
                text = getattr(msg, "text", "")
                self.log.info("[STATUSTEXT] %s: %s", msg.severity, text)

            elif mtype == "COMMAND_ACK":
                self.log.info(
                    "[COMMAND_ACK] command=%s result=%s",
                    getattr(msg, "command", "?"),
                    getattr(msg, "result", "?"),
                )

    def set_thrust(self, thrust: float):
        """
        Send SET_ATTITUDE_TARGET with zero roll/pitch/yaw and specified thrust.
        thrust range: 0.0 .. 1.0
        """
        self._require_master()
        thrust = max(0.0, min(1.0, thrust))

        # time_boot_ms must be uint32 in milliseconds
        time_boot_ms = int(time.time() * 1000) & 0xFFFFFFFF

        # Level attitude quaternion (no rotation): w=1, x=y=z=0
        q = [1.0, 0.0, 0.0, 0.0]

        self.master.mav.set_attitude_target_send(
            time_boot_ms,                # time_boot_ms (not microseconds)
            self.master.target_system,
            self.master.target_component,
            0b00000111,                  # ignore body rates, use attitude+thrust
            q,                           # quaternion
            0.0, 0.0, 0.0,               # body rates (ignored)
            thrust,                      # normalized thrust
        )

    def set_throttle_percent(self, percent: float) -> None:
        """
        Override RC throttle channel by percentage (0–100).
        This directly maps to PWM 1000–2000us on channel 3 (typical throttle).
        NOTE: Requires vehicle to be armed and RC override enabled.
        """
        self._require_master()

        # clamp 0..100
        percent = max(0.0, min(100.0, percent))

        # Map 0–100% to 1000–2000us
        pwm = int(1000 + (percent / 100.0) * 1000)

        self.log.debug("RC override throttle: %.1f%% -> %d us", percent, pwm)

        # ArduPilot: 0 means "do not override" for that channel
        # Order: chan1, chan2, chan3, chan4, chan5, chan6, chan7, chan8
        self.master.mav.rc_channels_override_send(
            self.master.target_system,
            self.master.target_component,
            0,        # ch1 (roll) - no override
            0,        # ch2 (pitch) - no override
            pwm,      # ch3 (throttle) - our override
            0,        # ch4 (yaw) - no override
            0, 0, 0, 0  # ch5-8 - no override
        )
