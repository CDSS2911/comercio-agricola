import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

def _to_bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in {'true', '1', 'on', 'yes'}


class Config:
    # Configuracion basica de Flask
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'clave-secreta-super-segura-cambiar-en-produccion'

    # Configuracion de la base de datos MySQL/MariaDB
    # Desarrollo
    MYSQL_HOST = os.environ.get('MYSQL_HOST') or 'localhost'
    MYSQL_PORT = int(os.environ.get('MYSQL_PORT') or 3306)
    MYSQL_USER = os.environ.get('MYSQL_USER') or 'root'
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD') or ''
    MYSQL_DB = os.environ.get('MYSQL_DB') or 'gestion_usuarios' 

    # Produccion
    # MYSQL_HOST = os.environ.get('MYSQL_HOST') or '185.181.254.86'
    # MYSQL_PORT = int(os.environ.get('MYSQL_PORT') or 3306)
    # MYSQL_USER = os.environ.get('MYSQL_USER') or 'hrentubo_root'
    # MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD') or 'Huevos.2026'
    # MYSQL_DB = os.environ.get('MYSQL_DB') or 'hrentubo_rambo'

    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        f'mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Correo SSL: toma entorno si existe; si no, usa estos valores por defecto.
    MAIL_SERVER = os.environ.get('SMTP_RAMBO_SERVER') or 'mail.hrentubolsillo.org'
    MAIL_PORT = int(os.environ.get('SMTP_RAMBO_PORT') or 465)
    MAIL_USE_SSL = _to_bool(os.environ.get('SMTP_RAMBO_USE_SSL'), True)
    MAIL_USE_TLS = _to_bool(os.environ.get('SMTP_RAMBO_USE_TLS'), False)
    MAIL_USERNAME = os.environ.get('SMTP_RAMBO_USERNAME') or 'huevos.rambo@hrentubolsillo.org'
    MAIL_PASSWORD = os.environ.get('SMTP_RAMBO_PASSWORD') or 'Cdss_29112002'
    MAIL_DEFAULT_SENDER = os.environ.get('SMTP_RAMBO_DEFAULT_SENDER') or 'huevos.rambo@hrentubolsillo.org'
    APP_NAME = os.environ.get('APP_NAME') or 'Huevos Rambo'

    SCALE_API_TOKEN = os.environ.get('SCALE_API_TOKEN') or ''

    # Configuracion de paginacion
    POSTS_PER_PAGE = 10

    # Zona horaria operativa del sistema
    APP_TIMEZONE = os.environ.get('APP_TIMEZONE') or 'America/Bogota'
