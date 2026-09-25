#!/bin/bash

# Startup script for LOTeka Analyzer Docker container
set -e

echo "🚀 Starting LOTeka Analyzer Docker Container..."
echo "=================================="

# Create assets directory if it doesn't exist
mkdir -p assets

# Check if loteka_numbers.json exists, if not create it with empty array
if [ ! -f "loteka_numbers.json" ]; then
    echo "📊 Creating initial loteka_numbers.json file..."
    echo "[]" > loteka_numbers.json
    echo "✅ loteka_numbers.json created"
fi

# Check if .env exists, if not create it with default values
if [ ! -f ".env" ]; then
    echo "⚙️  Creating initial .env file..."
    echo "LAST_PROCESSED_DATE=15/10/2019" > .env
    echo "✅ .env file created"
fi

# Verify Python installation
echo "🔍 Checking Python installation..."
python --version || { echo "❌ Python not found"; exit 1; }

# Verify required files exist
echo "🔍 Verifying application files..."
for file in flet_app.py scrapy.py MarkovPY.py main_runner.py; do
    if [ ! -f "$file" ]; then
        echo "❌ Missing file: $file"
        exit 1
    fi
    echo "✅ Found: $file"
done

echo ""
echo "🌐 Starting Flet web server..."
echo "📱 Server Configuration:"
echo "   Port: ${FLET_SERVER_PORT:-8550}"
echo "   Host: ${FLET_SERVER_HOST:-0.0.0.0}"
echo ""
echo "🌟 Access the application at:"
echo "   Local: http://localhost:${FLET_SERVER_PORT:-8550}"
echo "   Network: http://$(hostname -I | awk '{print $1}'):${FLET_SERVER_PORT:-8550}"
echo ""
echo "=================================="

# Start the Flet application
exec python flet_app.py