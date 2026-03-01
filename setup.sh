#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "🚀 Starting Playwright Environment Fix..."

# 1. Update keys (using || true here because we expect the initial update to have GPG issues)
echo "🔑 Refreshing GPG keys..."
sudo apt-get update || true
sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 871920D1991BC93C

# 2. Update and Install System Dependencies
echo "🛠️ Installing System Dependencies..."
sudo apt-get update
sudo apt-get install -y libgbm1 libnss3 libasound2

# 3. Install Playwright Python Library
echo "📦 Installing Playwright Python package..."
pip install playwright

# 4. Install Playwright Browsers & their specific dependencies
echo "🌐 Installing Chromium and final driver dependencies..."
playwright install-deps chromium
playwright install chromium

echo "--------------------------------------"
echo "✅ SETUP SUCCESSFUL!"
echo "--------------------------------------"
