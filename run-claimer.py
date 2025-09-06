#!/bin/bash
cd /opt/octopus-coffee
source .env
export OCTOPUS_EMAIL OCTOPUS_PASSWORD OCTOPUS_ACCOUNT_ID
/usr/bin/python3 octopus-coffee-claimer.py
