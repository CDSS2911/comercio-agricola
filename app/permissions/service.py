from flask import flash, redirect, request, url_for
from flask_login import current_user

from app import db
from app.models import Permission
from app.permissions.rutas import ENDPOINT_PERMISSIONS, PERMISSION_DEFINITIONS


def required_permission_for_endpoint(endpoint):
    if not endpoint:
        return None
    return ENDPOINT_PERMISSIONS.get(endpoint)


def can_access_endpoint(endpoint):
    required = required_permission_for_endpoint(endpoint)
    if not required:
        return True
    if not current_user.is_authenticated:
        return False
    if isinstance(required, (list, tuple, set)):
        return any(current_user.has_permission(code) for code in required)
    return current_user.has_permission(required)


def resolve_home_endpoint():
    """Determina una pagina inicial valida segun permisos del usuario."""
    candidates = [
        'inventario.dashboard',
        'ventas.ventas_dashboard',
        'gallinas.dashboard',
        'main.index',
    ]
    for endpoint in candidates:
        if can_access_endpoint(endpoint):
            return endpoint
    return 'main.index'


def enforce_permission_by_endpoint():
    """Guard global: aplica permisos segun endpoint configurado en rutas.py."""
    endpoint = request.endpoint or ''
    if not endpoint:
        return None
    if endpoint.startswith('static'):
        return None

    required = required_permission_for_endpoint(endpoint)
    if not required:
        return None

    if not current_user.is_authenticated:
        return redirect(url_for('auth.login', next=request.path))

    allowed = can_access_endpoint(endpoint)
    if allowed:
        return None

    flash('No tienes permisos para acceder a esta ruta', 'error')
    home_endpoint = resolve_home_endpoint()
    if home_endpoint == endpoint:
        home_endpoint = 'main.index'
    return redirect(url_for(home_endpoint))


def sync_defined_permissions():
    """Crea/actualiza permisos definidos en rutas.py sin tocar codigo de rutas."""
    changed = False
    existing = {p.code: p for p in Permission.query.all()}

    for code, (name, module, description) in PERMISSION_DEFINITIONS.items():
        perm = existing.get(code)
        if perm is None:
            db.session.add(
                Permission(
                    code=code,
                    name=name,
                    module=module,
                    description=description,
                    active=True,
                )
            )
            changed = True
            continue

        if perm.name != name or perm.module != module or (perm.description or '') != description:
            perm.name = name
            perm.module = module
            perm.description = description
            changed = True

    if changed:
        db.session.commit()
