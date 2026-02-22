#!/usr/bin/env python3
"""
Script de inicialización de la base de datos
Ejecutar este script después de configurar la base de datos MySQL
"""

from app import create_app, db
from app.models import User
import os

def init_database():
    """Inicializar la base de datos con datos básicos"""
    app = create_app()
    
    with app.app_context():
        print("Creando tablas de base de datos...")
        db.create_all()
        
        # Verificar si ya existe el usuario administrador
        admin = User.query.filter_by(username='admin').first()
        
        if not admin:
            print("Creando usuario administrador...")
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
            
            # Crear algunos usuarios de ejemplo
            print("Creando usuarios de ejemplo...")
            
            user1 = User(
                username='usuario1',
                email='usuario1@ejemplo.com',
                first_name='Juan',
                last_name='Pérez',
                is_active=True,
                email_confirmed=True
            )
            user1.set_password('usuario123')
            
            user2 = User(
                username='usuario2',
                email='usuario2@ejemplo.com',
                first_name='María',
                last_name='García',
                is_active=True,
                email_confirmed=False
            )
            user2.set_password('usuario123')
            
            db.session.add(user1)
            db.session.add(user2)
            
            try:
                db.session.commit()
                print("✅ Base de datos inicializada correctamente!")
                print("\n--- CREDENCIALES DE ACCESO ---")
                print("👑 Administrador:")
                print("   Usuario: admin")
                print("   Contraseña: admin123")
                print("   Email: admin@sistema.com")
                print("\n👤 Usuario de ejemplo 1:")
                print("   Usuario: usuario1")
                print("   Contraseña: usuario123")
                print("   Email: usuario1@ejemplo.com")
                print("\n👤 Usuario de ejemplo 2:")
                print("   Usuario: usuario2")
                print("   Contraseña: usuario123")
                print("   Email: usuario2@ejemplo.com")
                print("\n⚠️  IMPORTANTE: Cambia estas contraseñas en producción!")
                
            except Exception as e:
                print(f"❌ Error al inicializar la base de datos: {e}")
                db.session.rollback()
        else:
            print("✅ La base de datos ya está inicializada.")
            print("👑 Usuario administrador ya existe.")


if __name__ == '__main__':
    # Verificar archivo .env
    if not os.path.exists('.env'):
        print("⚠️  ADVERTENCIA: No se encontró archivo .env")
        print("📁 Copia .env.example a .env y configura tus variables")
        print("🔗 Asegúrate de configurar la conexión a MySQL/MariaDB")
        response = input("\n¿Continuar de todos modos? (s/N): ")
        if response.lower() not in ['s', 'si', 'sí', 'y', 'yes']:
            print("❌ Cancelado por el usuario.")
            exit(1)
    
    init_database()