# Online Cinema

A **FastAPI-based online cinema platform** that lets users browse movies, manage carts and orders, and pay via Stripe.  
The project integrates **JWT authentication**, **Celery for background tasks**, **SendGrid for emails**, and **PostgreSQL** for persistent data.

---

## Tech Stack

|Category|Technology|
|---|---|
|Framework|FastAPI|
|Database|PostgreSQL|
|ORM|SQLAlchemy (async)|
|Auth|JWT (access/refresh)|
|Background Tasks|Celery + Redis|
|Payment|Stripe|
|Email|SendGrid|
|Testing|Pytest + pytest-asyncio + pytest-cov|
|Config|Pydantic BaseSettings|
|Containerization|Docker + Docker Compose|

## Features

- User authentication and registration with JWT
    
- Role-based access control (user, admin)
    
- Full movie catalog with availability filtering
    
- Shopping cart and order management
    
- Stripe payment integration
    
- Email notifications via SendGrid
    
- Admin endpoints for managing users, movies, and orders
    
- Celery background tasks (email, async operations)
    
- Full test suite with pytest and coverage reporting

### 1. Clone the repository

```
git clone https://github.com/RomanSapunGit/online-cinema.git
cd online-cinema

```

### 2. Create and activate a virtual environment

```
python -m venv venv
source venv/bin/activate      # macOS/Linux
venv\Scripts\activate         # Windows
```

## 3. Install dependencies

```
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the project root directory.  
Example:

```
# === DATABASE CONFIGURATION ===
POSTGRES_USER=postgres
POSTGRES_PASSWORD=yourpassword
POSTGRES_HOST=localhost
POSTGRES_DB_PORT=5432
POSTGRES_DB=online_cinema

# === JWT / AUTHENTICATION ===
SECRET_KEY_ACCESS=your_secret_key_access
SECRET_KEY_REFRESH=your_secret_key_refresh
JWT_SIGNING_ALGORITHM=HS256
LOGIN_TIME_DAYS=7

# === STRIPE PAYMENT CONFIG ===
STRIPE_API_KEY=sk_test_your_stripe_key
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret

# === EMAIL CONFIGURATION ===
SENDGRID_API_KEY=SG.xxxxxxx
EMAIL_SENDER=no-reply@onlinecinema.com

# === FRONTEND & URLS ===
FRONTEND_URL=http://localhost:8000

# === REDIS / CELERY ===
REDIS_URL=redis://localhost:6379/0

# === LOCAL FILE PATHS ===
PATH_TO_EMAIL_TEMPLATES_DIR=src/notifications/templates
ACTIVATION_EMAIL_TEMPLATE_NAME=activation_request.html
ACTIVATION_COMPLETE_EMAIL_TEMPLATE_NAME=activation_complete.html
PASSWORD_RESET_TEMPLATE_NAME=password_reset_request.html
PASSWORD_RESET_COMPLETE_TEMPLATE_NAME=password_reset_complete.html
NOTIFICATION_EMAIL_TEMPLATE_NAME=notification.html
PATH_TO_MOVIES_CSV=src/tests/seeds/test_data.csv

# === SECURITY / MISC ===
SECRET_KEY=some_random_string

```

## 5. Apply database migrations

```
alembic upgrade head
```

## Running with Docker

The easiest way to run the application locally is via Docker Compose.

### 1. Build and start the containers

```
docker-compose up --build
```

This will start:

- **FastAPI app** (backend API)
    
- **PostgreSQL** database
    
- **Redis** (Celery broker)
    
- **Celery worker** (Needs to send email notifications and schedulers)
    
- **Ngrok tunnel** (optional, for testing payment integration)

## Running the Application (Locally)

```
uvicorn src.main:app --reload
```

Then open:  
http://localhost:8000/docs

## Testing

### Run all tests


```
pytest
```

### Run tests with coverage report

```
pytest --cov=src --cov-report=html --cov-branch --cov-config=.coveragerc
```

After running, open `htmlcov/index.html` in your browser to view the coverage report.
