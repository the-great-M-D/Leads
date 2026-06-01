#!/usr/bin/env bash
set -e

echo "📥 Installing Python dependencies..."
pip install -r requirements.txt

echo "🌐 Installing Playwright browsers and system deps..."
playwright install-deps chromium
playwright install chromium

echo "✅ Build complete."
