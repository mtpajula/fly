# hop/state_machine.py

import time

from . import config
from .drone_api import DroneAPI
from .states import (
    State,
    WaitHeartbeatState,
    DoneState,
    AbortState,
)
from .logger_setup import setup_logger


class StateContext:
    def __init__(self, drone: DroneAPI, log_func):
        self.drone = drone
        self.log = log_func

        self.state_start_time: float = time.time()
        self.hover_start_time: float | None = None

        # For landing detection
        self.ground_below_threshold_since: float | None = None
        self.ground_candidate_alt: float | None = None

        # Latest telemetry
        self.alt: float | None = None
        self.ascent_baseline_alt: float | None = None


    @property
    def elapsed(self) -> float:
        """Time since current state was entered."""
        return time.time() - self.state_start_time


class StateMachine:
    def __init__(self, drone: DroneAPI):
        logger = setup_logger()
        self._logger = logger
        self.log = logger.info  # <-- callable, same style as before

        self.drone = drone
        self.ctx = StateContext(drone=drone, log_func=self.log)

        self.state: State = WaitHeartbeatState()
        self.state.on_enter(self.ctx)
        self._print_state_banner()

    def step(self) -> bool:
        """
        Execute one FSM tick.
        Returns True to keep running, False when DONE/ABORT.
        """
        # Update telemetry by draining the message buffer
        self.drone.update()
        
        # Update context telemetry
        self.ctx.alt = self.drone.get_relative_alt()

        # Log altitude if state is active
        if not isinstance(self.state, (WaitHeartbeatState, DoneState, AbortState)):
            if self.ctx.alt is not None:
                self.log(f"[ALT] {self.ctx.alt:.3f} m")

        # Let state run
        new_state = self.state.step(self.ctx)

        # State might request a transition
        if new_state is not self.state:
            self.state = new_state
            self.ctx.state_start_time = time.time()
            self._print_state_banner()
            self.state.on_enter(self.ctx)

        # Continue until DONE or ABORT
        if isinstance(self.state, (DoneState, AbortState)):
            self.log(f"[HINT] {self.state.hint(self.ctx)}")
            return False

        # Regular hint
        self.log(f"[HINT] {self.state.hint(self.ctx)}")
        return True

    def _print_state_banner(self) -> None:
        """Nice clear state display for the console."""
        print("")
        print("=" * 60)
        print(f" STATE: {self.state.name}")
        print("=" * 60)

    @property
    def current_state(self) -> State:
        return self.state
