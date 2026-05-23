# Network Security Runbook

## Overview
This runbook details how Foxhole assists with monitoring local network security, Pi-hole DNS metrics, and discovering rogue devices.

## What Foxhole Checks (Read-Only)
1. **Pi-hole / Unbound Health:** Queries the Pi-hole API to ensure it is actively blocking domains and checks Unbound latency/status.
2. **Rogue MAC Discovery:** Executes a limited `nmap` ping sweep (ICMP and ARP) across explicitly configured RFC1918 subnets. Compares found MAC addresses against a known allowlist.
3. **Open Ports (Basic):** Optionally runs a fast top-100 port scan against discovered IP addresses to identify exposed management interfaces (e.g., Port 22, 8006).

## Manual Actions Required
Foxhole will alert you to new devices or exposed ports, but you must manually configure your firewall (e.g., pfSense/OPNsense), update Pi-hole blocklists, or isolate rogue devices at the switch level.

## Example Prompts
- *"Are there any unknown devices on the IoT VLAN (192.168.20.0/24)?"*
- *"Is Pi-hole currently blocking ads?"*
- *"Scan the network for exposed Proxmox management ports."*
