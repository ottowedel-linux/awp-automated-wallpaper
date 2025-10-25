#!/bin/sh
# awp_start.sh - Startup script for AWP Daemon
# Customize this script to add your own startup commands (Conky, etc.)

CONFIG_FILE="$HOME/awp/awp_config.ini"

# Kill any previous instances
pkill -f "$HOME/awp/awp_daemon.py" 2>/dev/null
sleep 1

# Start the AWP daemon
python3 "$HOME/awp/awp_daemon.py" &

# =============================================================================
# CUSTOM INTEGRATIONS - UNCOMMENT AND MODIFY AS NEEDED
# =============================================================================

# Example: Start Conky with your custom configuration
# sleep 1
# pkill -f conky
# sleep 1
# conky -c "$HOME/awp/conky/.conkyrc" &
