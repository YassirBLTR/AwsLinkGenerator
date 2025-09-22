import os
import json
from datetime import datetime
from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")

class MaintenanceMode:
    def __init__(self, config_file="maintenance_config.json"):
        self.config_file = config_file
        self.config = self.load_config()
    
    def load_config(self):
        """Load maintenance configuration from file"""
        default_config = {
            "enabled": False,
            "message": "We're currently performing scheduled maintenance.",
            "estimated_completion": None,
            "allowed_ips": [],  # IPs that can bypass maintenance mode
            "bypass_paths": ["/health", "/status"]  # Paths that bypass maintenance
        }
        
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    # Merge with defaults
                    default_config.update(config)
            return default_config
        except Exception as e:
            print(f"Error loading maintenance config: {e}")
            return default_config
    
    def save_config(self):
        """Save maintenance configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving maintenance config: {e}")
            return False
    
    def enable(self, message=None, estimated_completion=None):
        """Enable maintenance mode"""
        self.config["enabled"] = True
        if message:
            self.config["message"] = message
        if estimated_completion:
            self.config["estimated_completion"] = estimated_completion
        self.save_config()
        print("🔧 Maintenance mode ENABLED")
    
    def disable(self):
        """Disable maintenance mode"""
        self.config["enabled"] = False
        self.save_config()
        print("✅ Maintenance mode DISABLED")
    
    def is_enabled(self):
        """Check if maintenance mode is enabled"""
        return self.config.get("enabled", False)
    
    def should_bypass(self, request: Request):
        """Check if request should bypass maintenance mode"""
        # Check if path is in bypass list
        path = request.url.path
        if path in self.config.get("bypass_paths", []):
            return True
        
        # Check if IP is in allowed list
        client_ip = request.client.host
        if client_ip in self.config.get("allowed_ips", []):
            return True
        
        # Check for admin bypass token in headers
        bypass_token = request.headers.get("X-Maintenance-Bypass")
        if bypass_token == os.getenv("MAINTENANCE_BYPASS_TOKEN", "admin123"):
            return True
        
        return False
    
    def get_maintenance_response(self, request: Request):
        """Get maintenance mode response"""
        return templates.TemplateResponse("maintenance.html", {
            "request": request,
            "message": self.config.get("message", "Under maintenance"),
            "estimated_completion": self.config.get("estimated_completion")
        })

# Global maintenance mode instance
maintenance = MaintenanceMode()

# Middleware function
async def maintenance_middleware(request: Request, call_next):
    """Middleware to check maintenance mode"""
    if maintenance.is_enabled() and not maintenance.should_bypass(request):
        return maintenance.get_maintenance_response(request)
    
    response = await call_next(request)
    return response
