# Clanker_clipboard

**Node target:** Raspberry Pi Zero 2W

Clipboard input device for the Clanker generative AI art installation. Handles four 8-position rotary knobs (resistor-ladder ADC), multiple buttons, and continuously updates a 6-inch grayscale IT8951 ePaper display with user selections. Wirelessly pushes and/or serves live button and knob state to other Clanker system components over the local network (Tailscale).

## Hardware

- Raspberry Pi Zero 2W
- 6-inch grayscale ePaper display (IT8951 controller, SPI)
- Four 8-position rotary knobs via resistor ladders on MCP3008 ADC (SPI)
- Several push buttons (GPIO)

## Setup

```bash
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in device-specific values before running.

## Running

```bash
python main.py
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
- Secrets: place device-specific config in `.env` (never commit to GitHub)
- systemd unit: `deploy/clanker-clipboard.service`
