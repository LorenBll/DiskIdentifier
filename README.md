# DiskIdentifier

DiskIdentifier is a local disk registration service that assigns persistent SHA-256 identifiers to mounted disk roots and resolves them on demand.

## About

- **Disk Registration** — assign a persistent SHA-256 identifier to any mounted disk root by writing a hidden `.id` file on the volume.
- **Identifier Lookup** — resolve a disk identifier to its cached root path, or a root path to its loaded identifier.
- **Universal Identifier** — each installation generates a unique universal disk identifier key name persisted in `resources/configuration.json`.
- **Background Refresh** — disk associations are refreshed from disk every 30 seconds in a background thread, keeping the in-memory cache in sync with the `.id` files on mounted volumes.
- **Persistence** — registered disk IDs are stored in `resources/identifiers.json` so they survive restarts.

## Setup

1. Windows: run `scripts\setup.bat` (creates a virtual environment and installs dependencies).
2. Unix-like systems: run `bash scripts/setup.sh`.
3. Manual: `pip install -r requirements.txt` (after creating and activating a virtual environment).
4. Review `resources/configuration.json` if you want to change the port or reset the universal disk identifier.
5. Keep `resources/identifiers.json` in place so registered disk IDs can be persisted.
6. Leave the project structure intact so the service can find `resources/` and `src/`.

## Run

1. Windows: run `scripts\run.bat`.
2. Unix-like systems: run `bash scripts/run.sh`.
3. Manual: run `python src/main.py` from the project root (with the virtual environment activated).

## Integration

This service can optionally register with [ServiceHandler](https://www.github.com/LorenBll/ServiceHandler) for service discovery, but does not depend on it. Set `servicehandlerEnabled` in `resources/configuration.json` to control this behavior.

When registered, DiskIdentifier also registers its API endpoints with ServiceHandler so they can be discovered by other services.

## Auto-Startup

The `deployment/` directory contains auto-startup configurations for each platform:

- **Windows**: `startup-windows.vbs` — place in the Startup folder or use as a scheduled task.
- **Linux**: `service.service` — systemd unit file.
- **macOS**: `com.service.plist` — launchd property list.

Update the paths in these files to match your installation before deploying.

## Access Control

All `/api/*` endpoints are local-device only. Requests from non-local addresses are rejected with `403`:

- `403` -> `{ "error": "Local device access only." }`

All endpoints also support `HEAD` and `OPTIONS`. API responses use `Connection: close`.

## API Endpoints

### `POST /api/register/disk` (also `HEAD`, `OPTIONS`)

Registers a disk root, writes `<UNIVERSAL_DISK_IDENTIFIER_ID>.id` at that root, and stores the association.

- Auth: local-device only (no API key required).
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

### `GET /api/locate/disk` (also `HEAD`, `OPTIONS`)

Resolves a disk identifier to its cached disk-root path.

- Auth: local-device only (no API key required).
- Body (JSON object):
	- `disk_identifier` (string, required): previously registered disk identifier.
- Returns:
	- `200` -> `{ "path": "<disk-root-path>" }`
	- `400` -> `{ "error": "A disk identifier is required." }`
	- `404` -> `{ "error": "Disk identifier not found." }`

### `GET /api/whoisit/disk` (also `HEAD`, `OPTIONS`)

Resolves a disk root to its loaded disk identifier.

- Auth: local-device only (no API key required).
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

- Auth: local-device only (no API key required).
- Body: none.
- Returns:
	- `200` -> `{ "universaldiskidentifierid": "<universal-id-name>" }`
	- `500` -> `{ "error": "Universal disk identifier is not configured." }`

### `DELETE /api/forget/disk` (also `HEAD`, `OPTIONS`)

Deletes a registered disk identifier, removes its identifier file from disk root, and removes cache and persistence entries.

- Auth: local-device only (no API key required).
- Body (JSON object):
	- `disk_identifier` (string, required): identifier to remove.
- Returns:
	- `200` -> `{ "status": "forgotten", "disk_identifier": "<id>", "path": "<disk-root-path>" }`
	- `400` -> `{ "error": "A disk identifier is required." }`
	- `404` -> `{ "error": "Disk identifier not found." }`
	- `500` -> `{ "error": "Failed to delete identifier file." }`

### `GET /api/health` (also `HEAD`, `OPTIONS`)

Service health check.

- Auth: local-device only (no API key required).
- Body: none.
- Returns:
	- `200` -> `{ "status": "ok", "service": "DiskIdentifier", "bind_address": "127.0.0.1", "port": 49157, "hostname": "<hostname>", "pid": 12345 }`

---

## Support

- Open an issue on [GitHub](https://github.com/LorenBll/DiskIdentifier/issues) for bug reports, feature requests, or help.

## License

- [LICENSE](LICENSE)

## Author

- [LorenBll](https://github.com/LorenBll)
