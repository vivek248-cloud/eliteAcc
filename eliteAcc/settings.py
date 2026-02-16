
from pathlib import Path
import os


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent



SECRET_KEY = 'django-insecure-ie926!pa)-1=%6zn*c#wz$=4y#wtv536a(^dxp58x5uj!vurcc'

# SECURITY WARNING: don't run with debug turned on in production!

DEBUG = True

# DEBUG = False

ALLOWED_HOSTS = ['eliteaccounts.in', 'www.eliteaccounts.in', '31.97.62.126','*']

# ALLOWED_HOSTS = ['eliteaccounts.in', 'www.eliteaccounts.in', '31.97.62.126']

# Application definition

INSTALLED_APPS = [

    'admin_interface',
    'colorfield',

    'accountsApp',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',

    'accountsApp.middleware.SessionTimeoutMiddleware',  # 👈 ADD HERE custom middleware logout after 15min inactivity 

    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',

    
]

ROOT_URLCONF = 'eliteAcc.urls'

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

                'accountsApp.context_processors.selected_company',  # 👈 ADD HERE custom context processor for selected company
                # 'accountsApp.context_processors.smart_alerts',
                'accountsApp.context_processors.global_alerts',
            ],
        },
    },
]

WSGI_APPLICATION = 'eliteAcc.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'eliteacc',
        'USER': 'root',
        'PASSWORD': 'Admin123',
        'HOST': 'localhost',
        'PORT': '3306',
    }
}



# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.mysql',
#         'NAME': 'eliteaccounts_db',
#         'USER': 'eliteaccountuser',
#         'PASSWORD': 'Admin@123',
#         'HOST': 'localhost',
#         'PORT': '3306',
#     }
# }


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/




STATIC_URL = '/static/'

STATICFILES_DIRS = [
    BASE_DIR / "static",
]

STATIC_ROOT = BASE_DIR / "staticfiles"




MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')


# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True

EMAIL_HOST_USER = 'elitedreambuildersofficial@gmail.com'
EMAIL_HOST_PASSWORD = 'yhjfrgtlvcouqghe'  # remove spaces

DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

# IMPORTANT
EMAIL_TIMEOUT = 30




# SESSION_COOKIE_AGE = 15 * 60
# SESSION_SAVE_EVERY_REQUEST = True
