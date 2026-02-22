from flask import Blueprint

bp = Blueprint('main', __name__)

# Importar todas las rutas
from app.routes import main, admin, auth, inventario, usuarios, ventas, gallinas