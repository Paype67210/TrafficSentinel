#!/bin/bash

# Liste blanche
AUTHORIZED_MACS=("AA:BB:CC:DD:EE:FF" "11:22:33:44:55:66")

# Scan du réseau
DETECTED_MACS=$(arp-scan --interface=eth0 --localnet | grep -Eo "([[:xdigit:]]{1,2}:){5}[[:xdigit:]]{1,2}")

for mac in $DETECTED_MACS; do
    if [[ ! " ${AUTHORIZED_MACS[@]} " =~ " ${mac} " ]]; then
        echo "MAC non autorisée détectée : $mac"
        # Blocage via ebtables
        ebtables -A INPUT -s $mac -j DROP
    fi
done
