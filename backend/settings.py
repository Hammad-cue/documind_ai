"""
Django settings for DocuMind AI (v2).

All environment-specific values come from environment variables / .env.
See .env.example for the full list.
"""
import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')


def env(name, default=None):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    return str(env(name, '1' if default else '0')).lower() in ('1', 'true', 'yes', 'on')


SECRET_KEY = env('DJANGO_SECRET_KEY', 'dev-only-insecure-key-change-me')
DEBUG = env_bool('DJANGO_DEBUG', True)
ALLOWED_HOSTS = [h.strip() for h in env('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if h.strip()]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.postgres',
    'rest_framework',
    'corsheaders',
    'accounts',
    'documents',
    'assistant',
    'audit',
    'notifications',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
]

ROOT_URLCONF = 'backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'backend.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env('DB_NAME', 'docuvault_db'),
        'USER': env('DB_USER', 'postgres'),
        'PASSWORD': env('DB_PASSWORD', 'mysecretpassword'),
        'HOST': env('DB_HOST', 'localhost'),
        'PORT': env('DB_PORT', '5433'),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Karachi'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Uploads
MAX_UPLOAD_MB = int(env('MAX_UPLOAD_MB', '25'))
MAX_PAGES = int(env('MAX_PAGES', '300'))
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_MB * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

# CORS: only the Vite dev server
CORS_ALLOWED_ORIGINS = [o.strip() for o in env('CORS_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173').split(',')]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_THROTTLE_CLASSES': (
        'rest_framework.throttling.UserRateThrottle',
        'rest_framework.throttling.AnonRateThrottle',
    ),
    'DEFAULT_THROTTLE_RATES': {
        'user': '600/hour',
        'anon': '60/hour',
        'assistant': env('ASSISTANT_RATE', '20/min'),
    },
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=8),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
}

# ---- AI / processing configuration ----
LLM_PROVIDER = env('LLM_PROVIDER', 'groq')
LLM_MODEL = env('LLM_MODEL', 'openai/gpt-oss-20b')
# Used automatically when the main text model is rate-limited or down (only if its API key is set)
LLM_FALLBACK_PROVIDER = env('LLM_FALLBACK_PROVIDER', 'gemini')
LLM_FALLBACK_MODEL = env('LLM_FALLBACK_MODEL', 'gemini-flash-lite-latest')
VISION_PROVIDER = env('VISION_PROVIDER', 'gemini')
VISION_MODEL = env('VISION_MODEL', 'gemini-2.5-flash')
EMBEDDING_MODEL = env('EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
EMBEDDING_DIM = 384
CLAUSE_MODEL_DIR = BASE_DIR / env('CLAUSE_MODEL_DIR', 'ml/models/clause-classifier')
TESSERACT_CMD = env('TESSERACT_CMD', r'C:\Program Files\Tesseract-OCR\tesseract.exe')
HANDWRITING_CONFIDENCE_THRESHOLD = float(env('HANDWRITING_CONFIDENCE_THRESHOLD', '70'))
# Field confidence below this goes to the human verification queue
REVIEW_CONFIDENCE_THRESHOLD = float(env('REVIEW_CONFIDENCE_THRESHOLD', '0.75'))
# Reminders: in-app always; e-mail only when REMINDER_EMAILS=1 (console backend prints mails in development)
REMINDER_EMAILS = env_bool('REMINDER_EMAILS', False)
APP_URL = env('APP_URL', 'http://localhost:5173')
EMAIL_BACKEND = env('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', 'DocuMind <noreply@documind.local>')
# When True, uploads are processed inside the request (tests / demos without a worker)
PROCESS_INLINE = env_bool('PROCESS_INLINE', False)
