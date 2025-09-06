#!/bin/bash
# Get the directory where the script is located
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Change to that directory
cd "$DIR"

# Source the environment file and run the Python script
source .env
export OCTOPUS_EMAIL OCTOPUS_PASSWORD OCTOPUS_ACCOUNT_ID
/usr/bin/python3 "$DIR/claimer.py"
