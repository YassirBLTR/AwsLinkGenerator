# AWS S3 Bucket Manager

A FastAPI web application that provides a user-friendly interface for managing AWS S3 bucket creation across multiple AWS accounts. Built with modern web technologies and a clean, responsive UI.

## 🚀 Features

### Admin Features
- **User Management**: Create, view, and delete users
- **AWS Key Management**: Add, assign, and manage AWS credentials
- **Dashboard**: Overview of system statistics and recent activity
- **Role-based Access**: Admin and regular user roles

### User Features
- **Region Selection**: Choose from 47 AWS regions worldwide
- **Bucket Creation**: Create multiple S3 buckets across assigned AWS accounts
- **File Upload**: Automatically upload HTML and image files to buckets
- **URL Generation**: Get public URLs for all uploaded content
- **Results Tracking**: View detailed creation results and download reports

## 🛠️ Technology Stack

- **Backend**: FastAPI (Python)
- **Database**: SQLite with SQLAlchemy ORM
- **Authentication**: JWT tokens with bcrypt password hashing
- **Frontend**: Bootstrap 5, Jinja2 templates
- **AWS Integration**: boto3 SDK
- **UI**: Modern responsive design with Font Awesome icons

## 📋 Prerequisites

- Python 3.8+
- AWS credentials (Access Key ID and Secret Access Key)
- HTML and image files for upload (optional)

## 🔧 Installation & Setup

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Initialize Database**
   ```bash
   python init_db.py
   ```
   This creates the database and default admin user:
   - Username: `admin`
   - Password: `admin123`

3. **Start the Application**
   ```bash
   python main.py
   ```

4. **Access the Application**
   Open your browser and go to: `http://localhost:8000`

## 👥 User Roles

### Admin Users
- Full system access
- Can create and manage users
- Can add and assign AWS keys
- View system statistics

### Regular Users
- Can view assigned AWS keys
- Can create S3 buckets in selected regions
- Can download creation results

## 🔐 Security Features

- JWT-based authentication
- Bcrypt password hashing
- Role-based access control
- Secure cookie handling
- Input validation and sanitization

## 📊 AWS Integration

The application integrates with your existing AWS S3 automation script:
- Supports multiple AWS accounts
- Creates buckets with random names
- Configures public access settings
- Uploads files with public-read permissions
- Generates direct access URLs

## 🌍 Supported AWS Regions

All 47 AWS regions are supported, including:
- US regions (us-east-1, us-west-2, etc.)
- Europe (eu-west-1, eu-central-1, etc.)
- Asia Pacific (ap-southeast-1, ap-northeast-1, etc.)
- And many more...

## 📁 Project Structure

```
├── main.py              # FastAPI application
├── database.py          # Database configuration
├── models.py            # SQLAlchemy models
├── schemas.py           # Pydantic schemas
├── aws_service.py       # AWS S3 integration
├── init_db.py           # Database initialization
├── requirements.txt     # Python dependencies
├── templates/           # HTML templates
│   ├── base.html
│   ├── login.html
│   ├── admin_dashboard.html
│   ├── admin_users.html
│   ├── admin_keys.html
│   ├── user_dashboard.html
│   ├── create_buckets.html
│   └── bucket_results.html
└── static/             # Static files (CSS, JS, images)
```

## 🔄 Workflow

1. **Admin Setup**
   - Login as admin
   - Add AWS credentials
   - Create user accounts
   - Assign AWS keys to users

2. **User Operations**
   - Login with user credentials
   - Select AWS region
   - Specify number of buckets per key
   - Create buckets and view results

3. **Results**
   - View generated URLs
   - Copy URLs to clipboard
   - Download detailed results file

## ⚠️ Important Notes

- Change the default admin password after first login
- Keep AWS credentials secure and rotate regularly
- Monitor AWS costs when creating multiple buckets
- Ensure proper IAM permissions for S3 operations

## 🐛 Troubleshooting

### Common Issues

1. **Database not found**: Run `python init_db.py` first
2. **AWS credentials error**: Verify access keys and permissions
3. **Port already in use**: Change port in `main.py` or stop conflicting services
4. **Template not found**: Ensure `templates/` directory exists

### Error Messages

- **"No AWS keys assigned"**: Contact admin to assign credentials
- **"Cannot create buckets"**: Check AWS account limits
- **"Authentication failed"**: Verify username and password

## 📞 Support

For issues or questions:
1. Check the troubleshooting section
2. Verify AWS credentials and permissions
3. Review application logs for detailed error messages

## 🔒 Security Considerations

- Use strong passwords for all accounts
- Regularly rotate AWS credentials
- Monitor AWS CloudTrail for API activity
- Keep the application updated
- Use HTTPS in production environments

---

**Built with ❤️ using FastAPI and modern web technologies**
