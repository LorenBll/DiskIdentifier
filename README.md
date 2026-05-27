# DiskIdentifier

DiskIdentifier is a local Flask service for creating, storing, locating, and removing disk identifiers. It persists identifier associations and keeps an in-memory cache for fast lookup.

## About

- Scope: disk-root registration and reverse lookup by identifier.
- Runtime model: persistent JSON association store plus background refresh loop.
- Networking: local-only bind (`127.0.0.1`) with API-only workflow.

## Setup

### Prerequisites

- Python 3.10 or newer
- Permission to read and write the root of the target disks

### Install Dependencies

```bash
python -m pip install -r requirements.txt
```

### Configuration

Edit `resources/configuration.json` as needed:

- `port`: TCP port used by the service
- `universalDiskIdentifierID`: optional installation identifier (auto-generated when blank)

## Run

Start with:

```bash
python src/main.py
```

Windows shortcut:

```bat
scripts\run.bat
```

Startup behavior is consistent with the other services in this workspace: structured logging and a threaded Flask server.

## Usage

### `POST /api/register` and `POST /api/register/<path>`

- Method: `POST`
- Input: disk root path in route or JSON body
- Behavior: validates disk root, creates identifier file, persists association
- Response: `201 Created` with generated `disk_identifier`

### `GET /api/locate` and `GET /api/locate/<identifier>`

- Method: `GET`
- Input: identifier in route or JSON body
- Behavior: resolves identifier to disk root path
- Response: `200 OK` with `path`

### `GET /api/identify` and `GET /api/identify/<path>`

- Method: `GET`
- Input: disk root path in route or JSON body
- Behavior: resolves path to identifier
- Response: `200 OK` with `disk_identifier` and `path`

### `GET /api/whoareu`

- Method: `GET`
- Input: none
- Behavior: returns configured installation identifier
- Response: `200 OK`

### `DELETE /api/forget` and `DELETE /api/forget/<identifier>`

- Method: `DELETE`
- Input: identifier in route or JSON body
- Behavior: removes identifier file and persistent association
- Response: `200 OK`

### `GET /api/health`

- Method: `GET`
- Input: none
- Behavior: reports service availability
- Response: `200 OK` with `status`

## Project Structure

```text
DiskIdentifier/
├── deployment/
├── resources/
│   ├── configuration.json
│   └── identifiers.json
├── scripts/
├── src/
│   └── main.py
├── LICENSE
├── README.md
├── requirements.txt
└── SECURITY.md
```

## License

This project is licensed under the terms specified in [LICENSE](LICENSE).