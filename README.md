# DiskIdentifier

REST API for generating, storing, locating, and removing disk identifiers on a local machine. The service works with disk roots, writes a unique identifier file at the root of a drive, and keeps an in-memory cache so identifiers can be resolved back to their paths quickly.

## Table of Contents

- [About](#about)
- [Features](#features)
- [Project Structure](#project-structure)
- [Installation](#installation)
- [Usage](#usage)
- [Tech Stack](#tech-stack)
- [License](#license)

## About

This project provides a small Flask service for assigning a unique identifier to a disk root, looking that disk root up later, and forgetting the association when it is no longer needed. It stores persistent identifier records in `resources/identifiers.json`, writes the identifier file directly at the disk root, and refreshes the path-to-id cache on startup and every 30 seconds in the background.

## Features

- **REST API:** Simple HTTP interface for registering, locating, and forgetting disk identifiers
- **Disk-Root Registration:** Create a unique identifier file at the root of a drive or mounted volume
- **Persistent Identifier Store:** Save registered disk/path associations in `resources/identifiers.json`
- **Cached Lookups:** Resolve identifiers from memory without rereading every file on each request
- **Background Refresh:** Rebuild the cache automatically at startup and on a repeating interval
- **Local-Only Service:** Bind to the host and port defined in `resources/configuration.json`

## Project Structure

```text
DiskIdentifier/
├── deployment/
│   ├── com.service.plist        # macOS launch agent example
│   ├── service.service          # systemd service example
│   └── startup-windows.vbs      # Windows startup helper
├── resources/
│   ├── configuration.json       # Host, port, and universal identifier settings
│   └── identifiers.json         # Persistent disk/path association store
├── scripts/
│   ├── run.bat                  # Windows launcher
│   ├── run.sh                   # macOS/Linux launcher
│   ├── setup.bat                # Windows setup script
│   └── setup.sh                 # macOS/Linux setup script
├── src/
│   └── main.py                  # Flask application entry point
├── LICENSE
├── README.md
└── requirements.txt
```

The code is intentionally compact:
- `src/main.py` contains configuration loading, identifier generation, lookup logic, cache refreshes, and all API routes.
- `resources/configuration.json` controls the bind address, port, and universal identifier file name.
- `resources/identifiers.json` stores the registered disk-root associations.
- `scripts/` provides the quickest way to create the virtual environment, install dependencies, and start the server.

## Installation

### Prerequisites

- Python 3.10 or newer
- Permission to read and write the root of the disk you want to register
- Local access to the machine where the service will run

### Quick Start

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd DiskIdentifier
   ```

2. **Configure the service:**
   Edit [resources/configuration.json](resources/configuration.json) and set the local bind address and port if needed. Leave `universalDiskIdentifierID` blank if you want the application to generate one automatically on first start.

3. **Install dependencies:**
   - Windows: run [scripts/setup.bat](scripts/setup.bat)
   - macOS/Linux: run [scripts/setup.sh](scripts/setup.sh)

4. **Start the server:**
   - Windows: run [scripts/run.bat](scripts/run.bat)
   - macOS/Linux: run [scripts/run.sh](scripts/run.sh)

### Manual Execution

1. **Create and activate a virtual environment**
2. **Install dependencies:**
   ```bash
   python -m pip install -r requirements.txt
   ```
3. **Run the application:**
   ```bash
   python src/main.py
   ```

### Configuration Notes

- `ip` and `port` in [resources/configuration.json](resources/configuration.json) control where the server binds.
- `universalDiskIdentifierID` is the filename used for the identifier file written to disk roots. If it is empty, the service generates and saves one automatically.
- `resources/identifiers.json` is the persistent store for registered disk/path associations.
- The service runs locally only and refreshes the cache every 30 seconds in a daemon thread.

## Usage

The API exposes four endpoints.

### `POST /api/register` or `POST /api/register/<path>`

- **Request type:** `POST`
- **Arguments:** provide the disk root as a path parameter or in a JSON body with `path`.
- **What it does:** validates that the path is a disk root, generates a unique disk identifier, writes an identifier file at the disk root, and stores the association in `resources/identifiers.json`.
- **How it answers:** returns `201 Created` with JSON like `{"disk_identifier": "..."}`. If the root already has an identifier file, the API returns `409`. Invalid paths return `400`.

### `GET /api/locate` or `GET /api/locate/<identifier>`

- **Request type:** `GET`
- **Arguments:** provide the disk identifier as a path parameter or in a JSON body with `disk_identifier`.
- **What it does:** looks up the identifier in the in-memory cache and returns the matching disk root path.
- **How it answers:** returns `200 OK` with JSON like `{"path": "..."}`. Missing identifiers return `400`. Unknown identifiers return `404`.

### `GET /api/identify` or `GET /api/identify/<path>`

- **Request type:** `GET`
- **Arguments:** provide the disk root as a path parameter or in a JSON body with `path`.
- **What it does:** returns the disk identifier currently loaded for the provided disk root (from the in-memory cache).
- **How it answers:** returns `200 OK` with JSON like `{"disk_identifier": "...", "path": "..."}` when an identifier is loaded. If the path is missing or invalid the endpoint returns `400`. If no identifier is loaded for the provided disk root, the endpoint returns `404` with a warning message.

### `DELETE /api/forget` or `DELETE /api/forget/<identifier>`

- **Request type:** `DELETE`
- **Arguments:** provide the disk identifier as a path parameter or in a JSON body with `disk_identifier`.
- **What it does:** removes the identifier file from disk, deletes the persistent record from `resources/identifiers.json`, and removes the association from the in-memory cache.
- **How it answers:** returns `200 OK` with JSON like `{"status": "forgotten", "disk_identifier": "...", "path": "..."}`. Missing identifiers return `400`. Unknown identifiers return `404`.

### `GET /api/health`

- **Request type:** `GET`
- **Arguments:** none
- **What it does:** reports whether the service is running.
- **How it answers:** returns `200 OK` with JSON containing `{"status": "ok"}`.

### Request Rules

- `POST /api/register` requires a disk root, not an arbitrary subfolder.
- `GET /api/locate` and `DELETE /api/forget` require a previously registered disk identifier.
- The identifier file name comes from `universalDiskIdentifierID` in [resources/configuration.json](resources/configuration.json).
- The service only recognizes identifiers that exist in `resources/identifiers.json` and the current in-memory cache.

## Tech Stack

- **Language:** Python 3.10+
- **Web Framework:** Flask
- **Storage:** JSON file for persistent identifier records
- **Concurrency:** Standard library threads for cache refresh
- **Configuration:** JSON file

## License

This project is licensed under the terms specified in [LICENSE](LICENSE).