# linux-corsair-headset-controller

A small Python 3 command-line tool for the **Corsair Virtuoso RGB Wireless XT**
headset (SlipStream dongle `1b1c:0a64`) on Linux. It needs no third-party packages,
only Python 3.7+. You don't need ckb-next or any other daemon.

This is the only headset I own, and I currently have no plans to support other models.

The script talks to the dongle directly through `/dev/hidrawN` (USB interface 3).
ckb-next doesn't support this dongle and never takes it over, so the script and
ckb-next can run at the same time.

## Install
Running the installer copies the script to ~/.local/bin/corsairvirtuosoctl, the man page to
~/.local/share/man/man1, and installs the udev rule

```sh
./install.sh
```

Or by hand: run `./corsairvirtuosoctl.py` directly, and copy `70-corsair-headset.rules` to
`/etc/udev/rules.d/` so you can open the device without root. After copying the rule,
replug the dongle.

## Usage

```sh
corsairvirtuosoctl status                  # battery, charging, mic state and current settings
corsairvirtuosoctl sidetone on|off|toggle  # hear your own mic
corsairvirtuosoctl sidetone-volume 40      # 0-100
corsairvirtuosoctl brightness 75           # LED brightness, 0-100
corsairvirtuosoctl sleep-timer 15          # auto-sleep after N idle minutes, 0 = off
```

See `man corsairvirtuosoctl` for details.

## How settings are written

The headset rejects writes while it is in its default hardware mode. For each change,
the script switches the headset to software mode, writes the setting, and switches
back. The headset keeps the new value after switching back.
