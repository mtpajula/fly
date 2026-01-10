## fly

Minimal MAVSDK-based scripts for PX4 (and generally MAVSDK-compatible stacks).

### Scripts

- `hop/main.py`: arm → takeoff → wait → land → disarm
- `pixhawk_link_test.py`: connect + print some telemetry samples (link sanity check)
- `battery_check.py`: print battery telemetry samples

### Run (examples)

```bash
uv run -m hop.main --system-address udpin://0.0.0.0:14540 --hover-seconds 5
```

```bash
uv run pixhawk_link_test.py --system-address udpin://0.0.0.0:14540 --samples 20
```

```bash
uv run battery_check.py --system-address udpin://0.0.0.0:14540 --count 20
```


