# Permisos Centralizados

Este modulo evita tocar cada ruta cuando quieras crear o ajustar permisos.

## Archivos

- `app/permissions/rutas.py`
  - `PERMISSION_DEFINITIONS`: catalogo de permisos.
  - `ENDPOINT_PERMISSIONS`: mapa `endpoint -> permiso`.
  - `SYSTEM_ROLE_PERMISSIONS`: permisos base por rol del sistema.
- `app/permissions/service.py`
  - Aplica validacion global por endpoint.
  - Sincroniza permisos en BD al iniciar la app.

## Como crear un permiso nuevo

1. Agrega el permiso en `PERMISSION_DEFINITIONS`.
2. Asigna el permiso a uno o varios endpoints en `ENDPOINT_PERMISSIONS`.
3. (Opcional) agrega el permiso a roles base en `SYSTEM_ROLE_PERMISSIONS`.
4. Reinicia la app.

La app sincroniza automaticamente los permisos definidos en `PERMISSION_DEFINITIONS`.

## Ejemplo rapido

```python
PERMISSION_DEFINITIONS['ventas.refunds.create'] = (
    'Crear devoluciones',
    'ventas',
    'Registrar devoluciones de ventas'
)

ENDPOINT_PERMISSIONS['ventas.crear_devolucion'] = 'ventas.refunds.create'
```
