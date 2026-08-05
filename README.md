# Word Clock Project
## Overview
The Word Clock project features two main platforms: ESP32 and Raspberry Pi. This project allows you to display the time in a creative word format and includes functionalities for handling GIF animations.


You can find printing models on https://makerworld.com/en/models/686196#profileId-614840


## [Device Build Instructions here ](docs/device_build.md)

![Word Clock demo](wordclock.jpg)
## Directory Structure
```
word-clock-main/
├── .gitignore
├── README.md
├── esp/
│   └── wordclock/
└── raspberry-pi/
    ├── gifs/                       # twelve animations played on the hour
    ├── tools/
    │   └── make_animations.py      # regenerates the bundled animations
    ├── install.sh
    ├── requirements.txt
    ├── src/
    │   └── wordclock/
    │       ├── __init__.py
    │       ├── clock_display_hal.py  # LED matrix and word-to-LED mapping
    │       ├── gif.py                # animation library and playback
    │       ├── main.py               # entry point and render loop
    │       ├── settings.py           # persisted, thread-safe settings
    │       ├── themes.py             # color themes
    │       ├── timekeeper.py         # time zone / daylight saving handling
    │       ├── webui.py              # local web interface
    │       └── word_clock.py         # time to words
    └── sync.sh
```

## Setup Instructions

### Raspberry Pi

Docs for Raspberry Pi installation can be found [here](docs/installation_raspberry.md)

Once installed, the Raspberry Pi build offers:

- **A web interface** at `http://<your-pi>:8080` for brightness, color theme,
  animations and time zone, with a live preview of the clock face and an
  explicit save — see [Using the clock](docs/using_the_clock.md)
- **Color themes**: phases of the day, solid, gradient, rainbow, color cycle and
  spectrum, plus a letter shimmer that can be switched on over any of them
- **Animations**: twelve bundled 12x11 animations, one per hour of the dial, and
  you can drop in your own. One plays at the top of every hour, then the time
  comes back. Choose them per hour and preview them without waiting
- **Correct daylight saving time**: pick a time zone from the dropdown or let it
  detect your device's, and DST is applied from the tz database

### ESP32

Docs for ESP32 installation can be found [here](docs/installation_esp32.md)

## Development

The `sync.sh` script is included to help synchronize files between a source directory and a target directory in real-time. This ensures that any changes made in the source directory are reflected in the target directory.

### How to Use Sync Script

1. **Run the Sync Script**
   To synchronize the files, execute the following command in the terminal:
   ```bash
   chmod +x sync.sh
   ./sync.sh /path/to/source /path/to/target
   ```
   Replace `/path/to/source` and `/path/to/target` with the actual paths you want to synchronize.

2. **Automatic Sync**
   You can run this script in the background or set it up as a service to keep your directories synchronized without needing to run the script manually each time.

## Development Guidelines

- **Code Structure**: Follow the existing file organization within the `src/wordclock` directory. This helps maintain clarity in functionality.

- **Comments**: Keep comments to the most important parts of the code, as specified in your development preferences.

- **Contributing**: For any contributions or issues, please raise a pull request or create an issue in the GitHub repository.

## Notes

- Ensure that your Raspberry Pi has a stable internet connection for the initial setup and for the synchronization process.
- For the ESP32, make sure you have the correct board selected in PlatformIO.

Legal:
The provided project, including all instructions and materials, is shared for informational purposes only and is offered without any express or implied warranties. I disclaim all liability for any damages, losses, or injuries that may occur as a result of using, modifying, or following the instructions in this project. The project is shared 'as is,' and I make no guarantees regarding its functionality or suitability for any particular purpose. Use this project at your own risk, and be aware that results may vary based on individual implementation.
