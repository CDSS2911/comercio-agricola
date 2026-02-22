#!/usr/bin/env python3
"""
Script para generar lotes de huevos mensuales
Genera datos realistas de recolección de huevos para pruebas
"""

import random
import datetime
from datetime import timedelta
import calendar

def generar_peso_realista():
    """Genera un peso realista para huevos de gallina (45-80 gramos)"""
    # Distribución normal con media en 60g y desviación estándar de 8g
    peso = random.normalvariate(60, 8)
    # Limitar entre 40 y 85 gramos
    return max(40, min(85, round(peso, 1)))

def generar_cantidad_diaria():
    """Genera una cantidad realista de huevos por día (50-150 huevos)"""
    # Más huevos en días de semana, menos en fines de semana
    base = random.randint(80, 120)
    variacion = random.randint(-20, 30)
    return max(50, base + variacion)

def generar_sql_lotes_mensuales(año=2024, meses=12, usuario_id=1):
    """
    Genera SQL para crear lotes de huevos mensuales
    
    Args:
        año: Año para generar los datos
        meses: Número de meses a generar
        usuario_id: ID del usuario que realiza la recolección
    """
    
    sql_commands = []
    sql_commands.append("-- Script para generar lotes de huevos mensuales")
    sql_commands.append("-- Generado automáticamente")
    sql_commands.append("")
    
    # Obtener categorías existentes (asumiendo que ya existen)
    sql_commands.append("-- Asegurar que las categorías existan")
    sql_commands.append("""
INSERT IGNORE INTO categoria_huevo (nombre, peso_min, peso_max, precio_base, activo) VALUES
('Extra Grande', 73, 85, 0.35, 1),
('Grande', 63, 72, 0.30, 1),
('Mediano', 53, 62, 0.25, 1),
('Pequeño', 43, 52, 0.20, 1),
('Mini', 35, 42, 0.15, 1);
""")
    sql_commands.append("")
    
    lote_counter = 1
    huevo_id = 1
    
    for mes in range(1, meses + 1):
        if mes > 12:
            break
            
        # Calcular días del mes
        dias_en_mes = calendar.monthrange(año, mes)[1]
        
        sql_commands.append(f"-- Lotes para {calendar.month_name[mes]} {año}")
        
        for dia in range(1, dias_en_mes + 1):
            fecha = datetime.date(año, mes, dia)
            
            # Generar entre 1-3 lotes por día (más común 1-2)
            num_lotes = random.choices([1, 2, 3], weights=[50, 40, 10])[0]
            
            for lote_del_dia in range(num_lotes):
                # Generar número de lote
                numero_lote = f"{fecha.strftime('%Y%m%d')}-{str(lote_del_dia + 1).zfill(3)}"
                
                # Hora de inicio (entre 6:00 AM y 4:00 PM)
                hora_inicio = fecha.strftime('%Y-%m-%d') + f" {random.randint(6, 16):02d}:{random.randint(0, 59):02d}:00"
                
                # Generar cantidad de huevos para este lote
                cantidad_huevos = generar_cantidad_diaria()
                if num_lotes > 1:
                    cantidad_huevos = cantidad_huevos // num_lotes
                
                # SQL para insertar el lote
                sql_commands.append(f"""
INSERT INTO lote_recoleccion (
    numero_lote, fecha_recoleccion, hora_inicio, hora_fin, 
    usuario_id, estado, total_huevos, total_peso, huevos_rotos
) VALUES (
    '{numero_lote}', '{fecha}', '{hora_inicio}', 
    DATE_ADD('{hora_inicio}', INTERVAL {random.randint(30, 120)} MINUTE),
    {usuario_id}, 'COMPLETADO', 0, 0, 0
);""")
                
                # Obtener el ID del lote (asumiendo que se incrementa automáticamente)
                lote_id = f"(SELECT id FROM lote_recoleccion WHERE numero_lote = '{numero_lote}')"
                
                # Generar huevos para este lote
                huevos_buenos = 0
                huevos_rotos = 0
                peso_total = 0
                
                sql_huevos = []
                for huevo_num in range(cantidad_huevos):
                    peso = generar_peso_realista()
                    roto = random.random() < 0.05  # 5% de probabilidad de estar roto
                    
                    if roto:
                        huevos_rotos += 1
                    else:
                        huevos_buenos += 1
                        peso_total += peso
                    
                    # Determinar categoría basada en peso
                    if peso >= 73:
                        categoria_id = "(SELECT id FROM categoria_huevo WHERE nombre = 'Extra Grande')"
                    elif peso >= 63:
                        categoria_id = "(SELECT id FROM categoria_huevo WHERE nombre = 'Grande')"
                    elif peso >= 53:
                        categoria_id = "(SELECT id FROM categoria_huevo WHERE nombre = 'Mediano')"
                    elif peso >= 43:
                        categoria_id = "(SELECT id FROM categoria_huevo WHERE nombre = 'Pequeño')"
                    else:
                        categoria_id = "(SELECT id FROM categoria_huevo WHERE nombre = 'Mini')"
                    
                    timestamp = hora_inicio.replace('00', f"{random.randint(0, 59):02d}")
                    
                    sql_huevos.append(f"""
    ({peso}, {1 if roto else 0}, '{timestamp}', {lote_id}, {categoria_id if not roto else 'NULL'}, 0, NULL)""")
                
                # Insertar todos los huevos del lote
                if sql_huevos:
                    sql_commands.append(f"""
INSERT INTO huevo (peso, roto, timestamp, lote_id, categoria_id, vendido, fecha_venta) VALUES{','.join(sql_huevos)};""")
                
                # Actualizar estadísticas del lote
                sql_commands.append(f"""
UPDATE lote_recoleccion SET 
    total_huevos = {huevos_buenos},
    total_peso = {round(peso_total, 1)},
    huevos_rotos = {huevos_rotos}
WHERE numero_lote = '{numero_lote}';""")
                
                sql_commands.append("")
                lote_counter += 1
    
    sql_commands.append("-- Fin del script de generación de lotes")
    sql_commands.append(f"-- Total de lotes generados: {lote_counter - 1}")
    
    return '\n'.join(sql_commands)

def generar_archivo_sql():
    """Genera el archivo SQL con los lotes"""
    
    print("=== Generador de Lotes de Huevos Mensuales ===")
    print()
    
    # Obtener parámetros del usuario
    año = input("Año para generar datos (default: 2024): ").strip()
    if not año:
        año = 2024
    else:
        año = int(año)
    
    meses = input("Número de meses a generar (1-12, default: 12): ").strip()
    if not meses:
        meses = 12
    else:
        meses = int(meses)
        meses = max(1, min(12, meses))
    
    usuario_id = input("ID del usuario recolector (default: 1): ").strip()
    if not usuario_id:
        usuario_id = 1
    else:
        usuario_id = int(usuario_id)
    
    print()
    print(f"Generando lotes para {meses} meses del año {año}...")
    print("Esto puede tomar un momento...")
    
    # Generar SQL
    sql_content = generar_sql_lotes_mensuales(año, meses, usuario_id)
    
    # Guardar archivo
    filename = f"lotes_huevos_{año}_{meses}meses.sql"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(sql_content)
    
    print(f"✓ Archivo SQL generado: {filename}")
    print(f"✓ Para aplicar los datos: mysql -u usuario -p database_name < {filename}")
    print()
    
    # Mostrar estadísticas estimadas
    dias_estimados = sum(calendar.monthrange(año, m)[1] for m in range(1, meses + 1))
    lotes_estimados = dias_estimados * 1.5  # Promedio de 1.5 lotes por día
    huevos_estimados = lotes_estimados * 100  # Promedio de 100 huevos por lote
    
    print("=== Estadísticas Estimadas ===")
    print(f"Días con datos: {dias_estimados}")
    print(f"Lotes estimados: {int(lotes_estimados)}")
    print(f"Huevos estimados: {int(huevos_estimados)}")
    print()

if __name__ == "__main__":
    generar_archivo_sql()