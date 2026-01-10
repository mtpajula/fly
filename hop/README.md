# Hop (MAVSDK)

This folder contains a minimal **MAVSDK**-based “hop” example:

- connect
- wait until connected
- wait until global position + home are OK
- arm
- takeoff
- wait
- land
- wait until landed
- disarm

## Run

From repo root:

```bash
uv run -m hop.main --hover-seconds 5
```

Or serial (example):

```bash
uv run -m hop.main --system-address serial:///dev/ttyS0:57600
```

### Indoors tip

Default takeoff altitude is **0.5m**. You can set it lower/higher (clamped to >= 0.3m):

```bash
uv run -m hop.main --takeoff-alt-m 0.5
```


