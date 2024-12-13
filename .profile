#!/bin/bash

# Download and install Google Chrome for Heroku
CHROME_BINARY_PATH="$HOME/.apt/usr/bin/google-chrome"

# Create the .apt directory if it doesn't exist
mkdir -p "$HOME/.apt/usr/bin"

# Download the latest Chrome package
wget -q -O /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb

# Extract Chrome from the package
dpkg -x /tmp/chrome.deb /tmp/chrome

# Move the Chrome binary to the .apt directory
mv /tmp/chrome/usr/bin/google-chrome-stable "$CHROME_BINARY_PATH"

# Make Chrome executable
chmod +x "$CHROME_BINARY_PATH"

# Clean up temporary files
rm -rf /tmp/chrome.deb /tmp/chrome

# Create symbolic link
ln -s "$CHROME_BINARY_PATH" "$HOME/.apt/usr/bin/google-chrome"

# Export Chrome binary path
export GOOGLE_CHROME_BIN="$CHROME_BINARY_PATH"
export GOOGLE_CHROME_SHIM="$CHROME_BINARY_PATH"

