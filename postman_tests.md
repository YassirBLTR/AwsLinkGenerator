# Postman API Tests for AWS S3 Manager

This document provides comprehensive Postman test cases for all endpoints in the FastAPI AWS S3 Manager application.

## 🔧 Setup Instructions

1. **Start the application**: `python main.py`
2. **Initialize database**: `python init_db.py` (if not done already)
3. **Base URL**: `http://localhost:8000`
4. **Default Admin**: username: `admin`, password: `admin123`

## 📋 Test Collection Structure

### Environment Variables (Create in Postman)
```json
{
  "base_url": "http://localhost:8000",
  "access_token": "",
  "user_id": "",
  "key_id": ""
}
```

---

## 🔐 Authentication Tests

### 1. GET Login Page
```
Method: GET
URL: {{base_url}}/login
Headers: None
Body: None

Expected Response: 200 OK
Content-Type: text/html
```

### 2. POST Login (Admin)
```
Method: POST
URL: {{base_url}}/login
Headers: 
  Content-Type: application/x-www-form-urlencoded
Body (form-data):
  username: admin
  password: admin123

Expected Response: 302 Redirect
Location: /admin/dashboard
Set-Cookie: access_token=Bearer ...

Test Script:
pm.test("Login successful", function () {
    pm.expect(pm.response.code).to.be.oneOf([302, 200]);
});

pm.test("Cookie set", function () {
    pm.expect(pm.response.headers.get("Set-Cookie")).to.include("access_token");
});
```

### 3. POST Login (Invalid Credentials)
```
Method: POST
URL: {{base_url}}/login
Headers: 
  Content-Type: application/x-www-form-urlencoded
Body (form-data):
  username: invalid
  password: wrong

Expected Response: 200 OK
Content should include error message
```

### 4. GET Logout
```
Method: GET
URL: {{base_url}}/logout
Headers: None

Expected Response: 302 Redirect
Location: /login
Set-Cookie: access_token=; (cookie cleared)
```

---

## 👨‍💼 Admin Dashboard Tests

### 5. GET Admin Dashboard
```
Method: GET
URL: {{base_url}}/admin/dashboard
Headers: 
  Cookie: access_token=Bearer {{access_token}}

Expected Response: 200 OK
Content-Type: text/html

Test Script:
pm.test("Dashboard loads", function () {
    pm.expect(pm.response.code).to.eql(200);
    pm.expect(pm.response.text()).to.include("Admin Dashboard");
});
```

### 6. GET Admin Dashboard (Unauthorized)
```
Method: GET
URL: {{base_url}}/admin/dashboard
Headers: None

Expected Response: 401 Unauthorized
```

---

## 👥 User Management Tests

### 7. GET Admin Users Page
```
Method: GET
URL: {{base_url}}/admin/users
Headers: 
  Cookie: access_token=Bearer {{access_token}}

Expected Response: 200 OK
Content-Type: text/html
```

### 8. POST Create User
```
Method: POST
URL: {{base_url}}/admin/users/create
Headers: 
  Content-Type: application/x-www-form-urlencoded
  Cookie: access_token=Bearer {{access_token}}
Body (form-data):
  username: testuser
  password: testpass123
  is_admin: false

Expected Response: 302 Redirect
Location: /admin/users

Test Script:
pm.test("User created successfully", function () {
    pm.expect(pm.response.code).to.eql(302);
});
```

### 9. POST Create User (Duplicate Username)
```
Method: POST
URL: {{base_url}}/admin/users/create
Headers: 
  Content-Type: application/x-www-form-urlencoded
  Cookie: access_token=Bearer {{access_token}}
Body (form-data):
  username: admin
  password: testpass123
  is_admin: false

Expected Response: 200 OK
Content should include error about existing username
```

### 10. POST Create Admin User
```
Method: POST
URL: {{base_url}}/admin/users/create
Headers: 
  Content-Type: application/x-www-form-urlencoded
  Cookie: access_token=Bearer {{access_token}}
Body (form-data):
  username: admin2
  password: admin456
  is_admin: true

Expected Response: 302 Redirect
Location: /admin/users
```

### 11. POST Delete User
```
Method: POST
URL: {{base_url}}/admin/users/2/delete
Headers: 
  Content-Type: application/x-www-form-urlencoded
  Cookie: access_token=Bearer {{access_token}}

Expected Response: 302 Redirect
Location: /admin/users

Note: Replace '2' with actual user ID
```

---

## 🔑 AWS Key Management Tests

### 12. GET Admin Keys Page
```
Method: GET
URL: {{base_url}}/admin/keys
Headers: 
  Cookie: access_token=Bearer {{access_token}}

Expected Response: 200 OK
Content-Type: text/html
```

### 13. POST Create AWS Key (Unassigned)
```
Method: POST
URL: {{base_url}}/admin/keys/create
Headers: 
  Content-Type: application/x-www-form-urlencoded
  Cookie: access_token=Bearer {{access_token}}
Body (form-data):
  name: test-aws-key
  access_key: AKIATEST123456789
  secret_key: testSecretKey123456789abcdef
  user_id: (leave empty)

Expected Response: 302 Redirect
Location: /admin/keys

Test Script:
pm.test("AWS key created", function () {
    pm.expect(pm.response.code).to.eql(302);
});
```

### 14. POST Create AWS Key (Assigned to User)
```
Method: POST
URL: {{base_url}}/admin/keys/create
Headers: 
  Content-Type: application/x-www-form-urlencoded
  Cookie: access_token=Bearer {{access_token}}
Body (form-data):
  name: assigned-aws-key
  access_key: AKIAASSIGNED123456
  secret_key: assignedSecretKey123456789abcdef
  user_id: 2

Expected Response: 302 Redirect
Location: /admin/keys

Note: Replace '2' with actual user ID
```

### 15. POST Assign Key to User
```
Method: POST
URL: {{base_url}}/admin/keys/1/assign
Headers: 
  Content-Type: application/x-www-form-urlencoded
  Cookie: access_token=Bearer {{access_token}}
Body (form-data):
  user_id: 2

Expected Response: 302 Redirect
Location: /admin/keys

Note: Replace '1' with actual key ID and '2' with user ID
```

### 16. POST Unassign Key
```
Method: POST
URL: {{base_url}}/admin/keys/1/unassign
Headers: 
  Content-Type: application/x-www-form-urlencoded
  Cookie: access_token=Bearer {{access_token}}

Expected Response: 302 Redirect
Location: /admin/keys

Note: Replace '1' with actual key ID
```

### 17. POST Delete AWS Key
```
Method: POST
URL: {{base_url}}/admin/keys/1/delete
Headers: 
  Content-Type: application/x-www-form-urlencoded
  Cookie: access_token=Bearer {{access_token}}

Expected Response: 302 Redirect
Location: /admin/keys

Note: Replace '1' with actual key ID
```

---

## 👤 User Dashboard Tests

### 18. POST Login as Regular User
```
Method: POST
URL: {{base_url}}/login
Headers: 
  Content-Type: application/x-www-form-urlencoded
Body (form-data):
  username: testuser
  password: testpass123

Expected Response: 302 Redirect
Location: /user/dashboard

Test Script:
pm.test("User login successful", function () {
    pm.expect(pm.response.code).to.be.oneOf([302, 200]);
});

// Extract cookie for subsequent requests
var cookies = pm.response.headers.get("Set-Cookie");
if (cookies) {
    var token = cookies.split("access_token=")[1].split(";")[0];
    pm.environment.set("user_access_token", token);
}
```

### 19. GET User Dashboard
```
Method: GET
URL: {{base_url}}/user/dashboard
Headers: 
  Cookie: access_token={{user_access_token}}

Expected Response: 200 OK
Content-Type: text/html

Test Script:
pm.test("User dashboard loads", function () {
    pm.expect(pm.response.code).to.eql(200);
    pm.expect(pm.response.text()).to.include("Dashboard");
});
```

### 20. GET User Dashboard (Admin Redirect)
```
Method: GET
URL: {{base_url}}/user/dashboard
Headers: 
  Cookie: access_token=Bearer {{access_token}}

Expected Response: 302 Redirect
Location: /admin/dashboard
(Admin users should be redirected to admin dashboard)
```

---

## 🪣 Bucket Creation Tests

### 21. GET Create Buckets Page
```
Method: GET
URL: {{base_url}}/user/create-buckets
Headers: 
  Cookie: access_token={{user_access_token}}

Expected Response: 200 OK
Content-Type: text/html
```

### 22. POST Create Buckets (Valid Request)
```
Method: POST
URL: {{base_url}}/user/create-buckets
Headers: 
  Content-Type: application/x-www-form-urlencoded
  Cookie: access_token={{user_access_token}}
Body (form-data):
  region: us-east-1
  num_buckets: 1

Expected Response: 200 OK
Content-Type: text/html
Should show bucket creation results

Test Script:
pm.test("Bucket creation initiated", function () {
    pm.expect(pm.response.code).to.eql(200);
    pm.expect(pm.response.text()).to.include("Bucket Creation Results");
});

Note: This will only work if the user has valid AWS keys assigned
```

### 23. POST Create Buckets (No AWS Keys)
```
Method: POST
URL: {{base_url}}/user/create-buckets
Headers: 
  Content-Type: application/x-www-form-urlencoded
  Cookie: access_token={{user_access_token}}
Body (form-data):
  region: us-east-1
  num_buckets: 1

Expected Response: 200 OK
Content should include error about no AWS keys assigned

Note: Test this with a user who has no AWS keys assigned
```

### 24. POST Create Buckets (Invalid Region)
```
Method: POST
URL: {{base_url}}/user/create-buckets
Headers: 
  Content-Type: application/x-www-form-urlencoded
  Cookie: access_token={{user_access_token}}
Body (form-data):
  region: invalid-region
  num_buckets: 1

Expected Response: 422 Unprocessable Entity or validation error
```

### 25. POST Create Buckets (Invalid Number)
```
Method: POST
URL: {{base_url}}/user/create-buckets
Headers: 
  Content-Type: application/x-www-form-urlencoded
  Cookie: access_token={{user_access_token}}
Body (form-data):
  region: us-east-1
  num_buckets: -1

Expected Response: 422 Unprocessable Entity or validation error
```

---

## 🔒 Authorization Tests

### 26. Access Admin Endpoint as Regular User
```
Method: GET
URL: {{base_url}}/admin/users
Headers: 
  Cookie: access_token={{user_access_token}}

Expected Response: 403 Forbidden
```

### 27. Access User Endpoint without Authentication
```
Method: GET
URL: {{base_url}}/user/dashboard
Headers: None

Expected Response: 401 Unauthorized
```

### 28. Access Admin Endpoint without Authentication
```
Method: GET
URL: {{base_url}}/admin/dashboard
Headers: None

Expected Response: 401 Unauthorized
```

---

## 📄 Static Page Tests

### 29. GET Home Page (Redirect to Login)
```
Method: GET
URL: {{base_url}}/
Headers: None

Expected Response: 200 OK
Content-Type: text/html
Should show login page
```

### 30. GET Non-existent Endpoint
```
Method: GET
URL: {{base_url}}/nonexistent
Headers: None

Expected Response: 404 Not Found
```

---

## 🧪 Test Scenarios

### Scenario 1: Complete Admin Workflow
1. Login as admin
2. Create a new user
3. Create AWS keys
4. Assign keys to user
5. Verify user can see assigned keys

### Scenario 2: Complete User Workflow
1. Login as regular user
2. Check dashboard shows assigned keys
3. Create buckets in a region
4. Verify results page shows URLs

### Scenario 3: Security Testing
1. Try accessing admin endpoints as regular user
2. Try accessing protected endpoints without authentication
3. Try creating users with duplicate usernames
4. Try deleting your own admin account

---

## 📝 Test Data Setup

### Required Test Data:
```json
{
  "admin_user": {
    "username": "admin",
    "password": "admin123"
  },
  "test_user": {
    "username": "testuser",
    "password": "testpass123"
  },
  "test_aws_key": {
    "name": "test-key",
    "access_key": "AKIATEST123456789",
    "secret_key": "testSecretKey123456789abcdef"
  }
}
```

### Pre-test Scripts (Add to Postman Collection):
```javascript
// Set base URL
pm.environment.set("base_url", "http://localhost:8000");

// Function to extract cookies
function extractCookie(cookieName) {
    var cookies = pm.response.headers.get("Set-Cookie");
    if (cookies) {
        var cookieArray = cookies.split(";");
        for (var i = 0; i < cookieArray.length; i++) {
            var cookie = cookieArray[i].trim();
            if (cookie.startsWith(cookieName + "=")) {
                return cookie.substring(cookieName.length + 1);
            }
        }
    }
    return null;
}
```

### Common Test Scripts:
```javascript
// Check response time
pm.test("Response time is less than 2000ms", function () {
    pm.expect(pm.response.responseTime).to.be.below(2000);
});

// Check for HTML content
pm.test("Response is HTML", function () {
    pm.expect(pm.response.headers.get("Content-Type")).to.include("text/html");
});

// Check for successful redirect
pm.test("Successful redirect", function () {
    pm.expect(pm.response.code).to.be.oneOf([301, 302]);
});
```

---

## 🚀 Running the Tests

1. **Import into Postman**: Create a new collection and add these requests
2. **Set Environment Variables**: Create environment with base_url
3. **Run in Sequence**: Execute tests in the order provided
4. **Check Results**: Verify expected responses and status codes
5. **Monitor Performance**: Check response times and error rates

## ⚠️ Important Notes

- Ensure the FastAPI application is running before testing
- Initialize the database with `python init_db.py`
- Some tests require valid AWS credentials to fully succeed
- Test data will be created/modified during testing
- Use a test database for safety
- Cookie-based authentication requires proper cookie handling in Postman
