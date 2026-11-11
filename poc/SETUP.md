# ArcticChain Level-1 Setup Guide (Raspberry Pi CM5)

Goal: from a blank CM5 IO Board to a running ArcticChain agent in under 2 hours.

## 1. Flash the OS

- **OS:** Raspberry Pi OS Lite (64-bit, Bookworm) — no desktop needed
- **Tool:** Raspberry Pi Imager → "Raspberry Pi OS (other)" → Lite 64-bit
- **In Imager settings (gear icon):**
  - Hostname: `arcticchain-01`
  - Enable SSH, set user `arctic` + password
  - Configure Wi-Fi (for first boot only — mesh takes over after)
  - Set locale: `en_CA.UTF-8`, timezone: your region (e.g. `America/Edmonton`)

## 2. First boot & update

```bash
ssh arctic@arcticchain-01.local
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y git python3-pip python3-venv i2c-tools libgpiod-dev \
    minicom screen ppp lighttpd
```

## 3. Enable interfaces (`/boot/firmware/config.txt` — CM5 uses `firmware` not `boot`)

```ini
# --- ArcticChain interfaces ---
dtparam=i2c_arm=on
dtparam=spi=on
dtparam=uart0=on          # 4G/LTE HAT UART (GPIO 14/15)
dtoverlay=spi1-3cs        # second SPI bus for LoRa (GPIO 16-21)
dtoverlay=gpio-shutdown   # safe shutdown on power loss
disable_overscan=1
```

Reboot: `sudo reboot`.

## 4. Verify hardware

```bash
# I2C devices (E-Ink + LoRa may show here)
i2cdetect -y 1
i2cdetect -y 0

# UART for LTE modem
ls /dev/serial*
# talk to modem: minicom -D /dev/ttyAMA0 -b 115200
# AT           -> OK
# AT+CPIN?     -> +CPIN: READY
# AT+CSQ       -> signal quality

# LoRa SPI
ls /dev/spidev*
```

## 5. Build the ArcticChain agent

```bash
# Rust toolchain (if building from this repo)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source ~/.cargo/env

# Or run the Level-1 Python agent (poc/arcticchain_agent.py)
sudo cp poc/arcticchain-agent.service /etc/systemd/system/
sudo cp poc/arcticchain_agent.py /opt/arcticchain/
sudo systemctl enable --now arcticchain-agent
journalctl -u arcticchain-agent -f
```

## 6. Acceptance test (the demo)

With **two** units powered on:

```bash
# On unit A
curl -X POST http://localhost:8080/message \
  -d '{"to":"broadcast","text":"Mesh test from Lac La Biche"}'

# On unit B (within LoRa range, no SIM/Wi-Fi)
curl http://localhost:8080/inbox
# -> {"messages":[{"from":"arcticchain-01","text":"Mesh test...","rssi":-87}]}
```

Then toggle airplane mode on the 4G HAT — the mesh message must still deliver.
That is the whole pitch in one test: **connectivity without towers**.

## 7. OTA updates (optional, Level 1)

- Git-based: `git pull` + `systemctl restart arcticchain-agent` over mesh
- Content-addressed bundles signed with the community Ed25519 key
  (matches `arcticchain_hal::auth` — same key format)
