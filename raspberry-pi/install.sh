#!/bin/bash

# Get the directory of the currently executing script
BASE_PATH="$(dirname "$(realpath "$0")")"

# Variables
SERVICE_NAME="word_clock.service"
SERVICE_PATH="/etc/systemd/system/$SERVICE_NAME"
SCRIPT_PATH="$BASE_PATH/src/wordclock/main.py"
GIF_DIRECTORY="$BASE_PATH/gifs"
BACKGROUND_DIRECTORY="$BASE_PATH/backgrounds"
CONFIG_PATH="$BASE_PATH/wordclock.json"
WORKING_DIRECTORY="$BASE_PATH/src/wordclock"
PYTHON_PATH="/usr/bin/python3"
LED_PIN="${LED_PIN:-D12}"
WEB_PORT="${WEB_PORT:-8080}"

# Check if the service already exists
if [ -f "$SERVICE_PATH" ]; then
    echo "Service $SERVICE_NAME already exists. Removing the old service."
    sudo systemctl stop $SERVICE_NAME
    sudo systemctl disable $SERVICE_NAME
    sudo rm "$SERVICE_PATH"
fi

# Create the service file
echo "Creating systemd service file at $SERVICE_PATH"
sudo bash -c "cat > $SERVICE_PATH" <<EOF
[Unit]
Description=Word Clock Service
After=multi-user.target network.target

[Service]
ExecStart=$PYTHON_PATH $SCRIPT_PATH --pin $LED_PIN --gif-dir $GIF_DIRECTORY --background-dir $BACKGROUND_DIRECTORY --config $CONFIG_PATH --web-port $WEB_PORT
WorkingDirectory=$WORKING_DIRECTORY
StandardOutput=inherit
StandardError=inherit
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Settings changed from the web interface are stored here. Existing settings are
# left alone when reinstalling.
if [ ! -f "$CONFIG_PATH" ]; then
    echo '{}' | sudo tee "$CONFIG_PATH" > /dev/null
fi
sudo chmod 664 "$CONFIG_PATH"

# Enable the service
echo "Enabling the $SERVICE_NAME to start on boot"
sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME

# Start the service
echo "Starting the $SERVICE_NAME service"
sudo systemctl start $SERVICE_NAME

# Check the status
echo "Checking the status of the $SERVICE_NAME service"
sudo systemctl status $SERVICE_NAME --no-pager

echo
echo "Installation complete!"
echo "Web interface: http://$(hostname -I 2>/dev/null | awk '{print $1}'):$WEB_PORT (also http://$(hostname).local:$WEB_PORT)"
echo "Animations:    put .gif files in $GIF_DIRECTORY"
echo "Backgrounds:   $BACKGROUND_DIRECTORY"
echo "Settings:      $CONFIG_PATH"
