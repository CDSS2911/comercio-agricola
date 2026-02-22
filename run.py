#!/usr/bin/env python3
"""
Script principal para ejecutar la aplicación Flask
"""

import os
from app import create_app, db
from app.models import User
from flask_migrate import upgrade

app = create_app()


def create_tables():
    """Crear tablas de base de datos si no existen"""
    with app.app_context():
        db.create_all()
        
        # Crear usuario administrador por defecto si no existe
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin_user = User(
                username='admin',
                email='admin@sistema.com',
                first_name='Administrador',
                last_name='Sistema',
                is_admin=True,
                is_active=True,
                email_confirmed=True
            )
            admin_user.set_password('admin123')
            db.session.add(admin_user)
            db.session.commit()
            print("Usuario administrador creado - Username: admin, Password: admin123")


@app.shell_context_processor
def make_shell_context():
    """Contexto de shell para facilitar el desarrollo"""
    return {
        'db': db,
        'User': User
    }


if __name__ == '__main__':
    # Verificar si existe archivo .env
    if not os.path.exists('.env'):
        print("¡ADVERTENCIA! No se encontró archivo .env")
        print("Copia .env.example a .env y configura tus variables de entorno")
    
    # Inicializar la base de datos
    create_tables()
    
    app.run(debug=True, host='0.0.0.0', port=5000)