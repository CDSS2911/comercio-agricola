#!/usr/bin/env python3
"""
Script para limpiar e inicializar la base de datos con el nuevo esquema de inventario de huevos
"""
from app import create_app, db
from app.models import User, CategoriaHuevo
from werkzeug.security import generate_password_hash
import os

def init_database():
    """Inicializar la base de datos con datos básicos"""
    app = create_app()
    
    with app.app_context():
        try:
            # Deshabilitar restricciones de claves foráneas temporalmente
            print("⚠️  Deshabilitando restricciones de claves foráneas...")
            with db.engine.connect() as conn:
                conn.execute(db.text("SET FOREIGN_KEY_CHECKS = 0"))
                conn.commit()
            
            # Limpiar todas las tablas
            print("🗑️  Limpiando base de datos...")
            db.drop_all()
            
            # Crear todas las tablas
            print("🏗️  Creando tablas...")
            db.create_all()
            
            # Crear usuario administrador por defecto
            print("👤 Creando usuario administrador...")
            admin = User(
                username='admin',
                email='admin@granja.com',
                first_name='Administrador',
                last_name='Sistema',
                is_active=True,
                is_admin=True,
                email_confirmed=True
            )
            admin.set_password('admin123')
            db.session.add(admin)
            
            # Crear categorías predeterminadas de huevos
            print("🏷️  Creando categorías de huevos...")
            categorias = [
                {'nombre': 'XL', 'peso_min': 73.0, 'peso_max': 100.0, 'precio_venta': 0.60},
                {'nombre': 'L', 'peso_min': 63.0, 'peso_max': 72.9, 'precio_venta': 0.55},
                {'nombre': 'M', 'peso_min': 53.0, 'peso_max': 62.9, 'precio_venta': 0.50},
                {'nombre': 'S', 'peso_min': 43.0, 'peso_max': 52.9, 'precio_venta': 0.45},
            ]
            
            for cat_data in categorias:
                categoria = CategoriaHuevo(
                    nombre=cat_data['nombre'],
                    peso_min=cat_data['peso_min'],
                    peso_max=cat_data['peso_max'],
                    precio_venta=cat_data['precio_venta'],
                    activo=True
                )
                db.session.add(categoria)
            
            # Guardar todos los cambios
            db.session.commit()
            
            # Rehabilitar restricciones de claves foráneas
            print("🔒 Habilitando restricciones de claves foráneas...")
            with db.engine.connect() as conn:
                conn.execute(db.text("SET FOREIGN_KEY_CHECKS = 1"))
                conn.commit()
            
            print("✅ Base de datos inicializada correctamente!")
            print("\n📋 Resumen:")
            print(f"   👤 Usuario admin creado (admin/admin123)")
            print(f"   🏷️  {len(categorias)} categorías de huevos creadas")
            print("\n🚀 El sistema de inventario de huevos está listo!")
            
        except Exception as e:
            print(f"❌ Error al inicializar la base de datos: {e}")
            db.session.rollback()

if __name__ == '__main__':
    init_database()