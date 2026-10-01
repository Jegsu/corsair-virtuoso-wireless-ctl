#!/usr/bin/env python3
"""Control a Corsair Virtuoso RGB Wireless XT headset (SlipStream dongle 1b1c:0a64).

Standard library only. Talks to the dongle directly via /dev/hidrawN (USB interface 3).

Protocol: every frame is [0x02][0x09][op][register][0x00][value...] zero padded to
64 bytes, written as HID output report 0x02; op is 0x01 = write, 0x02 = read. The
response comes back as input report 0x01: byte 3 is a status (0 = ok), data from byte 4.
"""
import argparse
import glob
import os
import select
import sys

VID, PID = 0x1B1C, 0x0A64
HID_INTERFACE = "03"
FRAME_SIZE = 64
ROUTING = 0x09
OP_WRITE, OP_READ = 0x01, 0x02

REG_BRIGHTNESS = 0x02       # 0-1000
REG_MODE = 0x03
REG_SLEEP_ENABLE = 0x0d
REG_SLEEP_TIMEOUT = 0x0e    # milliseconds
REG_BATTERY = 0x0f          # 0-1000
REG_CHARGE_STATE = 0x10     # 1 = charging, 2 = discharging, 3 = full
REG_FIRMWARE = 0x13
REG_SIDETONE = 0x46         # inverted: 0 = on, 1 = off
REG_SIDETONE_VOLUME = 0x47  # 0-1000
REG_CABLE = 0x48            # 1 = USB cable connected
REG_VOLTAGE = 0x53          # battery millivolts
REG_MIC_MUTED = 0x8e

CHARGE_STATES = {1: "charging", 2: "discharging", 3: "full"}

MODE_HARDWARE, MODE_SOFTWARE = 1, 2


def find_hidraw():
    want = "HID_ID=0003:%08X:%08X" % (VID, PID)
    for node in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
        dev = os.path.realpath(node + "/device")
        try:
            with open(dev + "/uevent") as f:
                if want not in f.read():
                    continue
            with open(dev + "/../bInterfaceNumber") as f:
                if f.read().strip() == HID_INTERFACE:
                    return "/dev/" + os.path.basename(node)
        except OSError:
            continue
    sys.exit("headset dongle %04x:%04x not found" % (VID, PID))


def transfer(fd, op, reg, value=0, timeout=2.0):
    # Drop anything unsolicited still queued so we read our own response.
    while select.select([fd], [], [], 0)[0]:
        os.read(fd, FRAME_SIZE)
    frame = bytes([0x02, ROUTING, op, reg, 0x00]) + value.to_bytes(4, "little")
    os.write(fd, frame.ljust(FRAME_SIZE, b"\0"))
    while True:
        if not select.select([fd], [], [], timeout)[0]:
            raise TimeoutError("no response from headset (is it switched on?)")
        resp = os.read(fd, FRAME_SIZE)
        if resp and resp[0] == 0x01:
            break
    if resp[3]:
        raise OSError("headset rejected register 0x%02x (status 0x%02x)" % (reg, resp[3]))
    return int.from_bytes(resp[4:8], "little")


def get(fd, reg):
    return transfer(fd, OP_READ, reg)


def put(fd, reg, value):
    transfer(fd, OP_WRITE, reg, value)


def status(fd):
    fw = get(fd, REG_FIRMWARE)
    sleep = "%d min" % (get(fd, REG_SLEEP_TIMEOUT) // 60000)
    print("firmware:    %d.%d.%d" % (fw & 0xff, fw >> 8 & 0xff, fw >> 16 & 0xff))
    charge = get(fd, REG_CHARGE_STATE)
    print("battery:     %d%%, %s, %.2f V" % (get(fd, REG_BATTERY) // 10,
                                          CHARGE_STATES.get(charge, "unknown (%d)" % charge),
                                          get(fd, REG_VOLTAGE) / 1000))
    print("cable:       %s" % ("connected" if get(fd, REG_CABLE) else "disconnected"))
    print("mic:         %s" % ("muted" if get(fd, REG_MIC_MUTED) else "unmuted"))
    print("sidetone:    %s, volume %d%%" % ("off" if get(fd, REG_SIDETONE) else "on",
                                           get(fd, REG_SIDETONE_VOLUME) // 10))
    print("brightness:  %d%%" % (get(fd, REG_BRIGHTNESS) // 10))
    print("sleep timer: %s" % (sleep if get(fd, REG_SLEEP_ENABLE) else "off"))


def sidetone(fd, state):
    on = get(fd, REG_SIDETONE) != 0 if state == "toggle" else state == "on"
    put(fd, REG_SIDETONE, 0 if on else 1)
    print("sidetone %s" % ("on" if on else "off"))


def sidetone_volume(fd, pct):
    put(fd, REG_SIDETONE_VOLUME, pct * 10)


def brightness(fd, pct):
    put(fd, REG_BRIGHTNESS, pct * 10)


def sleep_timer(fd, minutes):
    put(fd, REG_SLEEP_ENABLE, 1 if minutes else 0)
    if minutes:
        put(fd, REG_SLEEP_TIMEOUT, minutes * 60000)


def ranged(lo, hi):
    def parse(s):
        v = int(s)
        if not lo <= v <= hi:
            raise argparse.ArgumentTypeError("must be %d-%d" % (lo, hi))
        return v
    return parse


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="show battery, mic state and current settings").set_defaults(fn=status)
    s = sub.add_parser("sidetone", help="hear your own mic")
    s.add_argument("value", choices=("on", "off", "toggle"))
    s.set_defaults(fn=sidetone)
    s = sub.add_parser("sidetone-volume", help="sidetone level")
    s.add_argument("value", type=ranged(0, 100), metavar="percent")
    s.set_defaults(fn=sidetone_volume)
    s = sub.add_parser("brightness", help="LED brightness")
    s.add_argument("value", type=ranged(0, 100), metavar="percent")
    s.set_defaults(fn=brightness)
    s = sub.add_parser("sleep-timer", help="auto-sleep after idle minutes, 0 = off")
    s.add_argument("value", type=ranged(0, 60), metavar="minutes")
    s.set_defaults(fn=sleep_timer)
    args = p.parse_args()

    path = find_hidraw()
    try:
        fd = os.open(path, os.O_RDWR)
        try:
            if args.fn is status:
                status(fd)
            else:
                # Writes are rejected (status 0x09) in hardware mode. Values written in
                # software mode are kept after switching back to hardware mode.
                put(fd, REG_MODE, MODE_SOFTWARE)
                try:
                    args.fn(fd, args.value)
                finally:
                    put(fd, REG_MODE, MODE_HARDWARE)
        finally:
            os.close(fd)
    except PermissionError as e:
        sys.exit("%s\nInstall the udev rule (see README) or run as root." % e)
    except (OSError, TimeoutError) as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
