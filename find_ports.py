#!/usr/bin/env python
"""List serial ports with Feetech motors and say which is the leader and which is the follower.

SO100/SO101 leader arms run on a ~5 V bus, follower arms on a ~12 V bus, so the
voltage reported by motor ID 1 identifies the arm without unplugging anything.

    python find_ports.py
    python find_ports.py --json   # machine-readable, for scripts and agents
"""

from __future__ import annotations

import argparse
import glob
import json
import sys

FOLLOWER_MIN_VOLTAGE = 8.0
MAX_MOTOR_ID = 20


def probe(port: str) -> dict | None:
    import scservo_sdk as scs

    handler = scs.PortHandler(port)
    if not handler.openPort():
        return None
    handler.setBaudRate(1_000_000)
    packet = scs.PacketHandler(0)
    try:
        ids = [i for i in range(1, MAX_MOTOR_ID + 1) if packet.ping(handler, i)[1] == scs.COMM_SUCCESS]
        if not ids:
            return None
        raw, result, _ = packet.read1ByteTxRx(handler, ids[0], 62)  # Present_Voltage, 0.1 V units
    finally:
        handler.closePort()
    voltage = raw / 10.0 if result == scs.COMM_SUCCESS else None
    role = None if voltage is None else ("follower" if voltage >= FOLLOWER_MIN_VOLTAGE else "leader")
    return {"port": port, "motor_ids": ids, "voltage": voltage, "role": role}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", action="store_true", help="print JSON instead of a table")
    args = parser.parse_args()

    candidates = sorted(glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*") + glob.glob("/dev/tty.usbmodem*"))
    arms = [info for port in candidates if (info := probe(port))]

    if args.json:
        print(json.dumps(arms, indent=2))
    elif not arms:
        print("No Feetech motors found on any serial port.")
    else:
        for arm in arms:
            missing = "" if len(arm["motor_ids"]) == 6 else f"  <-- expected 6 motors, found {len(arm['motor_ids'])}"
            print(f"{arm['port']}: {arm['role'] or 'unknown':<8} {arm['voltage']:.1f} V  motors {arm['motor_ids']}{missing}")
    sys.exit(0 if arms else 1)


if __name__ == "__main__":
    main()
