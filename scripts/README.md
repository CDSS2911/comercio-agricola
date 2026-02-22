# Scripts para Generar Lotes de Huevos

Este directorio contiene scripts para generar datos de prueba de lotes de huevos mensuales.

## Archivos Disponibles

### 1. `generar_lotes.py` (Recomendado)
Script Python que usa SQLAlchemy para generar datos directamente en la base de datos.

**Uso:**
```bash
# Desde la raíz del proyecto
python scripts/generar_lotes.py [año] [meses] [usuario_id]

# Ejemplos:
python scripts/generar_lotes.py                    # Año 2024, 12 meses, usuario 1
python scripts/generar_lotes.py 2024              # Año 2024, 12 meses, usuario 1  
python scripts/generar_lotes.py 2024 6            # Año 2024, 6 meses, usuario 1
python scripts/generar_lotes.py 2024 12 1         # Año 2024, 12 meses, usuario 1
```

**O usar el script rápido:**
```bash
python generar_datos.py
```

### 2. `lotes_mensuales.sql`
Script SQL con procedimiento almacenado para generar datos.

**Uso:**
```sql
-- Ejecutar en MySQL/MariaDB
mysql -u usuario -p nombre_base_datos < scripts/lotes_mensuales.sql

-- O dentro de MySQL:
source scripts/lotes_mensuales.sql;

-- Llamar el procedimiento manualmente:
CALL GenerarLotesMensuales(2024, 1, 12, 1);  -- año, mes_inicio, mes_fin, usuario_id
```

### 3. `generar_lotes_mensuales.py`
Generador interactivo que crea archivos SQL.

**Uso:**
```bash
python scripts/generar_lotes_mensuales.py
# Sigue las instrucciones en pantalla
```

## Datos Generados

Los scripts generan:

- **Lotes realistas**: 1-3 lotes por día
- **Huevos variados**: 50-150 huevos por lote  
- **Pesos realistas**: 40-85 gramos con distribución normal
- **Categorías automáticas**: Clasificación por peso
- **Huevos rotos**: ~5% de probabilidad
- **Horarios variados**: Recolección entre 6:00 AM y 6:00 PM

## Categorías de Huevos

Los scripts crean automáticamente estas categorías:

| Categoría    | Peso (g) | Precio Base |
|--------------|----------|-------------|
| Extra Grande | 73-85    | $0.35      |
| Grande       | 63-72    | $0.30      |
| Mediano      | 53-62    | $0.25      |
| Pequeño      | 43-52    | $0.20      |
| Mini         | 35-42    | $0.15      |

## Estadísticas Estimadas

Para un año completo (365 días):
- **Lotes**: ~550 lotes
- **Huevos**: ~55,000 huevos
- **Peso total**: ~3,300 kg

## Requisitos

- Python 3.6+
- Flask y SQLAlchemy configurados
- Base de datos MySQL/MariaDB
- Usuario válido en la tabla `user`

## Problemas Comunes

1. **Error de usuario**: Verifica que el usuario_id exista en la tabla `user`
2. **Error de conexión**: Asegúrate de que la base de datos esté corriendo
3. **Memoria**: Para grandes volúmenes, los datos se procesan en lotes

## Limpieza

Para eliminar todos los datos generados:

```sql
-- ⚠️ CUIDADO: Esto borra TODOS los datos
DELETE FROM huevo;
DELETE FROM lote_recoleccion;
ALTER TABLE huevo AUTO_INCREMENT = 1;
ALTER TABLE lote_recoleccion AUTO_INCREMENT = 1;
```