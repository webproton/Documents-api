# Documents-api

A **Documents API** application built with Django and Django REST Framework.

The system allows users to manage documents, document types, upload workflows, and document requests with email notifications, subscription plans, and admin control.

---

## 🚀 Tech Stack

- Python 3.11+
- Django
- Django REST Framework
- PostgreSQL
- Celery (background tasks)
- Redis (Celery broker)
- Stripe (subscriptions)
- AWS S3 (media storage)
- Docker & Docker Compose
- drf-yasg (API documentation)

---

## 📦 Features

### 📁 Document Types
- Managed by admin (via Django admin panel)
- Fields:
  - Name
  - Description
  - Optional template file
- Viewable by all users
- Searchable by name and description

---

### 🔐 Authentication
- Email + password registration/login
- Email confirmation after registration
- Social login (Google/Facebook)
- Stores:
  - First name
  - Last name
  - Email

---

### 📄 User Documents
- Upload documents (xls, csv, pdf)
- Fields:
  - Name
  - Document type
  - Expiration date
  - File
- Documents grouped by type (“folders”)
- Active / replaced document logic
- Filtering, sorting, searching
- Users can only access their own documents

---

### 📬 Document Requests
- Request documents from other users via email
- Secure one-time upload link:
  - expires in 30 days
  - disabled after upload
  - hard to guess (token-based)
- Resend limitation: once per hour
- Cancel request support

---

### 👤 User Profile
- Update:
  - Password
  - First name
  - Last name
  - Avatar

---

### 💳 Subscription Plans
- Default upload limit per user
- Stripe subscription integration
- Paid plan removes upload limits

---

### 🛠 Admin Features
- View all users and profiles
- Manage user plans
- View all documents (read-only)
- Search documents by:
  - name
  - author name
  - email
- Block/unblock users
- Bulk user actions

---

### ⏰ Automated Tasks
- Daily reminders for expiring documents
- Sent 30 days before expiration
- Implemented with Celery

---

## 🧪 Testing
- pytest / Django tests
- factory_boy for test data
- Covers:
  - API responses
  - permissions
  - document logic
  - token expiration

---

## 📚 API Documentation
Available via Swagger:
/api/docs/

Powered by drf-yasg

---

## ☁️ Storage
- Static and media files stored in AWS S3

---

## 🐳 Run with Docker

```bash
docker-compose up --build
```

🧹 Code Quality
    flake8
    pylint
    clean architecture principles
    DRF best practices

🌿 Git Workflow
    Main branch: main
    Feature branches per task
    Pull Requests required before merge


This project follows:

    REST API best practices
    modular Django architecture
    secure authentication flows