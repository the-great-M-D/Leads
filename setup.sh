#!/bin/bash

# Exit on any error
set -e

echo "🛠️ Step 1: Fixing GPG Keys and Package Lists..."
# We use '|| true' because the first update almost always fails on keys in this repo
sudo apt-get update || true
sudo apt-get install -y gnupg2
sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 871920D1991BC93C

echo "📥 Step 2: Updating System..."
sudo apt-get update
sudo apt-get install -y libgbm1 libnss3 libasound2 libxshmfence1 libglu1

echo "🐍 Step 3: Installing Playwright Python Package..."
# Using 'python3 -m pip' ensures we hit the right environment in this template
python3 -m pip install --upgrade pip
python3 -m pip install playwright

echo "🌐 Step 4: Installing Browser and System Dependencies..."
# This is the 'magic' command that fixes the Error 100 once and for all
python3 -m playwright install-deps chromium
python3 -m playwright install chromium

echo ""
echo "✅ SUCCESS: Playwright is ready to go!"
