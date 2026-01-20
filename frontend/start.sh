#!/bin/bash

# Frontend Startup Script for AI Video Quiz Generator
# This script starts the development server with proper error handling

set -e

echo "🚀 Starting AI Video Quiz Generator Frontend..."
echo ""

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Error: Node.js is not installed"
    echo "Please install Node.js 18+ from https://nodejs.org/"
    exit 1
fi

# Check Node.js version
NODE_VERSION=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 18 ]; then
    echo "⚠️  Warning: Node.js version 18+ is recommended (current: $(node -v))"
fi

# Check if we're in the frontend directory
if [ ! -f "package.json" ]; then
    echo "❌ Error: package.json not found"
    echo "Please run this script from the frontend directory"
    exit 1
fi

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
    echo "✅ Dependencies installed"
    echo ""
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚙️  Creating .env file from template..."
    cp .env.example .env
    echo "✅ .env file created"
    echo ""
fi

# Display configuration
echo "📋 Configuration:"
echo "   API URL: ${VITE_API_URL:-http://localhost:8000}"
echo "   Port: 5173 (default)"
echo ""

# Check if backend is running
echo "🔍 Checking backend connection..."
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Backend is running"
else
    echo "⚠️  Warning: Backend doesn't appear to be running on http://localhost:8000"
    echo "   The frontend will start, but you'll need to start the backend to use the app"
    echo "   Run: cd ../app && python run.py"
fi

echo ""
echo "🎨 Starting development server..."
echo "   Local: http://localhost:5173"
echo "   Network: http://$(hostname -I | awk '{print $1}'):5173"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Start the development server
npm run dev
