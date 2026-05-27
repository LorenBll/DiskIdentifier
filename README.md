# DiskIdentifier

DiskIdentifier is a local disk registration service. It solves the problem of assigning persistent identifiers to disk roots so the same volume can be found, identified, or forgotten later.

## About
DiskIdentifier is scoped to disk-root management and keeps its identifier cache in memory while persisting the universal installation ID and registered disk IDs in `resources/`. The service binds to `127.0.0.1` on port `49157` and rejects API calls that do not come from the local device.

## Setup
1. Install the Python dependencies with `pip install -r requirements.txt`.
2. Review `resources/configuration.json` if you want to change the port or reset the universal disk identifier.
3. Keep `resources/identifiers.json` in place so registered disk IDs can be persisted.

## Run
1. Windows: run `scripts\run.bat`.
2. Unix-like systems: run `bash scripts/run.sh`.
3. Manual: run `python src/main.py` from the project root.

## API Endpoints
- `POST /api/register` - Register a disk root using a JSON body.
- `POST /api/register/<path:path_value>` - Register a disk root from the path parameter.
- `GET /api/locate` - Resolve a disk identifier back to its disk root.
- `GET /api/locate/<string:identifier_value>` - Resolve a disk identifier from the path parameter.
- `GET /api/identify` - Return the identifier for a disk root.
- `GET /api/identify/<path:path_value>` - Return the identifier for a disk root from the path parameter.
- `GET /api/whoareu` - Return the installation-wide universal disk identifier.
- `DELETE /api/forget` - Remove a registered disk identifier using a JSON body.
- `DELETE /api/forget/<string:identifier_value>` - Remove a registered disk identifier from the path parameter.
- `GET /api/health` - Return service health.

## License
- [LICENSE](LICENSE)

## Author
- [LorenBll](https://github.com/LorenBll)