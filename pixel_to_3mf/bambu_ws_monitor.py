"""
Bambu Printer WebSocket AMS Monitor (Final Version)

Connects to a Bambu Lab printer's WebSocket API and prints real-time messages.

Modes:
  --mode full     → Print all JSON messages (debugging)
  --mode ams      → Only print AMS slot/humidity changes
                    (with change detection to avoid duplicate output)

Requirements:
    pip install websocket-client

Usage:
    python bambu_ws_monitor.py --ip 192.168.1.50 --access-code e3f6b787 --mode ams
"""

import argparse
import json
import websocket

# Store last AMS state for change detection
last_ams_state = None


def ams_state_changed(new_state):
    """Compare new AMS state to last known state."""
    global last_ams_state
    if last_ams_state != new_state:
        last_ams_state = new_state
        return True
    return False


def on_message(ws, message):
    """Called when a message is received from the printer."""
    try:
        data = json.loads(message)

        if args.mode == "full":
            print("\n📡 Received update:")
            print(json.dumps(data, indent=2))

        elif args.mode == "ams":
            # Try to find AMS data in common locations
            ams_info = None
            for key in ("ams", "AMS", "ams_info"):
                if key in data:
                    ams_info = data[key]
                    break
                if "print" in data and key in data["print"]:
                    ams_info = data["print"][key]
                    break

            if ams_info:
                # Extract relevant AMS state for change detection
                slots = ams_info.get("slots") or ams_info.get("slot_info") or []
                state_snapshot = {
                    "humidity": ams_info.get("humidity"),
                    "slots": [
                        {
                            "slot": slot.get("slot"),
                            "status": slot.get("status"),
                            "type": slot.get("type") or slot.get("material"),
                            "color": slot.get("color")
                        }
                        for slot in slots
                    ]
                }

                if ams_state_changed(state_snapshot):
                    print("\n=== AMS Update ===")
                    print(f"Humidity: {state_snapshot['humidity']}")
                    for slot in state_snapshot["slots"]:
                        print(f"  Slot {slot['slot']}: {slot['status']} "
                              f"({slot['type']}, {slot['color']})")
                # else: no change, so do nothing

    except json.JSONDecodeError:
        print("⚠ Received non-JSON message:", message)


def on_error(ws, error):
    """Called when an error occurs."""
    print(f"❌ WebSocket error: {error}")


def on_close(ws, close_status_code, close_msg):
    """Called when the connection is closed."""
    print(f"🔌 WebSocket closed: {close_status_code} {close_msg}")


def on_open(ws):
    """Called when the connection is established."""
    print(f"✅ Connected to printer WebSocket in '{args.mode}' mode. Waiting for updates...")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bambu Printer WebSocket AMS Monitor")
    parser.add_argument("--ip", required=True, help="Printer IP address")
    parser.add_argument("--access-code", required=True, help="LAN access code")
    parser.add_argument("--mode", choices=["full", "ams"], default="full",
                        help="Output mode: 'full' for all JSON, 'ams' for AMS-only updates with change detection")
    args = parser.parse_args()

    ws_url = f"ws://{args.ip}/ws?access_code={args.access_code}"
    print(f"Connecting to {ws_url} ...")

    ws = websocket.WebSocketApp(
        ws_url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )

    try:
        ws.run_forever()
    except KeyboardInterrupt:
        print("\n🛑 Stopping WebSocket monitor.")
