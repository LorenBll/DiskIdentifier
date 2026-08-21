# DiskIdentifier

DiskIdentifier is a local disk registration service that assigns persistent SHA-256 identifiers to mounted disk roots and resolves them on demand.

## About

DiskIdentifier binds to `127.0.0.1` on port `49157` and rejects API calls that do not come from the local device. Each installation generates a unique universal identifier persisted in the `UNIVERSAL_DISK_IDENTIFIER_ID` variable in `.env`. Disk associations are refreshed from disk every 30 seconds in a background thread, keeping the in-memory cache in sync with the `.id` files on mounted volumes.

**Features:**

- **Disk Registration** — assign a persistent SHA-256 identifier to any mounted disk root by writing a hidden `.id` file on the volume.
- **Identifier Lookup** — resolve a disk identifier to its cached root path, or a root path to its loaded identifier.
- **Universal Identifier** — each installation generates a unique universal disk identifier persisted in `.env`.
- **Background Refresh** — disk associations are refreshed from disk every 30 seconds in a background thread.
- **Persistence** — registered disk IDs are stored in the `DISK_IDENTIFIERS` variable in `.env`.
- **ServiceHandler Integration** — optionally registers with ServiceHandler for service discovery.

> **Safety notice**: DiskIdentifier is intended only for environments where safety is not a major risk — the chances of malevolent actors are low, and the consequences of an eventual mishap are low.

## Setup

1. Install Python dependencies: `pip install -r requirements.txt`.
2. Review `resources/configuration.json` if you want to change the port or disable ServiceHandler integration (enabled by default).
3. Leave the project structure intact so the service can find `resources/` and `src/`.

### Environment Variables

| Variable | Description |
|----------|-------------|
| `DISK_IDENTIFIERS` | JSON array of registered disk identifier hashes. Automatically saved to `.env`. |
| `UNIVERSAL_DISK_IDENTIFIER_ID` | 64-char hex installation identifier. Automatically saved to `.env`. |

## Run

1. Windows: run `scripts\run.bat` (add `--debug` for debug output).
2. Unix-like: run `bash scripts/run.sh` (add `--debug` for debug output).
3. Manual: run `python src/main.py` from the project root (add `--debug` for debug output).

## Logging

DiskIdentifier writes structured JSON log events to `logs/` (one file per run, named `DD-MM-YYYY_HH.MM.SS.json`). Each event contains `timestamp`, `type` (`ERROR`, `WARN`, `INFO`, `DEBUG`), `title`, `data`, and a `hash` of the entry. Debug events are only recorded when the service is started with `--debug`. Log files older than 14 days are pruned automatically at startup.

## Access Control

All `/api/*` endpoints are local-device only. Requests from non-local addresses are rejected with:
- `403` -> `{ "error": "Local device access only." }`
- All endpoints also support `HEAD` and `OPTIONS`.
- API responses use `Connection: close`.

## API Endpoints

### `POST /api/disk/register` (also `HEAD`, `OPTIONS`)
Registers a disk root, writes `<UNIVERSAL_DISK_IDENTIFIER_ID>.id` at that root, and stores the association.
- Auth: local-device only (no API key required).
- Body (JSON object):
	- `path` (string, required): absolute path to a disk root to register.
- Returns:
	- `201` -> `{ "disk_identifier": "<generated-id>", "env_var_entry": "DISK_IDENTIFIERS=[...]" }`
	- `400` -> `{ "error": "A non-empty path is required." }`
	- `400` -> `{ "error": "Invalid path provided." }`
	- `400` -> `{ "error": "The provided path must be a disk root." }`
	- `409` -> `{ "error": "An identifier already exists." }`
	- `500` -> `{ "error": "Universal disk identifier is not configured." }`
	- `500` -> `{ "error": "Failed to create identifier file." }`
	- `500` -> `{ "error": "Failed to persist disk identifier." }`

### `GET /api/disk/locate` (also `HEAD`, `OPTIONS`)
Resolves a disk identifier to its cached disk-root path.
- Auth: local-device only (no API key required).
- Body (JSON object):
	- `disk_identifier` (string, required): previously registered disk identifier.
- Returns:
	- `200` -> `{ "path": "<disk-root-path>" }`
	- `400` -> `{ "error": "A disk identifier is required." }`
	- `404` -> `{ "error": "Disk identifier not found." }`

### `GET /api/disk/whoisit` (also `HEAD`, `OPTIONS`)
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
Returns the installation-wide universal disk identifier for this installation.
- Auth: local-device only (no API key required).
- Body: none.
- Returns:
	- `200` -> `{ "universaldiskidentifierid": "<64-char-hex-id>" }`
	- `500` -> `{ "error": "Universal disk identifier is not configured." }`

### `DELETE /api/disk/forget` (also `HEAD`, `OPTIONS`)
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

## Notes

### Ultimate Absolute Paths

Projects that consume DiskIdentifier (CipherCLI, MPAgent, GalleryCleaner, etc.) use the **ultimate absolute path** convention to express paths that span unknown disk roots:

```
<64-char-disk-identifier-hex-hash>::<relative-path-within-disk>
```

The `::` separator distinguishes the disk identifier from the relative path. The consumer resolves the hash to a physical root via `GET /api/disk/locate`, then joins the relative portion.

Example:
```
bf5de32849cf52543eddf648d3cda6a3be93114eee9e1004d9174b6e606f9f80::Notes/Obsidian
```

---

## Support

- Open an issue on [GitHub](https://github.com/LorenBll/DiskIdentifier/issues) for bug reports, feature requests, or help.

## License

- [LICENSE](LICENSE)

## Author

- [LorenBll](https://github.com/LorenBll)
