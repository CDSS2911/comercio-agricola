# Huevos Rambo - Manual de Despliegue en cPanel

Sistema web para gestion de produccion, inventario y ventas de huevos, con control de lotes de gallinas, novedades sanitarias, gastos, permisos y reportes Excel.

## 1) Resumen Tecnico

- Framework: Flask 2.3
- ORM: SQLAlchemy + Flask-Migrate
- Base de datos: MySQL/MariaDB
- Autenticacion: Flask-Login
- Formularios: Flask-WTF
- Exportes: openpyxl
- Servidor en cPanel: Passenger (Python App)

## 2) Infraestructura Recomendada (Hosting con cPanel)

### Minimos

- cPanel con modulo `Setup Python App` habilitado.
- Python 3.10 o superior (recomendado 3.11).
- MySQL 8+ o MariaDB 10.5+.
- 1 vCPU, 1 GB RAM, 10 GB disco SSD.
- SSL activo en dominio/subdominio.

### Recomendado para produccion estable

- 2 vCPU, 2 GB RAM, 20+ GB SSD.
- Backups diarios (archivos + base de datos).
- Entorno separado por ambiente:
  - `prod`: app publica.
  - `stg`: pruebas previas.

## 3) Estructura del Proyecto

```text
app/
  __init__.py
  models.py
  forms.py
  routes/
    auth.py
    main.py
    admin.py
    usuarios.py
    inventario.py
    ventas.py
    gallinas.py
  permissions/
    rutas.py
    service.py
  templates/
  static/
migrations/
config.py
run.py
requirements.txt
```

## 4) Variables de Entorno

Configuralas en cPanel (Python App -> Environment Variables) o en `.env`.

```env
SECRET_KEY=CAMBIAR_ESTA_CLAVE_EN_PRODUCCION

MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=usuario_db
MYSQL_PASSWORD=clave_db
MYSQL_DB=nombre_db

# Opcional: si usas URL completa de SQLAlchemy
# DATABASE_URL=mysql+pymysql://usuario_db:clave_db@localhost:3306/nombre_db

MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=correo@dominio.com
MAIL_PASSWORD=clave_app_mail
MAIL_DEFAULT_SENDER=noreply@dominio.com
APP_NAME=Huevos Rambo

SCALE_API_TOKEN=token_para_balanza
```

Notas:
- `SECRET_KEY` debe ser unica y larga en produccion.
- Si defines `DATABASE_URL`, tiene prioridad sobre `MYSQL_*`.

## 5) Despliegue Paso a Paso en cPanel

## 5.1 Crear base de datos

1. Ir a `MySQL Databases`.
2. Crear BD, usuario y asignar permisos `ALL PRIVILEGES`.
3. Guardar: host, puerto, nombre, usuario, password.

## 5.2 Subir codigo

Opciones:
- `Git Version Control` (recomendado).
- `File Manager` + ZIP.

Ubica el codigo en una ruta tipo:
- `/home/USUARIO/apps/huevos_rambo`

## 5.3 Crear la Python App

En `Setup Python App`:
1. Python version: 3.11 (o la mas alta disponible y compatible).
2. Application root: `/home/USUARIO/apps/huevos_rambo`
3. Application URL: dominio o subdominio (ej. `app.tudominio.com`).
4. Application startup file:
   - usar `passenger_wsgi.py` (crearlo en la raiz del proyecto).
5. Application Entry point:
   - `application`

## 5.4 Crear `passenger_wsgi.py`

Archivo en la raiz del proyecto:

```python
import os
import sys

BASE_DIR = os.path.dirname(__file__)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import create_app

application = create_app()
```

## 5.5 Instalar dependencias

Desde Terminal de cPanel (dentro de la app root), activa el virtualenv que crea cPanel y ejecuta:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

Si cPanel no inyecta automaticamente el venv, usa la ruta que muestra `Setup Python App` en el boton de activacion.

## 5.6 Configurar variables de entorno

En `Setup Python App` -> `Environment Variables`, cargar todas las del punto 4.

## 5.7 Ejecutar migraciones

Con el virtualenv activo, dentro de la raiz del proyecto:

```bash
export FLASK_APP=run.py
flask db upgrade
```

Si necesitas inicializar datos base (solo primer despliegue):

```bash
python init_db.py
```

Atencion:
- `init_inventario_db.py` hace `drop_all()` y recrea tablas. No usar en produccion.

## 5.8 Reiniciar aplicacion

En `Setup Python App`, click en `Restart`.

## 5.9 Verificar

- Abrir URL publica de la app.
- Login con usuario administrador.
- Revisar menus segun permisos.
- Probar exporte Excel y modulos clave.

## 6) Flujo de Actualizacion (Releases)

1. Subir cambios (git pull o nuevo deploy).
2. `pip install -r requirements.txt` (si cambiaron dependencias).
3. `flask db upgrade` (si hay migraciones nuevas).
4. Reiniciar Python App en cPanel.
5. Validar rutas criticas.

## 7) Permisos del Sistema (RBAC)

El sistema ya esta centralizado para que no debas tocar cada ruta manualmente:

- Catalogo de permisos: `app/permissions/rutas.py` -> `PERMISSION_DEFINITIONS`
- Mapeo endpoint->permiso: `app/permissions/rutas.py` -> `ENDPOINT_PERMISSIONS`
- Roles base: `app/permissions/rutas.py` -> `SYSTEM_ROLE_PERMISSIONS`
- Servicio de validacion: `app/permissions/service.py`

Al iniciar la app, los permisos definidos se sincronizan automaticamente en BD.

## 8) Backups y Recuperacion

### Backup de base de datos

Usar cron diario con `mysqldump` (si el hosting lo permite), o backup nativo de cPanel.

Ejemplo:

```bash
mysqldump -u USUARIO_DB -p'NOMBRE_CLAVE' NOMBRE_DB > /home/USUARIO/backups/huevos_rambo_$(date +%F).sql
```

### Backup de archivos

Respaldar:
- Codigo fuente.
- Archivos subidos por usuarios (si aplica).
- `.env` (en almacenamiento seguro, no en repositorio publico).

## 9) Observabilidad y Logs

Revisar en cPanel:
- `Metrics` -> `Errors`.
- Logs de Passenger/Python App.
- Logs web del dominio.

Recomendado:
- Registrar errores en archivo y rotarlos.
- Monitorear 500, tiempos de respuesta y uso de memoria.

## 10) Troubleshooting Rapido

### Error 500 al iniciar

- Confirmar `passenger_wsgi.py` y entry point `application`.
- Confirmar `pip install -r requirements.txt` sin errores.
- Revisar variables de entorno faltantes.

### Error de conexion MySQL

- Verificar usuario/clave/host/puerto.
- Verificar privilegios del usuario sobre la BD.
- Probar conexion desde terminal del hosting.

### Plantillas con texto raro (Numero, Produccion)

- Guardar archivos en UTF-8 sin BOM.
- Evitar doble conversion de encoding.

### Migraciones no aplican

- Confirmar `FLASK_APP=run.py`.
- Ejecutar `flask db current` y `flask db heads`.
- Correr `flask db upgrade` y revisar salida.

## 11) MER (Modelo Entidad-Relacion)

Diagrama Mermaid (puedes pegarlo en cualquier visor Mermaid):

```mermaid
erDiagram
    USER {
        int id PK
        string username
        string email
    }

    ROLE {
        int id PK
        string slug
        string name
    }

    PERMISSION {
        int id PK
        string code
        string module
    }

    USER_ROLES {
        int user_id FK
        int role_id FK
    }

    ROLE_PERMISSIONS {
        int role_id FK
        int permission_id FK
    }

    LOGIN_ATTEMPT {
        int id PK
        string ip_address
        string username_attempted
    }

    PESA {
        int id PK
        string nombre
        string puerto
    }

    LOTE_GALLINAS {
        int id PK
        string numero_lote
        int usuario_id FK
    }

    CATEGORIA_HUEVO {
        int id PK
        string nombre
        float peso_min
        float peso_max
    }

    LOTE_RECOLECCION {
        int id PK
        string numero_lote
        int usuario_id FK
        int lote_gallinas_id FK
        int pesa_id FK
    }

    HUEVO {
        int id PK
        float peso
        int lote_id FK
        int categoria_id FK
    }

    INVENTARIO_HUEVOS {
        int id PK
        int categoria_id FK
        int cantidad_disponible
    }

    GASTO {
        int id PK
        datetime fecha_hora
        decimal valor
        string tipo
        int usuario_id FK
    }

    REGISTRO_MORTALIDAD {
        int id PK
        int lote_gallinas_id FK
        int usuario_id FK
    }

    VENTA_GALLINAS {
        int id PK
        int lote_gallinas_id FK
        int usuario_id FK
    }

    REGISTRO_SANITARIO {
        int id PK
        int lote_gallinas_id FK
        int usuario_id FK
    }

    SEPARACION_GALLINAS {
        int id PK
        int lote_gallinas_id FK
        int usuario_id FK
    }

    CLIENTE {
        int id PK
        string nombre
        string apellido
    }

    VENTA {
        int id PK
        string numero_venta
        int cliente_id FK
        int vendedor_id FK
    }

    DETALLE_VENTA {
        int id PK
        int venta_id FK
        int categoria_id FK
    }

    PAGO {
        int id PK
        int venta_id FK
        int cliente_id FK
        int usuario_id FK
    }

    CONFIGURACION_VENTA {
        int id PK
        string clave
        int modificado_por FK
    }

    USER ||--o{ USER_ROLES : tiene
    ROLE ||--o{ USER_ROLES : asigna

    ROLE ||--o{ ROLE_PERMISSIONS : tiene
    PERMISSION ||--o{ ROLE_PERMISSIONS : asigna

    USER ||--o{ LOTE_RECOLECCION : registra
    LOTE_GALLINAS ||--o{ LOTE_RECOLECCION : alimenta
    PESA ||--o{ LOTE_RECOLECCION : usa

    LOTE_RECOLECCION ||--o{ HUEVO : contiene
    CATEGORIA_HUEVO ||--o{ HUEVO : clasifica
    CATEGORIA_HUEVO ||--o{ INVENTARIO_HUEVOS : consolida

    USER ||--o{ GASTO : registra

    USER ||--o{ LOTE_GALLINAS : crea
    LOTE_GALLINAS ||--o{ REGISTRO_MORTALIDAD : tiene
    LOTE_GALLINAS ||--o{ VENTA_GALLINAS : tiene
    LOTE_GALLINAS ||--o{ REGISTRO_SANITARIO : tiene
    LOTE_GALLINAS ||--o{ SEPARACION_GALLINAS : tiene

    USER ||--o{ REGISTRO_MORTALIDAD : registra
    USER ||--o{ VENTA_GALLINAS : registra
    USER ||--o{ REGISTRO_SANITARIO : registra
    USER ||--o{ SEPARACION_GALLINAS : registra

    CLIENTE ||--o{ VENTA : compra
    USER ||--o{ VENTA : vende
    VENTA ||--o{ DETALLE_VENTA : detalle
    CATEGORIA_HUEVO ||--o{ DETALLE_VENTA : producto

    VENTA ||--o{ PAGO : recibe
    CLIENTE ||--o{ PAGO : paga
    USER ||--o{ PAGO : registra

    USER ||--o{ CONFIGURACION_VENTA : modifica
```

## 12) Seguridad Operativa

- No subir `.env` al repositorio.
- Forzar HTTPS.
- Cambiar credenciales por defecto inmediatamente.
- Restringir permisos MySQL al minimo necesario.
- Aplicar actualizaciones de dependencias de forma periodica.

## 13) Checklist de Salida a Produccion

- [ ] Dominio/subdominio con SSL activo.
- [ ] Python App creada y funcionando.
- [ ] Dependencias instaladas sin errores.
- [ ] Variables de entorno configuradas.
- [ ] Migraciones aplicadas (`flask db upgrade`).
- [ ] Usuario admin seguro y sin claves por defecto.
- [ ] Backups configurados y probados.
- [ ] Pruebas funcionales en inventario, ventas, gallinas, usuarios y permisos.
