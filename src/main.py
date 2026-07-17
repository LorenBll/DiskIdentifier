"""DiskIdentifier local web service."""

from __future__ import annotations

import ctypes
import hashlib
import ipaddress
import json
import logging
import os
import socket
import string
import threading
import time
from pathlib import Path

import urllib.error
import urllib.request

from flask import Flask, jsonify, request

from models import PostResponse

logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURATION AND GLOBAL VARIABLES
# ============================================================================

# Service configuration (loaded from configuration.json at startup)
SERVICE_HOST = None
SERVICE_PORT = None
UNIVERSAL_DISK_IDENTIFIER_ID = None

IDENTIFIERS_PATH = Path(__file__).parent.parent / "resources" / "identifiers.json"
DISK_ASSOCIATION_REFRESH_INTERVAL_SECONDS = 30
DISK_ASSOCIATION_CACHE: dict[str, str] = {}
DISK_ASSOCIATION_REVERSE_CACHE: dict[str, str] = {}
DISK_ASSOCIATION_CACHE_LOCK = threading.Lock()

SERVICEHANDLER_HASH = None


# ============================================================================
# CONFIGURATION LOADING
# ============================================================================


def _load_configuration() -> dict:
    """Load configuration from resources/configuration.json."""
    script_dir = Path(__file__).parent
    config_path = script_dir.parent / "resources" / "configuration.json"
    if not config_path.exists():
        raise FileNotFoundError(
            f"Configuration file not found at {config_path}. "
            "Ensure resources/configuration.json exists."
        )

    try:
        with open(config_path, "r", encoding="utf-8-sig") as f:
            config = json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Configuration file at {config_path} contains invalid JSON: {exc}"
        ) from exc
    except Exception as exc:
        raise RuntimeError(
            f"Failed to read configuration file at {config_path}: {exc}"
        ) from exc

    return config


def _save_configuration(config: dict) -> None:
    """Persist configuration back to resources/configuration.json."""
    script_dir = Path(__file__).parent
    config_path = script_dir.parent / "resources" / "configuration.json"

    with open(config_path, "w", encoding="utf-8") as file_handle:
        json.dump(config, file_handle, indent=2)


def _generate_universal_disk_identifier() -> str:
    """Generate a hash-style identifier for this installation."""
    return hashlib.sha256(os.urandom(32)).hexdigest()


def _is_valid_universal_disk_identifier(value: object) -> bool:
    """Check whether a configured universal identifier looks like a SHA-256 hex hash."""
    if not isinstance(value, str):
        return False

    candidate = value.strip()
    return len(candidate) == 64 and all(
        character in string.hexdigits for character in candidate
    )


def _initialize_service_config() -> None:
    """Load service configuration (private mode only)."""
    global SERVICE_HOST, SERVICE_PORT, UNIVERSAL_DISK_IDENTIFIER_ID
    config = _load_configuration()

    # Service binds to loopback only.
    SERVICE_HOST = "127.0.0.1"

    private_config = (
        config.get("private") if isinstance(config.get("private"), dict) else {}
    )
    configured_port = private_config.get("port")
    if configured_port is None:
        configured_port = config.get("port", 49157)

    if isinstance(configured_port, str) and configured_port.isdigit():
        configured_port = int(configured_port)
    if not isinstance(configured_port, int):
        configured_port = 49157

    SERVICE_PORT = configured_port

    universal_identifier = config.get("universalDiskIdentifierID")
    if not _is_valid_universal_disk_identifier(universal_identifier):
        universal_identifier = _generate_universal_disk_identifier()
        config["universalDiskIdentifierID"] = universal_identifier
        _save_configuration(config)
    else:
        universal_identifier = universal_identifier.strip()

    UNIVERSAL_DISK_IDENTIFIER_ID = universal_identifier


def _list_available_disks() -> list[Path]:
    """List available disk roots on the current machine."""
    if os.name == "nt":
        drive_mask = ctypes.windll.kernel32.GetLogicalDrives()
        available_roots: list[Path] = []

        for letter in string.ascii_uppercase:
            if drive_mask & 1:
                available_roots.append(Path(f"{letter}:/"))
            drive_mask >>= 1

        return available_roots

    return [Path("/")]


def _read_disk_identifier_file(disk_root: Path) -> str | None:
    """Read the identifier hash stored at the disk root."""
    if (
        not isinstance(UNIVERSAL_DISK_IDENTIFIER_ID, str)
        or not UNIVERSAL_DISK_IDENTIFIER_ID.strip()
    ):
        return None

    identifier_file = disk_root / f"{UNIVERSAL_DISK_IDENTIFIER_ID}.id"
    try:
        file_exists = identifier_file.exists()
    except OSError:
        # Some Windows drives can raise errors when media is unavailable.
        return None

    if not file_exists:
        return None

    try:
        return identifier_file.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def _is_disk_root(path_value: Path) -> bool:
    """Check whether a path points to a disk root."""
    if os.name == "nt":
        return bool(path_value.drive) and path_value.name == ""

    return path_value == Path("/")


def _load_allowed_disk_ids() -> set[str]:
    """Load the allowed disk IDs from the identifiers store."""
    identifiers_data = _load_identifiers()
    allowed_disk_ids: set[str] = set()

    for item in identifiers_data["identifiers"]:
        if isinstance(item, str) and item.strip():
            allowed_disk_ids.add(item.strip())
            continue

        if isinstance(item, dict):
            for key in ("disk_id", "signature", "identifier", "id"):
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    allowed_disk_ids.add(value.strip())
                    break

    return allowed_disk_ids


def _generate_disk_identifier(disk_root: Path) -> str:
    """Generate a new disk identifier for a disk root."""
    signature_source = disk_root.as_posix()

    try:
        stat_result = disk_root.stat()
    except OSError:
        stat_result = None

    if stat_result is not None:
        signature_source = "|".join(
            [
                signature_source,
                str(stat_result.st_dev),
                str(getattr(stat_result, "st_ino", 0)),
                str(stat_result.st_size),
                str(stat_result.st_mtime_ns),
                os.urandom(16).hex(),
            ]
        )
    else:
        signature_source = "|".join([signature_source, os.urandom(16).hex()])

    return hashlib.sha256(signature_source.encode("utf-8")).hexdigest()


def _persist_disk_identifier(disk_root: Path, disk_identifier: str) -> None:
    """Persist a disk identifier in the identifiers json store."""
    identifiers_data = _load_identifiers()
    identifiers = identifiers_data["identifiers"]
    identifiers.append(disk_identifier)

    IDENTIFIERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(IDENTIFIERS_PATH, "w", encoding="utf-8") as file_handle:
        json.dump({"identifiers": identifiers}, file_handle, indent=2)


def _remove_disk_identifier(disk_identifier: str) -> None:
    """Remove a disk identifier from the identifiers json store."""
    identifiers_data = _load_identifiers()
    filtered_identifiers: list[object] = []

    for item in identifiers_data["identifiers"]:
        if isinstance(item, dict):
            stored_identifier = item.get("disk_id")
            if (
                isinstance(stored_identifier, str)
                and stored_identifier == disk_identifier
            ):
                continue
        elif isinstance(item, str) and item == disk_identifier:
            continue

        filtered_identifiers.append(item)

    IDENTIFIERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(IDENTIFIERS_PATH, "w", encoding="utf-8") as file_handle:
        json.dump({"identifiers": filtered_identifiers}, file_handle, indent=2)


def _cache_disk_association(disk_root: Path, disk_identifier: str) -> None:
    """Store the association between a disk root and a disk identifier in memory."""
    disk_root_path = disk_root.as_posix()
    with DISK_ASSOCIATION_CACHE_LOCK:
        DISK_ASSOCIATION_CACHE[disk_root_path] = disk_identifier
        DISK_ASSOCIATION_REVERSE_CACHE[disk_identifier] = disk_root_path


def _remove_disk_association(disk_root: Path, disk_identifier: str) -> None:
    """Remove the association between a disk root and a disk identifier from memory."""
    disk_root_path = disk_root.as_posix()
    with DISK_ASSOCIATION_CACHE_LOCK:
        DISK_ASSOCIATION_CACHE.pop(disk_root_path, None)
        DISK_ASSOCIATION_REVERSE_CACHE.pop(disk_identifier, None)


def _refresh_disk_associations() -> None:
    """Load path-to-id associations for the current session."""
    allowed_disk_ids = _load_allowed_disk_ids()
    new_associations: dict[str, str] = {}
    new_reverse_associations: dict[str, str] = {}

    for disk_root in _list_available_disks():
        try:
            disk_identifier = _read_disk_identifier_file(disk_root)
            if not isinstance(disk_identifier, str) or not disk_identifier.strip():
                continue

            disk_identifier = disk_identifier.strip()
            if disk_identifier not in allowed_disk_ids:
                continue

            disk_root_path = disk_root.as_posix()
            new_associations[disk_root_path] = disk_identifier
            new_reverse_associations[disk_identifier] = disk_root_path
        except OSError:
            # Skip drive roots that are not currently readable.
            continue

    with DISK_ASSOCIATION_CACHE_LOCK:
        DISK_ASSOCIATION_CACHE.clear()
        DISK_ASSOCIATION_CACHE.update(new_associations)
        DISK_ASSOCIATION_REVERSE_CACHE.clear()
        DISK_ASSOCIATION_REVERSE_CACHE.update(new_reverse_associations)


def _disk_association_refresh_worker() -> None:
    """Refresh disk associations every 30 seconds without blocking the server."""
    while True:
        try:
            _refresh_disk_associations()
        except Exception as exc:
            logger.error(f"Disk association refresh failed: {exc}")

        time.sleep(DISK_ASSOCIATION_REFRESH_INTERVAL_SECONDS)


def _start_disk_association_refresh_loop() -> None:
    """Start the background refresh loop once at startup."""
    refresh_thread = threading.Thread(
        target=_disk_association_refresh_worker,
        name="disk-association-refresh",
        daemon=True,
    )
    refresh_thread.start()


def _normalize_disk_root_value(path_value: str) -> Path:
    """Map a user-provided value to a known local disk root."""
    candidate_value = path_value.strip()
    if not candidate_value:
        raise ValueError("A non-empty path is required.")

    available_roots = _list_available_disks()

    if os.name == "nt":
        candidate_value = candidate_value.replace("\\", "/")
        if (
            len(candidate_value) == 2
            and candidate_value[1] == ":"
            and candidate_value[0].isalpha()
        ):
            candidate_value = f"{candidate_value.upper()}/"

        if (
            len(candidate_value) != 3
            or candidate_value[1] != ":"
            or candidate_value[2] != "/"
            or not candidate_value[0].isalpha()
        ):
            raise ValueError("The provided path must be a disk root.")

        for disk_root in available_roots:
            if disk_root.as_posix().upper() == candidate_value.upper():
                return disk_root

        raise ValueError("The provided path must be a disk root.")

    if candidate_value != "/":
        raise ValueError("The provided path must be a disk root.")

    return available_roots[0]


def _load_identifiers() -> dict:
    """Load the identifier store from disk."""
    if not IDENTIFIERS_PATH.exists():
        return {"identifiers": []}

    try:
        with open(IDENTIFIERS_PATH, "r", encoding="utf-8") as file_handle:
            data = json.load(file_handle)
    except json.JSONDecodeError:
        return {"identifiers": []}

    if not isinstance(data, dict):
        return {"identifiers": []}

    identifiers = data.get("identifiers", [])
    if not isinstance(identifiers, list):
        identifiers = []

    return {"identifiers": identifiers}


def _get_local_device_addresses() -> set[str]:
    """Collect the local network addresses assigned to the current device."""
    local_addresses: set[str] = set()
    candidate_names = {socket.gethostname(), socket.getfqdn()}

    for candidate_name in candidate_names:
        if not candidate_name:
            continue

        try:
            local_addresses.update(
                address_info[4][0]
                for address_info in socket.getaddrinfo(candidate_name, None)
            )
        except OSError:
            pass

        try:
            local_addresses.update(socket.gethostbyname_ex(candidate_name)[2])
        except OSError:
            pass

    for probe_address in ("8.8.8.8", "1.1.1.1"):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as socket_handle:
                socket_handle.connect((probe_address, 80))
                local_addresses.add(socket_handle.getsockname()[0])
        except OSError:
            pass

    normalized_addresses: set[str] = set()
    for address_value in local_addresses:
        try:
            normalized_addresses.add(ipaddress.ip_address(address_value).compressed)
        except ValueError:
            continue

    normalized_addresses.update({"127.0.0.1", "::1"})
    return normalized_addresses


def _is_local_request() -> bool:
    """Check whether the current request originates from the local device."""
    remote_address = request.remote_addr
    if not isinstance(remote_address, str) or not remote_address.strip():
        return False

    try:
        client_ip = ipaddress.ip_address(remote_address.strip())
    except ValueError:
        return False

    if client_ip.is_loopback:
        return True

    return client_ip.compressed in _get_local_device_addresses()


app = Flask(__name__)


@app.before_request
def restrict_to_local_device() -> tuple | None:
    """Reject requests that do not originate from the local device."""
    if request.path.startswith("/api/") and not _is_local_request():
        return _error_response("Local device access only.", 403)

    return None


def _options_response(allowed_methods: list[str]) -> tuple:
    """Return an OPTIONS response with allowed methods."""
    response = jsonify({})
    response.headers["Allow"] = ", ".join(allowed_methods)
    response.headers["Access-Control-Allow-Methods"] = ", ".join(allowed_methods)
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response, 200


def _head_response() -> tuple:
    """Return a HEAD response with no body."""
    response = jsonify({})
    return response, 200


@app.after_request
def set_connection_header(response):
    content_type = response.headers.get("Content-Type", "")
    if content_type.startswith("text/html"):
        response.headers["Connection"] = "keep-alive"
    else:
        response.headers["Connection"] = "close"
    return response


def _error_response(message: str, status_code: int = 400) -> tuple:
    """Return a JSON error response using PostResponse model."""
    data = {"error": message}
    body = json.dumps(data)
    resp = PostResponse(
        status_code=status_code,
        reason="error",
        body=body,
        body_size=len(body),
        headers={"Content-Type": "application/json"},
        json_body=data,
    )
    return jsonify(resp.json_body), resp.status_code


def _success_response(data: dict, status_code: int = 200) -> tuple:
    """Return a JSON success response using PostResponse model."""
    body = json.dumps(data)
    resp = PostResponse(
        status_code=status_code,
        reason="OK",
        body=body,
        body_size=len(body),
        headers={"Content-Type": "application/json"},
        json_body=data,
    )
    return jsonify(resp.json_body), resp.status_code


# ============================================================================
# API ENDPOINTS
# ============================================================================


@app.route("/api/register", methods=["POST", "HEAD", "OPTIONS"])
def register() -> tuple:
    """Register a disk root, create its identifier file, and cache the association."""
    if request.method == "OPTIONS":
        return _options_response(["POST", "HEAD", "OPTIONS"])
    if request.method == "HEAD":
        return _head_response()

    payload = request.get_json(silent=True) or {}
    path_value = payload.get("path") if isinstance(payload, dict) else None

    if not isinstance(path_value, str) or not path_value.strip():
        return _error_response("A non-empty path is required.")

    try:
        disk_root = _normalize_disk_root_value(path_value)
    except (ValueError, OSError, RuntimeError):
        return _error_response("Invalid path provided.")

    if not _is_disk_root(disk_root):
        return _error_response("The provided path must be a disk root.")

    if (
        not isinstance(UNIVERSAL_DISK_IDENTIFIER_ID, str)
        or not UNIVERSAL_DISK_IDENTIFIER_ID.strip()
    ):
        return _error_response("Universal disk identifier is not configured.", 500)

    identifier_file = disk_root / f"{UNIVERSAL_DISK_IDENTIFIER_ID}.id"
    if identifier_file.exists():
        return _error_response("An identifier already exists.", 409)

    disk_identifier = _generate_disk_identifier(disk_root)

    try:
        identifier_file.write_text(disk_identifier, encoding="utf-8")
        _persist_disk_identifier(disk_root, disk_identifier)
    except OSError:
        try:
            if identifier_file.exists():
                identifier_file.unlink()
        except OSError:
            pass
        return _error_response("Failed to create identifier file.", 500)
    except Exception:
        try:
            if identifier_file.exists():
                identifier_file.unlink()
        except OSError:
            pass
        return _error_response("Failed to persist disk identifier.", 500)

    _cache_disk_association(disk_root, disk_identifier)

    return _success_response({"disk_identifier": disk_identifier}, 201)


@app.route("/api/locate", methods=["GET", "HEAD", "OPTIONS"])
def locate() -> tuple:
    """Return the cached disk root for a disk identifier."""
    if request.method == "OPTIONS":
        return _options_response(["GET", "HEAD", "OPTIONS"])
    if request.method == "HEAD":
        return _head_response()

    payload = request.get_json(silent=True) or {}
    identifier_value = payload.get("disk_identifier") if isinstance(payload, dict) else None

    if not isinstance(identifier_value, str) or not identifier_value.strip():
        return _error_response("A disk identifier is required.")

    with DISK_ASSOCIATION_CACHE_LOCK:
        disk_root = DISK_ASSOCIATION_REVERSE_CACHE.get(identifier_value.strip())

    if disk_root is None:
        return _error_response("Disk identifier not found.", 404)

    return _success_response({"path": disk_root})


@app.route("/api/identify", methods=["GET", "HEAD", "OPTIONS"])
def identify() -> tuple:
    """Return the disk identifier for a provided disk root path.

    If the disk does not have a loaded identifier, respond with a warning.
    """
    if request.method == "OPTIONS":
        return _options_response(["GET", "HEAD", "OPTIONS"])
    if request.method == "HEAD":
        return _head_response()

    payload = request.get_json(silent=True) or {}
    path_value = payload.get("path") if isinstance(payload, dict) else None

    if not isinstance(path_value, str) or not path_value.strip():
        return _error_response("A non-empty path is required.")

    try:
        disk_root = _normalize_disk_root_value(path_value)
    except (ValueError, OSError, RuntimeError):
        return _error_response("Invalid path provided.")

    if not _is_disk_root(disk_root):
        return _error_response("The provided path must be a disk root.")

    disk_root_path = disk_root.as_posix()
    with DISK_ASSOCIATION_CACHE_LOCK:
        disk_identifier = DISK_ASSOCIATION_CACHE.get(disk_root_path)

    if disk_identifier is None:
        return _success_response(
            {"warning": "No disk identifier is loaded for the provided disk."},
            404,
        )

    return _success_response({"disk_identifier": disk_identifier, "path": disk_root_path})


@app.route("/api/whoareu", methods=["GET", "HEAD", "OPTIONS"])
def who_are_you() -> tuple:
    """Return the universal disk identifier for this installation."""
    if request.method == "OPTIONS":
        return _options_response(["GET", "HEAD", "OPTIONS"])
    if request.method == "HEAD":
        return _head_response()

    if (
        not isinstance(UNIVERSAL_DISK_IDENTIFIER_ID, str)
        or not UNIVERSAL_DISK_IDENTIFIER_ID.strip()
    ):
        return _error_response("Universal disk identifier is not configured.", 500)

    return _success_response({"universaldiskidentifierid": UNIVERSAL_DISK_IDENTIFIER_ID})


@app.route("/api/forget", methods=["DELETE", "HEAD", "OPTIONS"])
def forget() -> tuple:
    """Delete a disk identifier, remove cache entries, and remove its json record."""
    if request.method == "OPTIONS":
        return _options_response(["DELETE", "HEAD", "OPTIONS"])
    if request.method == "HEAD":
        return _head_response()

    payload = request.get_json(silent=True) or {}
    identifier_value = payload.get("disk_identifier") if isinstance(payload, dict) else None

    if not isinstance(identifier_value, str) or not identifier_value.strip():
        return _error_response("A disk identifier is required.")

    disk_identifier = identifier_value.strip()

    with DISK_ASSOCIATION_CACHE_LOCK:
        disk_root_path = DISK_ASSOCIATION_REVERSE_CACHE.get(disk_identifier)

    if disk_root_path is None:
        return _error_response("Disk identifier not found.", 404)

    disk_root = Path(disk_root_path)
    identifier_file = disk_root / f"{UNIVERSAL_DISK_IDENTIFIER_ID}.id"

    try:
        if identifier_file.exists():
            identifier_file.unlink()
    except OSError:
        return _error_response("Failed to delete identifier file.", 500)

    _remove_disk_identifier(disk_identifier)
    _remove_disk_association(disk_root, disk_identifier)

    return _success_response(
        {
            "status": "forgotten",
            "disk_identifier": disk_identifier,
            "path": disk_root_path,
        }
    )


@app.route("/api/health", methods=["GET", "HEAD", "OPTIONS"])
def health() -> tuple:
    """Health check endpoint."""
    if request.method == "OPTIONS":
        return _options_response(["GET", "HEAD", "OPTIONS"])
    if request.method == "HEAD":
        return _head_response()

    return _success_response(
        {
            "status": "ok",
            "service": "DiskIdentifier",
            "bind_address": SERVICE_HOST,
            "port": SERVICE_PORT,
            "hostname": socket.gethostname(),
            "pid": os.getpid(),
        }
    )


# ============================================================================
# APPLICATION ENTRY POINT
# ============================================================================


def _register_endpoints_with_servicehandler() -> None:
    """Register this service's API endpoints with ServiceHandler."""
    global SERVICEHANDLER_HASH
    if not SERVICEHANDLER_HASH:
        return

    config = _load_configuration()
    sh_port = config.get("servicehandlerPort", 49155)

    endpoints = [
        {
            "verb": "POST",
            "path": "/api/register",
            "path_variables": [],
            "body_schema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute path to a disk root to register."}
                },
                "required": ["path"]
            },
            "description": "Register a disk root, create its identifier file, and cache the association.",
        },
        {
            "verb": "GET",
            "path": "/api/locate",
            "path_variables": [],
            "body_schema": {
                "type": "object",
                "properties": {
                    "disk_identifier": {"type": "string", "description": "Previously registered disk identifier."}
                },
                "required": ["disk_identifier"]
            },
            "description": "Resolve a disk identifier to its cached disk-root path.",
        },
        {
            "verb": "GET",
            "path": "/api/identify",
            "path_variables": [],
            "body_schema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute disk-root path."}
                },
                "required": ["path"]
            },
            "description": "Resolve a disk root to its loaded disk identifier.",
        },
        {
            "verb": "GET",
            "path": "/api/whoareu",
            "path_variables": [],
            "body_schema": {},
            "description": "Return the installation-wide universal disk identifier key name.",
        },
        {
            "verb": "DELETE",
            "path": "/api/forget",
            "path_variables": [],
            "body_schema": {
                "type": "object",
                "properties": {
                    "disk_identifier": {"type": "string", "description": "Identifier to remove."}
                },
                "required": ["disk_identifier"]
            },
            "description": "Delete a registered disk identifier and remove its cache and persistence entries.",
        },
        {
            "verb": "GET",
            "path": "/api/health",
            "path_variables": [],
            "body_schema": {},
            "description": "Service health check with registration statistics.",
        },
    ]

    for ep in endpoints:
        try:
            payload = json.dumps({
                "hash": SERVICEHANDLER_HASH,
                **ep
            }).encode("utf-8")
            req = urllib.request.Request(
                f"http://127.0.0.1:{sh_port}/api/register/endpoint",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 201:
                    logger.info(f"Registered endpoint: {ep['verb']} {ep['path']}")
        except urllib.error.HTTPError as exc:
            if exc.code == 409:
                logger.debug(f"Endpoint already registered: {ep['verb']} {ep['path']}")
            else:
                logger.warning(f"Failed to register endpoint {ep['verb']} {ep['path']} (HTTP {exc.code})")
        except Exception as exc:
            logger.warning(f"Failed to register endpoint {ep['verb']} {ep['path']}: {exc}")


def _servicehandler_keepalive_forever() -> None:
    global SERVICEHANDLER_HASH
    config = _load_configuration()
    ph_port = config.get("servicehandlerPort", 49155)
    service_name = "DiskIdentifier"

    while True:
        time.sleep(15)
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{ph_port}/api/question/service",
                data=json.dumps({"name": service_name}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    continue
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                logger.warning(f"ServiceHandler question failed (HTTP {exc.code})")
                continue
        except Exception as exc:
            logger.warning(f"ServiceHandler question failed: {exc}")
            continue

        try:
            payload = json.dumps({
                "name": service_name,
                "port": SERVICE_PORT,
                "starting_script": str(Path(__file__).resolve().parent.parent / "scripts" / ("run.bat" if os.name == "nt" else "run.sh")),
                "pid": os.getpid(),
                "bind_address": SERVICE_HOST,
                "hostname": socket.gethostname(),
            }).encode("utf-8")

            req = urllib.request.Request(
                f"http://127.0.0.1:{ph_port}/api/register/service",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 201:
                    data = json.loads(resp.read().decode("utf-8"))
                    SERVICEHANDLER_HASH = data.get("hash")
                    logger.info(f"Registered with ServiceHandler, hash={SERVICEHANDLER_HASH[:16]}...")
                    if SERVICEHANDLER_HASH:
                        _register_endpoints_with_servicehandler()
        except Exception as exc:
            logger.warning(f"ServiceHandler registration attempt failed: {exc}")


if __name__ == "__main__":
    try:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

        _initialize_service_config()
        _refresh_disk_associations()
        _start_disk_association_refresh_loop()
    except Exception as exc:
        logger.error(f"Failed to load configuration: {exc}")
        exit(1)

    config = _load_configuration()
    if config.get("servicehandlerEnabled", True):
        servicehandler_thread = threading.Thread(
            target=_servicehandler_keepalive_forever,
            name="servicehandler-keepalive",
            daemon=True,
        )
        servicehandler_thread.start()

    try:
        logger.info("=" * 50)
        logger.info("  Local API Server")
        logger.info("=" * 50)
        logger.info(f"Binding to: http://{SERVICE_HOST}:{SERVICE_PORT}")
        logger.info(f"Mode: private (local only)")
        logger.info("Server starting...")

        app.run(host=SERVICE_HOST, port=SERVICE_PORT, debug=False, threaded=True)

    except KeyboardInterrupt:
        logger.info("=" * 50)
        logger.info("  Server Stopped")
        logger.info("=" * 50)

    except OSError as exc:
        if "Address already in use" in str(exc):
            logger.error(
                f"Port {SERVICE_PORT} is already in use. "
                f"Change the port in resources/configuration.json"
            )
        elif "Permission denied" in str(exc):
            logger.error(
                f"Permission denied to bind to port {SERVICE_PORT}. "
                f"Use a port >= 1024 or run with elevated privileges."
            )
        else:
            logger.error(f"Network binding failed: {exc}")

    except Exception as exc:
        logger.error(f"Server startup failed: {exc}")
