#!/bin/bash

# Start Tor in background
echo "Starting Tor..."
tor --runasdaemon 1

# Wait for Tor to bootstrap
echo "Waiting for Tor to be ready..."
sleep 10

# Check if Tor is listening
if nc -z 127.0.0.1 9050; then
    echo "Tor is up and running!"
else
    echo "WARNING: Tor failed to start or is not listening on 9050."
fi

# Run the command
exec "$@"
