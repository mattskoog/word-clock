# Raspberry Pi Zero Installation Instructions

## Preparation Raspbian OS
1. Prepare the necessary hardware:
   1. Raspberry Pi Zero W
   2. microSD card (at least 8GB, 16GB or more recommended)
   3. micro USB power adapter
2. Download the necessary software:
   1. Raspberry Pi Imager: [https://www.raspberrypi.org/software/](https://www.raspberrypi.org/software/)
3. Prepare the SD card:
   1. Download the latest version of Raspberry Pi **Lite** OS for the Raspberry Pi Zero W. Make sure to select the 32-bit version. Choose the Lite version from Raspberry Pi OS (other).
   2. After selecting your storage, click "Next" and then `EDIT SETTINGS`. You'll need to fill in the following settings:
      1. Username/Password
      2. WiFi credentials
      3. Timezone
      4. (Optional) You can set a hostname. You should be able to access your device via SSH using the hostname, depending on your local network configuration.
      5. Switch to the "Services" tab and enable SSH.
   3. Write the image to the SD card.
## Project Installation
1. Insert the SD card into your Raspberry Pi and wait for it to connect to the WiFi.
1. Find the IP address of your Raspberry Pi on your router or remember the hostname.
1. Use your preferred tool to access SSH (e.g., PuTTY on Windows or SSH in the terminal).
1. Connect to your Raspberry Pi via SSH.
1. Set up the project:

   ```bash
   sudo apt update
   sudo apt install git libopenjp2-7 python3 python3-pip
   git clone https://github.com/mattskoog/word-clock.git
   cd word-clock/raspberry-pi/
   sudo pip3 install --break-system-packages -r requirements.txt
   ```

1. Connect your Word Clock following the [device build instructions](device_build.md).
1. Set the time zone so the clock follows daylight saving time. Use your own
   [IANA time zone name](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones):

    ```bash
    sudo timedatectl set-timezone Europe/Warsaw
    ```

   You can skip this and set it later in the web interface instead, where the
   zone is a dropdown and a **Detect** button fills in your device's own zone.

1. To check if everything is working, run the following command (for testing purposes only):

    ```bash
    sudo python3 src/wordclock/main.py --pin D12
    ```

1. To install it as a service (so it starts automatically on device startup), run the following command:

    ```bash
    ./install.sh
    ```

   If your LEDs are on a different pin, or you want the web interface on another
   port, set them first: `LED_PIN=D18 WEB_PORT=8080 ./install.sh`

1. Open `http://<your-pi>:8080` in a browser on the same network to control
   brightness, colors and animations. See [Using the clock](using_the_clock.md).

## Updating an existing installation

Most updates are a pull and a restart — no reinstall, and no dependency step:

```bash
cd ~/word-clock && git pull && sudo systemctl restart word_clock.service
```

Re-run `./install.sh` only when the service definition itself changes, which
means a new command line option, a different LED pin or a different web port.
The release that added the web interface is one of those, so coming from an
older version the first update is:

```bash
cd ~/word-clock && git pull && cd raspberry-pi && ./install.sh
```

Re-run `sudo pip3 install --break-system-packages -r requirements.txt` only if
`requirements.txt` changed; the web interface itself adds no new packages.

Your settings live in `raspberry-pi/wordclock.json`, which is not tracked by
git, so pulling never overwrites them and reinstalling leaves an existing file
alone. The single `heart_art_small.gif` now sits in `raspberry-pi/gifs/`
alongside eleven others, and the old `--gif <file>` argument still works if you
prefer one fixed animation.