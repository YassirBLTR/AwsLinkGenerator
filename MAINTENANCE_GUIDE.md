# 🔧 Maintenance Mode Implementation Guide

## 📋 Overview

Your AWS Link Generator now has a comprehensive maintenance mode system that allows you to:
- Put the application into maintenance mode with custom messages
- Control maintenance mode via web interface or command line
- Allow admin access during maintenance
- Set estimated completion times
- Quick maintenance presets (5, 15, 30 minutes)

## 🚀 Quick Start

### **Method 1: Web Interface (Recommended)**
1. **Login as admin** to your application
2. **Go to Admin → Maintenance Mode** (new menu item)
3. **Click "Enable Maintenance Mode"**
4. **Enter custom message and ETA**
5. **Click "Disable Maintenance Mode"** when done

### **Method 2: Command Line**
```bash
# Enable maintenance mode
python maintenance_cli.py enable "Upgrading performance optimizations" "30 minutes"

# Check status
python maintenance_cli.py status

# Disable maintenance mode
python maintenance_cli.py disable
```

### **Method 3: Quick SSH Commands**
```bash
# Quick 15-minute maintenance
cd /path/to/your/app
python maintenance_cli.py enable "Quick performance update" "15 minutes"

# When done
python maintenance_cli.py disable
```

## 📁 Files Added

### **New Files Created:**
- `templates/maintenance.html` - Beautiful maintenance page users see
- `templates/admin_maintenance.html` - Admin control panel
- `maintenance.py` - Maintenance mode logic and middleware
- `maintenance_cli.py` - Command-line control tool
- `maintenance_config.json` - Configuration file (auto-created)

### **Modified Files:**
- `main.py` - Added middleware and admin routes
- `templates/base.html` - Added maintenance menu item

## 🎨 Maintenance Page Features

### **User Experience:**
- 🎨 **Beautiful Design** - Professional maintenance page
- ⏰ **Auto-refresh** - Page refreshes every 30 seconds
- 📱 **Responsive** - Works on mobile and desktop
- 🔄 **Progress Animation** - Visual progress indicators
- 📧 **Contact Info** - Support links and information

### **Admin Features:**
- 🎛️ **Full Control** - Enable/disable from web interface
- ⚡ **Quick Presets** - 5, 15, 30-minute maintenance buttons
- 📝 **Custom Messages** - Set personalized maintenance messages
- ⏱️ **ETA Display** - Show estimated completion time
- 🔍 **Status Monitoring** - Real-time status display

## 🛠 Implementation Steps

### **Step 1: Deploy Files**
Upload all the new files to your Rocky Linux server:
```bash
# Upload files to your app directory
scp templates/maintenance.html user@server:/path/to/app/templates/
scp templates/admin_maintenance.html user@server:/path/to/app/templates/
scp maintenance.py user@server:/path/to/app/
scp maintenance_cli.py user@server:/path/to/app/
```

### **Step 2: Restart Application**
```bash
# Stop your current application
sudo systemctl stop your-app-service

# Or if running manually:
pkill -f "python.*main.py"

# Start the application
python main.py
# Or restart your service:
sudo systemctl start your-app-service
```

### **Step 3: Test Maintenance Mode**
1. **Access admin panel**: `http://your-server/admin/maintenance`
2. **Enable maintenance mode** with a test message
3. **Open new browser/incognito** and visit your site
4. **Verify maintenance page shows**
5. **Disable maintenance mode**

## 🔒 Security Features

### **Admin Bypass:**
- ✅ **Admins always have access** during maintenance
- ✅ **Health checks work** (`/health`, `/status`)
- ✅ **Bypass header support** for emergency access

### **Emergency Access:**
```bash
# If you get locked out, use CLI:
python maintenance_cli.py disable

# Or add bypass header in curl:
curl -H "X-Maintenance-Bypass: admin123" http://your-server/admin/login
```

## 📊 Monitoring

### **Health Checks:**
- `GET /health` - Returns `{"status": "healthy"}`
- `GET /status` - Returns maintenance status and timestamp

### **Status Monitoring:**
```bash
# Check if maintenance is active
curl http://your-server/status

# Response:
{
  "status": "running",
  "maintenance_mode": true,
  "timestamp": "2024-01-15T14:30:22"
}
```

## 🎯 Use Cases

### **Planned Maintenance:**
```bash
# Before deploying updates
python maintenance_cli.py enable "Deploying performance improvements" "20 minutes"

# Deploy your changes
git pull
pip install -r requirements.txt
# ... other deployment steps

# Re-enable application
python maintenance_cli.py disable
```

### **Emergency Maintenance:**
```bash
# Quick emergency maintenance
python maintenance_cli.py enable "Investigating performance issue" "ASAP"

# Fix the issue
# ...

# Back online
python maintenance_cli.py disable
```

### **Scheduled Maintenance:**
```bash
# For scheduled downtime
python maintenance_cli.py enable "Scheduled maintenance - upgrading servers" "2 hours"
```

## 🔧 Configuration

### **Maintenance Config File:**
The system creates `maintenance_config.json`:
```json
{
  "enabled": false,
  "message": "We're currently performing scheduled maintenance.",
  "estimated_completion": null,
  "allowed_ips": [],
  "bypass_paths": ["/health", "/status"]
}
```

### **Customization Options:**
- **Custom messages** for different maintenance types
- **Allowed IPs** for specific users to bypass
- **Additional bypass paths** for monitoring tools
- **Estimated completion times** for user communication

## 🚨 Troubleshooting

### **Common Issues:**

**1. Maintenance page not showing:**
- Check if middleware is properly added to `main.py`
- Verify `maintenance.py` is in the correct directory
- Restart the application

**2. Can't disable maintenance:**
- Use CLI: `python maintenance_cli.py disable`
- Check file permissions on `maintenance_config.json`
- Verify admin login is working

**3. Admin locked out:**
- Use bypass header: `X-Maintenance-Bypass: admin123`
- Access via CLI: `python maintenance_cli.py disable`
- Check `/health` endpoint is accessible

### **Logs and Debugging:**
```bash
# Check application logs
tail -f /var/log/your-app.log

# Check maintenance status
python maintenance_cli.py status

# Test health endpoint
curl http://your-server/health
```

## 📱 Mobile and API Support

### **API Responses:**
During maintenance, API endpoints return:
```json
HTTP 503 Service Unavailable
{
  "detail": "Service temporarily unavailable",
  "maintenance": true,
  "message": "We're currently performing scheduled maintenance.",
  "estimated_completion": "30 minutes"
}
```

### **Mobile App Handling:**
Mobile apps can check the `/status` endpoint to detect maintenance mode and show appropriate UI.

## 🎉 Benefits

### **For Administrators:**
- ✅ **Professional appearance** during downtime
- ✅ **Easy control** via web interface or CLI
- ✅ **No user confusion** with clear messaging
- ✅ **Flexible timing** with ETA display
- ✅ **Emergency access** options

### **For Users:**
- ✅ **Clear communication** about maintenance
- ✅ **Professional experience** instead of errors
- ✅ **Automatic refresh** to check when back online
- ✅ **Mobile-friendly** maintenance page
- ✅ **Contact information** for urgent needs

## 🚀 Next Steps

1. **Deploy the maintenance system** to your server
2. **Test all functionality** in a safe environment
3. **Train your team** on using the web interface
4. **Set up monitoring** for the health endpoints
5. **Plan your next maintenance window** with the new system!

Your application now has enterprise-grade maintenance mode capabilities! 🎉
