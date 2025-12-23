# first_hop/main.py

import time

from . import config
from .drone_api import DroneAPI
from .state_machine import StateMachine
from .states import DoneState, AbortState
from .logger_setup import setup_logger


def main():
    log = setup_logger()

    log.info("FIRST HOP TEST – manual lift, state machine")
    log.info("Props OFF for initial testing")
    log.info("Using port=%s baud=%d", config.PORT, config.BAUD)

    drone = DroneAPI()
    fsm = None

    try:
        drone.connect()
        fsm = StateMachine(drone=drone)

        running = True
        while running:
            running = fsm.step()
            time.sleep(config.LOOP_DT)

        if isinstance(fsm.current_state, DoneState):
            log.info("Test completed successfully")
        elif isinstance(fsm.current_state, AbortState):
            log.warning("Test aborted")
        else:
            log.warning("FSM ended unexpectedly: %s", fsm.current_state.name)

    except KeyboardInterrupt:
        log.warning("Interrupted by user")
    except Exception as e:
        log.exception("Unhandled exception: %s", e)
    finally:
        drone.close()
        log.info("Exit")

if __name__ == "__main__":
    main()