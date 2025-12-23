"""
Bambu AMS & Printer Info Tool (HTTP-only version)

This script queries a Bambu Lab printer's local API to retrieve:
  - AMS (Automatic Material System) information
  - Printer job status
  - Temperatures (nozzle, bed, chamber)
  - Error/warning states

Features:
  - On-demand updates (no persistent connection)
  - A --test-connection mode to print raw JSON for debugging
  - Auto-mapping of AMS fields to handle firmware differences

Future enhancement:
  - WebSocket support could be added for live updates without polling.
    The WebSocket endpoint is usually: ws://<ip>/ws?access_code=<code>
    This would allow real-time AMS monitoring, but requires more code and testing.

Developer Notes (Other API Data You Can Pull Later):
----------------------------------------------------
The `/api/v1/printer/status` endpoint can return many fields, depending on firmware:
  - Printer metadata:
      model, serial number, firmware version
  - Job status:
      state (printing, idle, paused), file name, progress %, time remaining
  - Temperatures:
      nozzle, bed, chamber
  - Fans:
      part cooling fan speed, chamber fan speed
  - AMS:
      humidity, slot status, filament type/color, AMS firmware
  - Error/warning states:
      filament runout, jams, overheating, door open
  - Network info:
      IP, Wi-Fi signal strength
  - Motion:
      axis positions, speeds

You can extend `update_from_printer()` to parse these fields from the JSON.
"""

import json
import os
import requests
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from dotenv import load_dotenv


def load_bambu_config_from_conf(
    serial_number: str | None = None
) -> dict[str, str | None]:
    r"""
    Load Bambu Lab printer configuration from BambuStudio.conf file.
    
    The BambuStudio.conf file is located at:
    - Windows: %APPDATA%\BambuStudio\BambuStudio.conf
    - macOS: ~/Library/Application Support/BambuStudio/BambuStudio.conf
    - Linux: ~/.config/BambuStudio/BambuStudio.conf
    
    The file contains JSON with structure:
    {
        "access_code": {
            "{serial_number}": "{access_code}"
        }
    }
    
    Args:
        serial_number: Optional serial number to look up. If not provided,
                      returns the first printer found.
    
    Returns:
        Dict with 'serial_number' and 'access_code' keys (values may be None).
    """
    result = {"serial_number": None, "access_code": None}
    
    # Determine config file path based on OS
    if os.name == "nt":  # Windows
        config_path = Path(os.environ.get("APPDATA", "")) / "BambuStudio" / "BambuStudio.conf"
    elif os.uname().sysname == "Darwin":  # macOS
        config_path = Path.home() / "Library" / "Application Support" / "BambuStudio" / "BambuStudio.conf"
    else:  # Linux
        config_path = Path.home() / ".config" / "BambuStudio" / "BambuStudio.conf"
    
    if not config_path.exists():
        return result
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)
        
        access_codes = config_data.get("access_code", {})
        
        if not access_codes:
            return result
        
        # If serial number provided, look it up specifically
        if serial_number:
            access_code = access_codes.get(serial_number)
            if access_code:
                result["serial_number"] = serial_number
                result["access_code"] = access_code
        else:
            # Return first printer found
            first_serial = next(iter(access_codes.keys()), None)
            if first_serial:
                result["serial_number"] = first_serial
                result["access_code"] = access_codes[first_serial]
    
    except (json.JSONDecodeError, OSError) as e:
        print(f"⚠️  Warning: Could not read BambuStudio.conf: {e}")
    
    return result


def get_config_value(
    cli_value: str | None,
    env_var_name: str,
    conf_value: str | None = None,
    default: str | None = None
) -> str | None:
    """
    Get configuration value with proper priority order.
    
    Priority (highest to lowest):
    1. Command-line argument (explicit user intent)
    2. Environment variable (session/system config)
    3. .env file value (project-level config, loaded via dotenv)
    4. BambuStudio.conf value (application config)
    5. Default value (fallback)
    
    Args:
        cli_value: Value from command-line argument
        env_var_name: Name of environment variable to check
        conf_value: Value from BambuStudio.conf file
        default: Default value if nothing else found
    
    Returns:
        The highest-priority value found, or None if nothing found.
    """
    # Priority 1: Command-line argument
    if cli_value is not None:
        return cli_value
    
    # Priority 2 & 3: Environment variable (includes .env file if loaded)
    env_value = os.environ.get(env_var_name)
    if env_value is not None:
        return env_value
    
    # Priority 4: BambuStudio.conf value
    if conf_value is not None:
        return conf_value
    
    # Priority 5: Default value
    return default

# ============================================================
# FUTURE ENHANCEMENTS ROADMAP
# ============================================================
# 1. WebSocket Live Updates
#    - Use `websocket-client` to connect to ws://<ip>/ws?access_code=<code>
#    - Receive real-time AMS and printer updates without polling.
#    - Example:
#        import websocket
#        def on_message(ws, msg): print(msg)
#        ws = websocket.WebSocketApp(f"ws://{PRINTER_IP}/ws?access_code={ACCESS_CODE}",
#                                    on_message=on_message)
#        ws.run_forever()
#
# 2. Printer Fan Speeds
#    - Some firmware returns fan speeds in `data["fans"]` or `data["print"]["fans"]`.
#    - Example:
#        fans = data.get("fans", {})
#        part_cooling = fans.get("part_cooling_fan_speed")
#        chamber_fan = fans.get("chamber_fan_speed")
#
# 3. Network Info
#    - Useful for diagnostics (Wi-Fi signal, IP, MAC).
#    - Example:
#        net_info = data.get("network", {})
#        wifi_signal = net_info.get("wifi_signal")
#        ip_addr = net_info.get("ip")
#
# 4. Motion / Axis Positions
#    - For debugging mechanical issues.
#    - Example:
#        motion = data.get("motion", {})
#        x_pos = motion.get("x")
#        y_pos = motion.get("y")
#        z_pos = motion.get("z")
#
# 5. Filament Usage Stats
#    - Some firmware tracks filament length used per job.
#    - Example:
#        filament_stats = data.get("filament", {})
#        used_mm = filament_stats.get("used_length_mm")
#
# 6. Multiple AMS Units
#    - If you have more than one AMS, `data["ams"]` may be a list.
#    - Loop through each AMS and store separately.
#
# 7. Error History
#    - Some firmware returns a log of past errors/warnings.
#    - Example:
#        error_history = data.get("error_history", [])
#
# 8. Job Queue
#    - If printer supports queued jobs, parse `data["job_queue"]`.
#
# 9. Save to File
#    - Save summary or raw JSON to a timestamped file for logging.
#    - Example:
#        with open(f"printer_status_{datetime.now():%Y%m%d_%H%M%S}.json", "w") as f:
#            json.dump(data, f, indent=2)
#
# 10. Remote Commands (CAUTION)
#    - Some endpoints allow sending commands (pause, resume, stop).
#    - Requires POST requests with correct JSON payload.
#    - Example:
#        requests.post(f"http://{PRINTER_IP}/api/v1/printer/control",
#                      headers={"X-Access-Code": ACCESS_CODE},
#                      json={"command": "pause"})
#
# ============================================================

class BambuAMS:
    """
    Class to store and manage Bambu Lab AMS and printer information.
    """

    def __init__(self, slot_count: int = 4):
        # AMS fields
        self.serial_number: Optional[str] = None
        self.firmware_version: Optional[str] = None
        self.slot_count = slot_count
        self.humidity: Optional[float] = None
        self.slots: List[Dict[str, Optional[str]]] = [
            {"slot": i + 1, "filament_type": None, "color": None, "status": "empty"}
            for i in range(slot_count)
        ]

        # Printer fields
        self.printer_model: Optional[str] = None
        self.printer_fw: Optional[str] = None
        self.job_state: Optional[str] = None
        self.job_file: Optional[str] = None
        self.progress: Optional[float] = None
        self.time_remaining: Optional[int] = None
        self.nozzle_temp: Optional[float] = None
        self.bed_temp: Optional[float] = None
        self.chamber_temp: Optional[float] = None
        self.errors: List[str] = []

        self.last_updated: Optional[datetime] = None

    def update_from_printer(self, printer_ip: str, access_code: str):
        """
        Pull AMS and printer data from the printer's local API and auto-map fields.
        """
        try:
            url = f"http://{printer_ip}/api/v1/printer/status"
            headers = {"X-Access-Code": access_code}
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status()

            data = response.json()

            # --- AMS Data ---
            ams_info = None
            for key in ("ams", "AMS", "ams_info"):
                if key in data:
                    ams_info = data[key]
                    break
                if "print" in data and key in data["print"]:
                    ams_info = data["print"][key]
                    break

            if ams_info:
                self.serial_number = ams_info.get("serial_number") or ams_info.get("sn") or self.serial_number
                self.firmware_version = ams_info.get("firmware_version") or ams_info.get("fw") or self.firmware_version
                self.humidity = ams_info.get("humidity") or ams_info.get("hum") or self.humidity

                slots_data = ams_info.get("slots") or ams_info.get("slot_info") or []
                for i, slot in enumerate(slots_data):
                    if i < self.slot_count:
                        self.slots[i].update({
                            "filament_type": slot.get("type") or slot.get("material"),
                            "color": slot.get("color"),
                            "status": slot.get("status", "empty")
                        })

            # --- Printer Metadata ---
            self.printer_model = data.get("printer_model") or data.get("model") or self.printer_model
            self.printer_fw = data.get("firmware_version") or data.get("fw") or self.printer_fw

            # --- Job Status ---
            if "print" in data:
                self.job_state = data["print"].get("state") or self.job_state
                self.job_file = data["print"].get("file") or self.job_file
                self.progress = data["print"].get("progress") or self.progress
                self.time_remaining = data["print"].get("time_remaining") or self.time_remaining

            # --- Temperatures ---
            temps = data.get("temperature") or {}
            self.nozzle_temp = temps.get("nozzle") or self.nozzle_temp
            self.bed_temp = temps.get("bed") or self.bed_temp
            self.chamber_temp = temps.get("chamber") or self.chamber_temp

            # --- Errors ---
            self.errors = data.get("errors") or []

            self.last_updated = datetime.now()

        except requests.RequestException as e:
            print(f"❌ Error fetching printer data: {e}")

    def summary(self) -> str:
        slot_info = "\n".join(
            f"  Slot {s['slot']}: {s['status']} "
            f"({s['filament_type'] or '-'}, {s['color'] or '-'})"
            for s in self.slots
        )
        error_info = "\n".join(f"  - {err}" for err in self.errors) if self.errors else "  None"

        return (
            f"=== Bambu Printer Info ===\n"
            f"Model: {self.printer_model or '-'}\n"
            f"Firmware: {self.printer_fw or '-'}\n"
            f"Job State: {self.job_state or '-'}\n"
            f"File: {self.job_file or '-'}\n"
            f"Progress: {self.progress if self.progress is not None else '-'}%\n"
            f"Time Remaining: {self.time_remaining if self.time_remaining is not None else '-'} sec\n"
            f"Nozzle Temp: {self.nozzle_temp if self.nozzle_temp is not None else '-'}°C\n"
            f"Bed Temp: {self.bed_temp if self.bed_temp is not None else '-'}°C\n"
            f"Chamber Temp: {self.chamber_temp if self.chamber_temp is not None else '-'}°C\n"
            f"Errors:\n{error_info}\n\n"
            f"=== AMS Info ===\n"
            f"Serial Number: {self.serial_number or '-'}\n"
            f"Firmware: {self.firmware_version or '-'}\n"
            f"Humidity: {self.humidity if self.humidity is not None else '-'}%\n"
            f"Last Updated: {self.last_updated.strftime('%Y-%m-%d %H:%M:%S') if self.last_updated else '-'}\n"
            f"Slots:\n{slot_info}"
        )


def test_connection(printer_ip: str, access_code: str):
    """
    Test connection to the printer and print raw JSON.
    """
    try:
        url = f"http://{printer_ip}/api/v1/printer/status"
        headers = {"X-Access-Code": access_code}
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        print("✅ Connection successful! Raw JSON from printer:\n")
        print(json.dumps(response.json(), indent=2))
    except requests.RequestException as e:
        print(f"❌ Connection failed: {e}")


if __name__ == "__main__":
    # Load .env file if present (must be done before accessing os.environ)
    load_dotenv()
    
    parser = argparse.ArgumentParser(
        description="Bambu AMS & Printer Info Tool",
        epilog="""Configuration priority (highest to lowest):
  1. Command-line arguments (--ip, --access-code, --serial-number)
  2. Environment variables (BAMBULAB_PRINTER_IP, BAMBULAB_ACCESS_CODE, BAMBULAB_SERIAL_NUMBER)
  3. .env file values (automatically loaded if present)
  4. BambuStudio.conf file (loaded with --use-conf)

Example .env file:
  BAMBULAB_PRINTER_IP=192.168.1.100
  BAMBULAB_ACCESS_CODE=12345678
  BAMBULAB_SERIAL_NUMBER=01S00C123456789
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--ip",
        help="Printer IP address (or set BAMBULAB_PRINTER_IP env var)"
    )
    parser.add_argument(
        "--access-code",
        help="LAN access code (or set BAMBULAB_ACCESS_CODE env var)"
    )
    parser.add_argument(
        "--serial-number",
        help="Printer serial number for conf file lookup (or set BAMBULAB_SERIAL_NUMBER env var)"
    )
    parser.add_argument(
        "--use-conf",
        action="store_true",
        help="Load access code from BambuStudio.conf file (lower priority than CLI/env)"
    )
    parser.add_argument(
        "--test-connection",
        action="store_true",
        help="Test connection and print raw JSON"
    )
    args = parser.parse_args()
    
    # Load values from BambuStudio.conf if requested
    conf_values = {"serial_number": None, "access_code": None}
    if args.use_conf:
        # If serial number provided, look up that specific printer
        serial_for_lookup = get_config_value(
            args.serial_number,
            "BAMBULAB_SERIAL_NUMBER",
            None
        )
        conf_values = load_bambu_config_from_conf(serial_for_lookup)
        if conf_values["serial_number"]:
            print(f"📋 Loaded config from BambuStudio.conf for printer: {conf_values['serial_number']}")
    
    # Resolve final configuration values with proper priority
    printer_ip = get_config_value(
        args.ip,
        "BAMBULAB_PRINTER_IP",
        None  # No conf file value for IP
    )
    access_code = get_config_value(
        args.access_code,
        "BAMBULAB_ACCESS_CODE",
        conf_values["access_code"]
    )
    serial_number = get_config_value(
        args.serial_number,
        "BAMBULAB_SERIAL_NUMBER",
        conf_values["serial_number"]
    )
    
    # Validate required values
    if not printer_ip:
        parser.error("Printer IP required: use --ip, BAMBULAB_PRINTER_IP env var, or .env file")
    if not access_code:
        parser.error("Access code required: use --access-code, BAMBULAB_ACCESS_CODE env var, .env file, or --use-conf")
    
    # Show configuration source for transparency
    print(f"🔧 Using printer IP: {printer_ip}")
    if serial_number:
        print(f"🔧 Using serial number: {serial_number}")
    print()
    
    if args.test_connection:
        test_connection(printer_ip, access_code)
    else:
        ams = BambuAMS()
        ams.update_from_printer(printer_ip, access_code)
        print(ams.summary())
