# Backend - VeriFi API

Django REST Framework backend for the VeriFi application.

## Tech Stack

- **Framework**: Django 6.0+
- **API**: Django REST Framework 3.16+
- **Python**: 3.12+
- **Server**: Gunicorn
- **CORS**: django-cors-headers

## Prerequisites

- Python 3.12 or higher
- pip or another Python package manager

## Installation

### 1. Create a Virtual Environment

```bash
# Navigate to the backend directory
cd backend

# Create a virtual environment
python3 -m venv venv

# Activate the virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -e .
```

Or if using the pyproject.toml directly:

```bash
pip install django django-cors-headers djangorestframework gunicorn
```

### 3. Apply Migrations

```bash
python manage.py migrate
```

### 4. Create a Superuser (Optional)

For admin access:

```bash
python manage.py createsuperuser
```

## Running the Development Server

```bash
python manage.py runserver
```

The API will be available at `http://localhost:8000`

Admin panel: `http://localhost:8000/admin`

## Project Structure

```
backend/
├── core/              # Main Django project settings
│   ├── settings.py    # Django settings
│   ├── urls.py        # URL routing
│   ├── asgi.py        # ASGI configuration
│   ├── wsgi.py        # WSGI configuration
│   └── __init__.py
├── manage.py          # Django management script
├── pyproject.toml     # Project dependencies
└── README.md          # This file
```

## Environment Variables

Create a `.env` file in the backend directory if needed for sensitive configuration:

```bash
DEBUG=True
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1
```

## Useful Commands

```bash
# Create a new Django app
python manage.py startapp appname

# Make migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic

# Run tests
python manage.py test
```

## CORS Configuration

Update `core/settings.py` to configure CORS if needed:

```python
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",  # Frontend dev server
    "http://localhost:3000",
]
```