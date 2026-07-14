# DiskIdentifier

DiskIdentifier is a local disk registration service. It solves the problem of assigning persistent identifiers to disk roots so the same volume can be found, identified, or forgotten later.

## About
DiskIdentifier is scoped to disk-root management and keeps its identifier cache in memory while persisting the universal installation ID and registered disk IDs in `resources/`. The service binds to `127.0.0.1` on port `49157` and rejects API calls that do not come from the local device.

## Integration

This service can optionally register with [PortHandler](https://www.github.com/LorenBll/PortHandler) for service discovery, but does not depend on it. Set `porthandlerEnabled` in `resources/configuration.json` to control this behavior.

## Background Refresh

Disk associations are refreshed from disk every 30 seconds in a background thread. This ensures the in-memory cache stays in sync with the `<UNIVERSAL_DISK_IDENTIFIER_ID>.id` files present on mounted volumes and the allowed identifiers listed in `resources/identifiers.json`.

## Setup

### Quick setup
1. Windows: run `scripts\setup.bat` (creates a virtual environment and installs dependencies).
2. Unix-like systems: run `bash scripts/setup.sh`.

### Manual setup
1. `pip install -r requirements.txt` (after creating and activating a virtual environment).
2. Review `resources/configuration.json` if you want to change the port or reset the universal disk identifier.
3. Keep `resources/identifiers.json` in place so registered disk IDs can be persisted.
4. Leave the project structure intact so the service can find `resources/` and `src/`.

## Run
1. Windows: run `scripts\run.bat`.
2. Unix-like systems: run `bash scripts/run.sh`.
3. Manual: run `python src/main.py` from the project root (with the virtual environment activated).

## Auto-Startup

The `deployment/` directory contains auto-startup configurations for each platform:
- **Windows**: `startup-windows.vbs` — place in the Startup folder or use as a scheduled task.
- **Linux**: `service.service` — systemd unit file.
- **macOS**: `com.service.plist` — launchd property list.

Update the paths in these files to match your installation before deploying.

## Access Control

All `/api/*` endpoints are local-device only. Requests from non-local addresses are rejected with:
- `403` -> `{ "error": "Local device access only." }`
- All endpoints also support `HEAD` and `OPTIONS`.
- API responses use `Connection: close` (non-persistent connections).

## API Endpoints

### `POST /api/register` (also `HEAD`, `OPTIONS`)
Registers a disk root, writes `<UNIVERSAL_DISK_IDENTIFIER_ID>.id` at that root, and stores the association.

- Body (JSON object):
	- `path` (string, required): absolute path to a disk root to register.
- Returns:
	- `201` -> `{ "disk_identifier": "<generated-id>" }`
	- `400` -> `{ "error": "A non-empty path is required." }`
	- `400` -> `{ "error": "Invalid path provided." }`
	- `400` -> `{ "error": "The provided path must be a disk root." }`
	- `409` -> `{ "error": "An identifier already exists." }`
	- `500` -> `{ "error": "Universal disk identifier is not configured." }`
	- `500` -> `{ "error": "Failed to create identifier file." }`
	- `500` -> `{ "error": "Failed to persist disk identifier." }`

### `GET /api/locate` (also `HEAD`, `OPTIONS`)
Resolves a disk identifier to its cached disk-root path.

- Body (JSON object):
	- `disk_identifier` (string, required): previously registered disk identifier.
- Returns:
	- `200` -> `{ "path": "<disk-root-path>" }`
	- `400` -> `{ "error": "A disk identifier is required." }`
	- `404` -> `{ "error": "Disk identifier not found." }`

### `GET /api/identify` (also `HEAD`, `OPTIONS`)
Resolves a disk root to its loaded disk identifier.

- Body (JSON object):
	- `path` (string, required): absolute disk-root path.
- Returns:
	- `200` -> `{ "disk_identifier": "<id>", "path": "<disk-root-path>" }`
	- `400` -> `{ "error": "A non-empty path is required." }`
	- `400` -> `{ "error": "Invalid path provided." }`
	- `400` -> `{ "error": "The provided path must be a disk root." }`
	- `404` -> `{ "warning": "No disk identifier is loaded for the provided disk." }`

### `GET /api/whoareu` (also `HEAD`, `OPTIONS`)
Returns the installation-wide universal disk identifier key name.

- Body: none
- Returns:
	- `200` -> `{ "universaldiskidentifierid": "<universal-id-name>" }`
	- `500` -> `{ "error": "Universal disk identifier is not configured." }`

### `DELETE /api/forget` (also `HEAD`, `OPTIONS`)
Deletes a registered disk identifier, removes its identifier file from disk root, and removes cache/persistence entries.

- Body (JSON object):
	- `disk_identifier` (string, required): identifier to remove.
- Returns:
	- `200` -> `{ "status": "forgotten", "disk_identifier": "<id>", "path": "<disk-root-path>" }`
	- `400` -> `{ "error": "A disk identifier is required." }`
	- `404` -> `{ "error": "Disk identifier not found." }`
	- `500` -> `{ "error": "Failed to delete identifier file." }`

### `GET /api/health` (also `HEAD`, `OPTIONS`)
Service health check.

- Body: none
- Returns:
	- `200` ->
		```json
		{
			"status": "ok",
			"service": "DiskIdentifier",
			"bind_address": "127.0.0.1",
			"port": 49157,
			"hostname": "workstation-name"
		}
		```

## License
- [LICENSE](LICENSE)

## Author
- [LorenBll](https://github.com/LorenBll)