# Hop Module

This module implements a simple autonomous "hop" for a drone using a Pixhawk 6C (ArduPilot) and a Raspberry Pi 3 A+ companion computer.

## Overview

The goal of this module is to perform a basic autonomous flight sequence:
1.  **Rise from the ground** to a small height.
2.  **Hover** for a few seconds.
3.  **Land** back safely.

The project is managed with `uv` and uses `pymavlink` for communication over the `Telem1` (RX/TX) port.

### Hardware Setup
- **Flight Controller:** Pixhawk 6C (running ArduPilot)
- **Companion Computer:** Raspberry Pi 3 A+
- **Connection:** Telem1 (Pixhawk) <-> UART (RPi)
- **Sensors:** Internal Pixhawk sensors only (Indoor flight, no GPS, no RC)

## Implementation Details

The core logic is implemented as a finite state machine (FSM):

- **StateMachine:** Manages transitions between states.
- **States:**
    - `WAIT_HEARTBEAT`: Wait for the Pixhawk to start sending heartbeats.
    - `SET_MODE_GUIDED_NOGPS`: Switch to `GUIDED_NOGPS` mode.
    - `ARM`: Send the arming command and wait for confirmation.
    - `SPIN_MOTORS`: Spin the motors at a low power (using RC overrides for testing).
    - `WAIT_FOR_ASCENT`: Wait for a manual or actual lift in altitude.
    - `HOVER`: Maintain position/height for a set duration.
    - `LAND`: Request `LAND` mode.
    - `WAIT_FOR_GROUNDED`: Detect when the drone has touched the ground.
    - `DONE`: Disarm and finish the test.

## Project Plan

### Step 1: State Machine Logic Test (COMPLETED)
- **Goal:** Verify the FSM transitions correctly.
- **Process:** Run the code while physically lifting and lowering the drone.
- **Result:** Successfully confirmed that the FSM moves through all states based on altitude changes and timeouts.

### Step 2: Bench Test (Props OFF) (IN PROGRESS)
- **Goal:** Test motor response and system behavior without risk.
- **Process:**
    - Remove all propellers.
    - Run the `hop` module.
    - Manually lift the drone during the `SPIN_MOTORS` and `WAIT_FOR_ASCENT` phases.
    - Observe if motors spin as expected and if the FSM reacts correctly.

### Step 3: First Autonomous Flight (FUTURE)
- **Goal:** Real autonomous hop.
- **Process:** Attach propellers and run the module in a safe, controlled environment.

