#!/usr/bin/env python3
"""
Command-line tool to control maintenance mode
Usage:
    python maintenance_cli.py enable "Custom message" "30 minutes"
    python maintenance_cli.py disable
    python maintenance_cli.py status
"""

import sys
import json
import os
from datetime import datetime

def load_config():
    """Load maintenance configuration"""
    config_file = "maintenance_config.json"
    default_config = {
        "enabled": False,
        "message": "We're currently performing scheduled maintenance.",
        "estimated_completion": None,
        "allowed_ips": [],
        "bypass_paths": ["/health", "/status"]
    }
    
    try:
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                config = json.load(f)
                default_config.update(config)
        return default_config, config_file
    except Exception as e:
        print(f"Error loading config: {e}")
        return default_config, config_file

def save_config(config, config_file):
    """Save maintenance configuration"""
    try:
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False

def enable_maintenance(message=None, estimated_completion=None):
    """Enable maintenance mode"""
    config, config_file = load_config()
    config["enabled"] = True
    
    if message:
        config["message"] = message
    if estimated_completion:
        config["estimated_completion"] = estimated_completion
    
    if save_config(config, config_file):
        print("🔧 Maintenance mode ENABLED")
        print(f"Message: {config['message']}")
        if config.get('estimated_completion'):
            print(f"ETA: {config['estimated_completion']}")
        return True
    else:
        print("❌ Failed to enable maintenance mode")
        return False

def disable_maintenance():
    """Disable maintenance mode"""
    config, config_file = load_config()
    config["enabled"] = False
    
    if save_config(config, config_file):
        print("✅ Maintenance mode DISABLED")
        print("Application is now accessible to all users")
        return True
    else:
        print("❌ Failed to disable maintenance mode")
        return False

def show_status():
    """Show current maintenance status"""
    config, _ = load_config()
    
    print("🔍 Maintenance Mode Status")
    print("=" * 30)
    
    if config["enabled"]:
        print("Status: 🔧 ENABLED")
        print(f"Message: {config['message']}")
        if config.get('estimated_completion'):
            print(f"ETA: {config['estimated_completion']}")
    else:
        print("Status: ✅ DISABLED")
        print("Application is accessible to all users")
    
    print(f"\nBypass paths: {', '.join(config.get('bypass_paths', []))}")
    if config.get('allowed_ips'):
        print(f"Allowed IPs: {', '.join(config['allowed_ips'])}")
    
    return config["enabled"]

def main():
    """Main CLI function"""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python maintenance_cli.py enable [message] [eta]")
        print("  python maintenance_cli.py disable")
        print("  python maintenance_cli.py status")
        print("\nExamples:")
        print('  python maintenance_cli.py enable "Upgrading database" "30 minutes"')
        print('  python maintenance_cli.py enable "Server maintenance"')
        print('  python maintenance_cli.py disable')
        print('  python maintenance_cli.py status')
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "enable":
        message = sys.argv[2] if len(sys.argv) > 2 else None
        eta = sys.argv[3] if len(sys.argv) > 3 else None
        enable_maintenance(message, eta)
    
    elif command == "disable":
        disable_maintenance()
    
    elif command == "status":
        show_status()
    
    else:
        print(f"Unknown command: {command}")
        print("Available commands: enable, disable, status")
        sys.exit(1)

if __name__ == "__main__":
    main()
