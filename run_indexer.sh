#!/bin/bash

# Define the name of the virtual environment directory
VENV_DIR="venv"

# Check if the virtual environment directory exists
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment at $VENV_DIR..."
    python3 -m venv $VENV_DIR
    if [ $? -ne 0 ]; then
        echo "Failed to create virtual environment. Please ensure python3-venv is installed."
        exit 1
    fi
fi

# Activate the virtual environment
echo "Activating virtual environment..."
source $VENV_DIR/bin/activate

# Install the required packages
echo "Installing dependencies from requirements.txt..."
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "Failed to install dependencies."
    exit 1
fi

# Run the indexer script
echo "Running the database indexer..."
python indexer.py

echo "Indexer run complete."
