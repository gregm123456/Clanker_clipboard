# Clanker_clipboard

**Node target:** Raspberry Pi Zero 2W

Clipboard input device for the Clanker generative AI art installation. Handles four 8-position rotary knobs (resistor-ladder ADC), multiple buttons, and continuously updates a 6-inch grayscale IT8951 ePaper display with user selections. Wirelessly pushes and/or serves live button and knob state to other Clanker system components over the local network (Tailscale).

## Hardware

- Raspberry Pi Zero 2W
- 6-inch grayscale ePaper display (IT8951 controller, SPI)
- Four 8-position rotary knobs via resistor ladders on MCP3008 ADC (SPI)
- Several push buttons (GPIO)

Important hardware precautions from Waveshare:

- Connect all cables before power-on; do not hot-plug the panel/driver board.
- Set the IT8951 board DIP switch to SPI mode before boot.
- Use the panel-specific VCOM value printed on the FPC cable.

This panel's VCOM for Clanker_clipboard is `-2.06`.

## Fresh-device requirements

Before this service can run on a brand-new Pi Zero 2W, the device must have:

- Raspberry Pi OS with Python 3 and `pip`
- A project-local virtual environment at `.venv` (required for all Python commands below)
- SPI enabled (required for both MCP3008 and IT8951)
- Access to `/dev/spidev0.0` and `/dev/spidev0.1`
- Python packages from `requirements.txt`
- IT8951 Python driver installed (not included in `requirements.txt`)
- `.env` created from `.env.example` with `EPAPER_VCOM=-2.06`

Wiring convention (matches picker project):

- ePaper IT8951 on SPI CE0 (`/dev/spidev0.0`)
- MCP3008 ADC on SPI CE1 (`/dev/spidev0.1`)

Waveshare SPI signal mapping for the 6inch HD e-Paper HAT (BCM):

- `5V` -> `5V`
- `GND` -> `GND`
- `MISO` -> `GPIO9`
- `MOSI` -> `GPIO10`
- `SCK` -> `GPIO11`
- `CS` -> `GPIO8` (CE0)
- `RST` -> `GPIO17`
- `HRDY`/`BUSY` -> `GPIO24`

Source: Waveshare wiki, 6inch HD e-Paper HAT, Raspberry Pi (SPI) section:
https://www.waveshare.com/wiki/6inch_HD_e-Paper_HAT

## Provisioning (first time on a new device)

### 1. OS-level setup and SPI enable

```bash
sudo apt update
sudo apt install -y git python3 python3-pip python3-venv

# Enable SPI and reboot so /dev/spidev0.* is created
sudo raspi-config nonint do_spi 0
sudo reboot
```

After reboot, verify SPI nodes exist:

```bash
ls -l /dev/spidev0.0 /dev/spidev0.1
```

If your image does not expose SPI devices after raspi-config, verify boot config:

```bash
grep -n "^dtparam=spi=on" /boot/firmware/config.txt /boot/config.txt 2>/dev/null
```

If missing, add `dtparam=spi=on` to the active config file and reboot.

Waveshare note for some `lg`/`gpiod` demo configurations: use `dtoverlay=spi0-0cs`
(with `dtparam=spi=on` commented) and reboot. For this Clanker service stack, keep
standard SPI enabled and use CE0 for ePaper and CE1 for MCP3008.

### 2. Clone and install Python dependencies

```bash
cd ~
git clone https://github.com/gregm123456/Clanker_clipboard.git
cd Clanker_clipboard
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 3. Install IT8951 driver

For Clanker_clipboard, the best-path is to install the Python IT8951 driver directly
into the project `.venv` and skip building the vendor C demo.

From inside `~/Clanker_clipboard` with `.venv` activated, run:

```bash
# Recommended path (works with this service code)
python -m pip install "git+https://github.com/GregDMeyer/IT8951.git"
```

Confirm installation landed in the active venv:

```bash
python -m pip show IT8951
```

Validate imports:

```bash
python - << 'PY'
import spidev
import RPi.GPIO
from PIL import Image
from IT8951.display import AutoEPDDisplay
print("imports ok")
PY
```

If `imports ok` prints, continue with Clanker diagnostics and service setup. The
vendor C demo is not required for this service.

Optional note: if you independently choose to test Waveshare's upstream C demo,
treat it as separate from Clanker runtime validation. Do not block service
bring-up on C-demo compilation.

### 4. Configure environment file

```bash
cp .env.example .env

grep -q '^EPAPER_VCOM=' .env && sed -i 's/^EPAPER_VCOM=.*/EPAPER_VCOM=-2.06/' .env || echo 'EPAPER_VCOM=-2.06' >> .env
grep -q '^EPAPER_SPI_BUS=' .env && sed -i 's/^EPAPER_SPI_BUS=.*/EPAPER_SPI_BUS=0/' .env || echo 'EPAPER_SPI_BUS=0' >> .env
grep -q '^EPAPER_SPI_DEVICE=' .env && sed -i 's/^EPAPER_SPI_DEVICE=.*/EPAPER_SPI_DEVICE=0/' .env || echo 'EPAPER_SPI_DEVICE=0' >> .env
grep -q '^EPAPER_SPI_HZ=' .env && sed -i 's/^EPAPER_SPI_HZ=.*/EPAPER_SPI_HZ=24000000/' .env || echo 'EPAPER_SPI_HZ=24000000' >> .env
grep -q '^EPAPER_CMD_HZ=' .env && sed -i 's/^EPAPER_CMD_HZ=.*/EPAPER_CMD_HZ=1000000/' .env || echo 'EPAPER_CMD_HZ=1000000' >> .env
grep -q '^EPAPER_TIMEOUT_SECS=' .env && sed -i 's/^EPAPER_TIMEOUT_SECS=.*/EPAPER_TIMEOUT_SECS=10.0/' .env || echo 'EPAPER_TIMEOUT_SECS=10.0' >> .env
grep -q '^EPAPER_READY_PIN=' .env && sed -i 's/^EPAPER_READY_PIN=.*/EPAPER_READY_PIN=24/' .env || echo 'EPAPER_READY_PIN=24' >> .env
grep -q '^EPAPER_RESET_PIN=' .env && sed -i 's/^EPAPER_RESET_PIN=.*/EPAPER_RESET_PIN=17/' .env || echo 'EPAPER_RESET_PIN=17' >> .env
grep -q '^MCP3008_SPI_BUS=' .env && sed -i 's/^MCP3008_SPI_BUS=.*/MCP3008_SPI_BUS=0/' .env || echo 'MCP3008_SPI_BUS=0' >> .env
grep -q '^MCP3008_SPI_DEVICE=' .env && sed -i 's/^MCP3008_SPI_DEVICE=.*/MCP3008_SPI_DEVICE=1/' .env || echo 'MCP3008_SPI_DEVICE=1' >> .env
```

If `.env` already had these keys, edit it so they match exactly:

- `EPAPER_VCOM=-2.06`
- `EPAPER_SPI_BUS=0`
- `EPAPER_SPI_DEVICE=0` (display on CE0)
- `EPAPER_SPI_HZ=24000000`
- `EPAPER_CMD_HZ=1000000`
- `EPAPER_TIMEOUT_SECS=10.0`
- `EPAPER_READY_PIN=24`
- `EPAPER_RESET_PIN=17`
- `MCP3008_SPI_BUS=0`
- `MCP3008_SPI_DEVICE=1` (ADC on CE1)

### 5. Service unit path/user check

The bundled unit file currently assumes:

- user: `pi`
- repo path: `/home/pi/Clanker_clipboard`

If your device uses a different user (for example `gregm`) or a different path, update `deploy/clanker-clipboard.service` before installing it.

For venv-based deployment, ensure `ExecStart` points to the venv interpreter, for example:

```ini
ExecStart=/home/<user>/Clanker_clipboard/.venv/bin/python /home/<user>/Clanker_clipboard/main.py
```

### 6. Install and start service

```bash
bash deploy/install_service.sh
sudo systemctl status clanker-clipboard
```

### Next wiring steps

- Fill in `BUTTON_PINS` in `clipboard/hw.py` with actual GPIO BCM pin numbers.
- Set `EPAPER_VCOM` in `.env` to match your panel's VCOM value (printed on the ribbon cable).
- Keep wiring aligned with picker: ePaper on CE0, MCP3008 on CE1.

## Setup (subsequent installs / dev iterations)

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in device-specific values before running.

## Running

```bash
source .venv/bin/activate
python main.py
```

## Hardware bring-up

These checks are intended for first power-on over SSH to the Pi Zero 2W and do not start the long-running service.

The diagnostics below now auto-load `.env` from the project root, so you do not need to `source .env` first.

1. Confirm SPI device nodes and open tests:

```bash
cd ~/Clanker_clipboard
source .venv/bin/activate
python -m clipboard.diagnostics check-spi
```

2. Probe the MCP3008 on CE1:

```bash
cd ~/Clanker_clipboard
source .venv/bin/activate
python -m clipboard.diagnostics probe-adc --samples 20 --interval 0.25
```

Notes:
- MCP3008 has no identity register, so you cannot positively enumerate it the way you would a USB device.
- A good result is: SPI opens cleanly, raw values stay in the `0..1023` range, and channels change when you move wiring or later attach knobs.
- With no knobs attached yet, floating channels may drift. That still proves the ADC path is alive if reads are stable enough to vary plausibly instead of hard-failing.

3. Probe the IT8951 ready/reset handshake:

```bash
cd ~/Clanker_clipboard
source .venv/bin/activate
python -m clipboard.diagnostics probe-epaper-ready
```

Expected result: after the reset pulse, `HRDY` should go high within the sample window. If it stays low for the full window, the failure is below Python display init and usually means a `BUSY/HRDY` or `RESET` wiring/config issue.

4. Smoke-test the IT8951 ePaper on CE0:

```bash
cd ~/Clanker_clipboard
source .venv/bin/activate
python -m clipboard.diagnostics test-epaper --text "CLANKER EPAPER TEST"
```

If that reports the display as unavailable, verify:
- the `IT8951` Python package or local driver is installed on the Pi
- `EPAPER_VCOM=-2.06` in `.env`
- `EPAPER_SPI_BUS=0` and `EPAPER_SPI_DEVICE=0` in `.env`
- `EPAPER_READY_PIN=24` and `EPAPER_RESET_PIN=17` in `.env`
- DIP switch is set to SPI mode
- the display CS line is on CE0 and the ADC CS line is on CE1

4. Once the diagnostics pass, start iterating on the actual service:

```bash
sudo systemctl restart clanker-clipboard
sudo systemctl status clanker-clipboard
```

## Update path

On the device:

```bash
cd ~/Clanker_clipboard
git pull
sudo systemctl restart clanker-clipboard
```

## Operator notes

- Node: Raspberry Pi Zero 2W
- Connectivity: Tailscale (local network preferred)
- Offline-capable: yes (ePaper and input work without network; state serving requires local network)
- Dependencies: keep lean — no large ML frameworks on Zero 2W
- Python env: use project-local `.venv` for install, diagnostics, and runtime
- Secrets: place device-specific config in `.env` (never commit to GitHub)
- systemd unit: `deploy/clanker-clipboard.service`
