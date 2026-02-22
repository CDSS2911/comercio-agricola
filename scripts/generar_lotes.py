#!/usr/bin/env python3
"""
Script Python para generar lotes de huevos mensuales usando SQLAlchemy
Ejecutar desde la raíz del proyecto Flask
"""

import sys
import os
import random
import datetime
from datetime import timedelta
import calendar

# Añadir el directorio del proyecto al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import User, CategoriaHuevo, LoteRecoleccion, Huevo

def generar_peso_realista():
    """Genera un peso realista para huevos de gallina (40-85 gramos)"""
    # Distribución que favorece pesos entre 55-70g
    peso = random.normalvariate(60, 8)
    return max(40, min(85, round(peso, 1)))

def generar_cantidad_diaria():
    """Genera una cantidad realista de huevos por día"""
    # Más variabilidad: 50-150 huevos por día
    base = random.randint(80, 120)
    variacion = random.randint(-30, 30)
    return max(50, base + variacion)

def crear_categorias_si_no_existen():
    """Crea las categorías de huevos si no existen"""
    categorias = [
        {'nombre': 'Extra Grande', 'peso_min': 73, 'peso_max': 85, 'precio_venta': 0.35},
        {'nombre': 'Grande', 'peso_min': 63, 'peso_max': 72, 'precio_venta': 0.30},
        {'nombre': 'Mediano', 'peso_min': 53, 'peso_max': 62, 'precio_venta': 0.25},
        {'nombre': 'Pequeño', 'peso_min': 43, 'peso_max': 52, 'precio_venta': 0.20},
        {'nombre': 'Mini', 'peso_min': 35, 'peso_max': 42, 'precio_venta': 0.15},
    ]
    
    for cat_data in categorias:
        categoria = CategoriaHuevo.query.filter_by(nombre=cat_data['nombre']).first()
        if not categoria:
            categoria = CategoriaHuevo(
                nombre=cat_data['nombre'],
                peso_min=cat_data['peso_min'],
                peso_max=cat_data['peso_max'],
                precio_venta=cat_data['precio_venta'],
                activo=True
            )
            db.session.add(categoria)
    
    db.session.commit()
    print("✓ Categorías de huevos verificadas/creadas")

def generar_lotes_mensuales(año=2024, meses=12, usuario_id=1):
    """
    Genera lotes de huevos para los meses especificados
    """
    
    # Verificar que el usuario existe
    usuario = db.session.get(User, usuario_id)
    if not usuario:
        print(f"❌ Error: No se encontró el usuario con ID {usuario_id}")
        return False
    
    print(f"Generando lotes para el usuario: {usuario.username}")
    
    # Crear categorías si no existen
    crear_categorias_si_no_existen()
    
    # Obtener todas las categorías
    categorias = CategoriaHuevo.query.filter_by(activo=True).all()
    if not categorias:
        print("❌ Error: No se encontraron categorías activas")
        return False
    
    total_lotes = 0
    total_huevos = 0
    
    for mes in range(1, min(meses + 1, 13)):
        print(f"Generando datos para {calendar.month_name[mes]} {año}...")
        
        # Calcular días del mes
        dias_en_mes = calendar.monthrange(año, mes)[1]
        
        for dia in range(1, dias_en_mes + 1):
            fecha = datetime.date(año, mes, dia)
            
            # Generar 1-3 lotes por día (más común 1-2)
            num_lotes = random.choices([1, 2, 3], weights=[50, 40, 10])[0]
            
            for lote_del_dia in range(num_lotes):
                # Crear lote
                lote = LoteRecoleccion(
                    fecha_recoleccion=fecha,
                    hora_inicio=datetime.datetime.combine(fecha, datetime.time(
                        hour=random.randint(6, 16),
                        minute=random.randint(0, 59)
                    )),
                    usuario_id=usuario_id,
                    estado='COMPLETADO'
                )
                
                # Generar número de lote
                lote.generar_numero_lote()
                
                # Hora fin (30-120 minutos después del inicio)
                lote.hora_fin = lote.hora_inicio + timedelta(minutes=random.randint(30, 120))
                
                db.session.add(lote)
                db.session.flush()  # Para obtener el ID del lote
                
                # Generar huevos para este lote
                cantidad_huevos = generar_cantidad_diaria()
                if num_lotes > 1:
                    cantidad_huevos = cantidad_huevos // num_lotes
                
                huevos_creados = []
                for _ in range(cantidad_huevos):
                    peso = generar_peso_realista()
                    roto = random.random() < 0.05  # 5% probabilidad de estar roto
                    
                    huevo = Huevo(
                        peso=peso,
                        roto=roto,
                        timestamp=lote.hora_inicio + timedelta(
                            minutes=random.randint(0, 90)
                        ),
                        lote_id=lote.id
                    )
                    
                    # Clasificar por peso si no está roto
                    if not roto:
                        huevo.clasificar()
                    
                    huevos_creados.append(huevo)
                    db.session.add(huevo)
                
                # Actualizar estadísticas del lote
                lote.actualizar_estadisticas()
                
                total_lotes += 1
                total_huevos += cantidad_huevos
                
                # Commit cada 10 lotes para evitar problemas de memoria
                if total_lotes % 10 == 0:
                    db.session.commit()
                    print(f"  Procesados {total_lotes} lotes...")
    
    # Commit final
    db.session.commit()
    
    print(f"✅ Generación completada:")
    print(f"   📦 Total lotes creados: {total_lotes}")
    print(f"   🥚 Total huevos generados: {total_huevos}")
    print(f"   📅 Periodo: {meses} meses del año {año}")
    
    return True

def main():
    """Función principal"""
    print("=== Generador de Lotes de Huevos Mensuales ===")
    print("Conectando a la base de datos...")
    
    # Crear aplicación Flask
    app = create_app()
    
    with app.app_context():
        try:
            # Verificar conexión a la base de datos
            from sqlalchemy import text
            db.session.execute(text('SELECT 1'))
            print("✓ Conexión a la base de datos establecida")
            
            # Parámetros por defecto
            año = 2024
            meses = 12
            usuario_id = 1
            
            # Verificar si hay argumentos de línea de comandos
            if len(sys.argv) > 1:
                try:
                    año = int(sys.argv[1])
                except ValueError:
                    print("Advertencia: Año inválido, usando 2024")
            
            if len(sys.argv) > 2:
                try:
                    meses = max(1, min(12, int(sys.argv[2])))
                except ValueError:
                    print("Advertencia: Número de meses inválido, usando 12")
            
            if len(sys.argv) > 3:
                try:
                    usuario_id = int(sys.argv[3])
                except ValueError:
                    print("Advertencia: ID de usuario inválido, usando 1")
            
            print(f"Parámetros: Año={año}, Meses={meses}, Usuario ID={usuario_id}")
            print()
            
            # Confirmar antes de proceder
            respuesta = input("¿Continuar con la generación? (s/N): ").strip().lower()
            if respuesta not in ['s', 'si', 'sí', 'y', 'yes']:
                print("Operación cancelada.")
                return
            
            # Generar los datos
            if generar_lotes_mensuales(año, meses, usuario_id):
                print("\n🎉 ¡Generación exitosa!")
                print("Los datos están listos para usar en el dashboard.")
            else:
                print("\n❌ Error durante la generación.")
                
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            db.session.rollback()
            return
        finally:
            db.session.close()

if __name__ == "__main__":
    main()