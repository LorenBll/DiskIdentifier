# DiskIdentifier

DiskIdentifier is a small local Flask service for creating, storing, locating, and removing disk identifiers. It writes a unique identifier file at the root of a disk, keeps a small in-memory cache for lookups, and rejects requests that do not originate from the local device.

## About

This project is designed for workflows that need stable references to disk roots instead of absolute paths. The service stores persistent identifier records in [resources/identifiers.json](resources/identifiers.json), refreshes its cache on startup and in the background, and binds only to `127.0.0.1` using the port in [resources/configuration.json](resources/configuration.json).

## Setup

### Prerequisites

- Python 3.10 or newer
- Permission to read and write the root of the disk you want to register

### Install Dependencies

```bash
python -m pip install -r requirements.txt
```

### Configuration

Edit [resources/configuration.json](resources/configuration.json) if you want to change the listening port. Leave `universalDiskIdentifierID` blank to let the service generate one on first start.

## Run

Start the service with:

```bash
python src/main.py
```

On Windows, you can also use:

```bat
scripts\run.bat
```

## Usage

### `POST /api/register` or `POST /api/register/<path>`

- **Request type:** `POST`
- **Arguments:** a disk root in the path or in a JSON body with `path`
- **What it does:** validates that the path is a disk root, generates a unique identifier, writes the identifier file, and stores the association in `resources/identifiers.json`
- **How it answers:** returns `201 Created` with JSON like `{"disk_identifier": "..."}`

### `GET /api/locate` or `GET /api/locate/<identifier>`

- **Request type:** `GET`
- **Arguments:** the disk identifier in the path or in a JSON body with `disk_identifier`
- **What it does:** looks up the identifier in the cache and returns the matching disk root path
- **How it answers:** returns `200 OK` with JSON like `{"path": "..."}`

### `GET /api/identify` or `GET /api/identify/<path>`

- **Request type:** `GET`
- **Arguments:** the disk root in the path or in a JSON body with `path`
- **What it does:** returns the identifier currently loaded for the provided disk root
- **How it answers:** returns `200 OK` with JSON like `{"disk_identifier": "...", "path": "..."}`

### `GET /api/whoareu`

- **Request type:** `GET`
- **Arguments:** none
- **What it does:** returns the installation's `universalDiskIdentifierID` value from [resources/configuration.json](resources/configuration.json)
- **How it answers:** returns `200 OK` with JSON like `{"universaldiskidentifierid": "..."}`

### `DELETE /api/forget` or `DELETE /api/forget/<identifier>`

- **Request type:** `DELETE`
- **Arguments:** the disk identifier in the path or in a JSON body with `disk_identifier`
- **What it does:** removes the identifier file, deletes the persistent record, and clears the in-memory association
- **How it answers:** returns `200 OK` with JSON like `{"status": "forgotten", "disk_identifier": "...", "path": "..."}`

### `GET /api/health`

- **Request type:** `GET`
- **Arguments:** none
- **What it does:** reports whether the service is running
- **How it answers:** returns `200 OK` with JSON containing `{"status": "ok"}`

## Project Structure

```text
DiskIdentifier/
├── deployment/
│   ├── com.service.plist
│   ├── service.service
│   └── startup-windows.vbs
├── resources/
│   ├── configuration.json
│   └── identifiers.json
├── scripts/
│   ├── run.bat
│   ├── run.sh
│   ├── setup.bat
│   └── setup.sh
├── src/
│   └── main.py
├── LICENSE
├── README.md
└── requirements.txt
```

## License

This project is licensed under the terms specified in [LICENSE](LICENSE).