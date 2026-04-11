from datetime import datetime
import re
import secrets
import string
from functools import wraps

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from flask_wtf.csrf import generate_csrf
from sqlalchemy import extract, or_
from werkzeug.security import check_password_hash, generate_password_hash

from app import db
from app.forms import UserProfileForm
from app.models import Permission, Role, User
from app.permissions.rutas import PERMISSION_DEFINITIONS, SYSTEM_ROLE_PERMISSIONS
from app.utils.email import send_confirmation_email

usuarios_bp = Blueprint('usuarios', __name__, url_prefix='/usuarios')


def permission_required(permission_code):
    """Decorador para verificar permisos RBAC."""

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated or not current_user.has_permission(permission_code):
                flash('No tienes permisos para acceder a esta pagina', 'error')
                return redirect(url_for('main.dashboard'))
            return f(*args, **kwargs)

        return decorated_function

    return decorator


def ensure_rbac_seed():
    """Asegura roles y permisos base en entornos legacy."""
    changed = False

    base_permissions = [
        (code, meta[0], meta[1], meta[2])
        for code, meta in PERMISSION_DEFINITIONS.items()
    ]

    existing_permissions = {p.code: p for p in Permission.query.all()}
    for code, name, module, description in base_permissions:
        if code not in existing_permissions:
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

    db.session.flush()

    existing_roles = {r.slug: r for r in Role.query.all()}

    if 'superadmin' not in existing_roles:
        db.session.add(
            Role(
                slug='superadmin',
                name='Superadmin',
                description='Control total del sistema',
                active=True,
                is_system=True,
            )
        )
        changed = True

    if 'admin' not in existing_roles:
        db.session.add(
            Role(
                slug='admin',
                name='Admin',
                description='Admin sin crear usuarios ni contrasenas',
                active=True,
                is_system=True,
            )
        )
        changed = True

    if 'operador' not in existing_roles:
        db.session.add(
            Role(
                slug='operador',
                name='Operador',
                description='Inventario huevos, vender y novedades aves',
                active=True,
                is_system=True,
            )
        )
        changed = True

    db.session.flush()

    role_permissions_map = SYSTEM_ROLE_PERMISSIONS

    permissions_by_code = {p.code: p for p in Permission.query.all()}
    roles_by_slug = {r.slug: r for r in Role.query.all()}

    for role_slug, permission_codes in role_permissions_map.items():
        role = roles_by_slug.get(role_slug)
        if role is None:
            continue

        current_codes = {p.code for p in role.permissions}
        desired_codes = set(permission_codes)
        if desired_codes - current_codes:
            role.permissions = [permissions_by_code[c] for c in permission_codes if c in permissions_by_code]
            changed = True

    if changed:
        db.session.commit()


def parse_checkbox(value):
    return str(value).lower() in {'1', 'true', 'on', 'yes'}


def _build_gestion_context(estado_filter='', rol_filter='', buscar_filter=''):
    """Construir contexto compartido para la vista de gestion de usuarios."""
    query = User.query

    if estado_filter == 'activo':
        query = query.filter(User.is_active.is_(True))
    elif estado_filter == 'inactivo':
        query = query.filter(User.is_active.is_(False))

    if rol_filter:
        if rol_filter == 'sin_rol':
            query = query.filter(~User.roles.any())
        else:
            query = query.filter(User.roles.any(Role.slug == rol_filter))

    if buscar_filter:
        search_term = f"%{buscar_filter}%"
        query = query.filter(
            or_(
                User.first_name.ilike(search_term),
                User.last_name.ilike(search_term),
                User.username.ilike(search_term),
                User.email.ilike(search_term),
            )
        )

    usuarios = query.order_by(User.created_at.desc()).all()
    roles_activos = Role.query.filter_by(active=True).order_by(Role.name.asc()).all()

    stats = {
        'total_usuarios': User.query.count(),
        'usuarios_activos': User.query.filter(User.is_active.is_(True)).count(),
        'administradores': User.query.filter(
            or_(
                User.roles.any(Role.slug == 'admin'),
                User.roles.any(Role.slug == 'superadmin'),
                User.is_admin.is_(True),
            )
        ).count(),
        'nuevos_mes': User.query.filter(
            extract('month', User.created_at) == datetime.now().month,
            extract('year', User.created_at) == datetime.now().year,
        ).count(),
    }

    return {
        'usuarios': usuarios,
        'stats': stats,
        'roles': roles_activos,
        'can_create': current_user.has_permission('users.create'),
        'can_edit': current_user.has_permission('users.edit'),
        'can_toggle': current_user.has_permission('users.toggle_active'),
        'can_reset': current_user.has_permission('users.reset_password'),
        'can_assign_roles': current_user.has_permission('users.assign_roles'),
        'can_manage_roles': current_user.has_permission('roles.manage'),
        'csrf_token': generate_csrf,
        'estado_filter': estado_filter,
        'rol_filter': rol_filter,
        'buscar_filter': buscar_filter,
    }


def validar_password(password):
    """Validar que la contrasena cumple con los requisitos minimos."""
    if len(password) < 8:
        return False
    if not re.search(r'[A-Z]', password):
        return False
    if not re.search(r'[a-z]', password):
        return False
    if not re.search(r'\d', password):
        return False
    if not re.match(r'^[a-zA-Z\d@$!%*?&._-]+$', password):
        return False
    return True


@usuarios_bp.route('/perfil', methods=['GET', 'POST'])
@login_required
def perfil():
    """Vista para que el usuario edite su perfil."""
    form = UserProfileForm(obj=current_user)

    if form.validate_on_submit():
        try:
            if form.username.data != current_user.username:
                existing_user = User.query.filter(
                    User.username == form.username.data,
                    User.id != current_user.id,
                ).first()
                if existing_user:
                    flash('El nombre de usuario ya esta en uso', 'error')
                    return render_template('usuarios/perfil.html', form=form)

            if form.email.data != current_user.email:
                existing_email = User.query.filter(
                    User.email == form.email.data,
                    User.id != current_user.id,
                ).first()
                if existing_email:
                    flash('El email ya esta registrado', 'error')
                    return render_template('usuarios/perfil.html', form=form)

                current_user.email_confirmed = False

            current_user.nombre = form.nombre.data
            current_user.apellido = form.apellido.data
            current_user.username = form.username.data
            current_user.email = form.email.data
            current_user.telefono = form.telefono.data
            current_user.fecha_nacimiento = form.fecha_nacimiento.data
            current_user.direccion = form.direccion.data
            current_user.tipo_identificacion = form.tipo_identificacion.data
            current_user.numero_identificacion = form.numero_identificacion.data

            db.session.commit()
            flash('Tu perfil ha sido actualizado correctamente', 'success')
            return redirect(url_for('usuarios.perfil'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar el perfil: {str(e)}', 'error')

    return render_template('usuarios/perfil.html', form=form)


@usuarios_bp.route('/cambiar-password', methods=['POST'])
@login_required
def cambiar_password():
    """Cambiar contrasena del usuario."""
    password_actual = request.form.get('password_actual')
    nueva_password = request.form.get('nueva_password')
    confirmar_password = request.form.get('confirmar_password')

    if not password_actual or not nueva_password or not confirmar_password:
        flash('Todos los campos son obligatorios', 'error')
        return redirect(url_for('usuarios.perfil'))

    if not check_password_hash(current_user.password_hash, password_actual):
        flash('La contrasena actual es incorrecta', 'error')
        return redirect(url_for('usuarios.perfil'))

    if nueva_password != confirmar_password:
        flash('Las nuevas contrasenas no coinciden', 'error')
        return redirect(url_for('usuarios.perfil'))

    if not validar_password(nueva_password):
        flash('La nueva contrasena debe tener minimo 8 caracteres, mayuscula, minuscula y numero', 'error')
        return redirect(url_for('usuarios.perfil'))

    try:
        current_user.password_hash = generate_password_hash(nueva_password)
        db.session.commit()
        flash('Tu contrasena ha sido cambiada correctamente', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al cambiar la contrasena: {str(e)}', 'error')

    return redirect(url_for('usuarios.perfil'))


@usuarios_bp.route('/reenviar-confirmacion', methods=['POST'])
@login_required
def reenviar_confirmacion():
    """Reenviar email de confirmacion."""
    try:
        if current_user.email_confirmed:
            return jsonify({'success': False, 'message': 'Tu email ya esta confirmado'})
        
        sent = send_confirmation_email(current_user)
        if sent:
            return jsonify({'success': True, 'message': 'Email de confirmacion enviado correctamente'})
        return jsonify({'success': False, 'message': 'No se pudo enviar el email. Verifica configuracion SMTP y credenciales.'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error al enviar el email: {str(e)}'})


# =============================================================================
# RUTAS ADMINISTRATIVAS DE GESTION DE USUARIOS
# =============================================================================


@usuarios_bp.route('/gestion')
@login_required
@permission_required('users.view')
def gestion():
    """Vista principal de gestion de usuarios para administradores."""
    ensure_rbac_seed()

    estado_filter = request.args.get('estado', '')
    rol_filter = request.args.get('rol', '')
    buscar_filter = request.args.get('buscar', '')

    return render_template('usuarios/gestion.html', **_build_gestion_context(estado_filter, rol_filter, buscar_filter))


@usuarios_bp.route('/gestion', methods=['POST'])
@login_required
@permission_required('users.edit')
def gestionar_usuario():
    """Crear o actualizar un usuario."""
    ensure_rbac_seed()

    try:
        data = request.form
        user_id = data.get('id')
        es_edicion = bool(user_id)
        form_data = data.to_dict(flat=True)
        form_errors = {}

        def add_error(field, message):
            form_errors.setdefault(field, []).append(message)

        if not es_edicion and not current_user.has_permission('users.create'):
            flash('No tienes permisos para crear usuarios', 'error')
            return redirect(url_for('usuarios.gestion'))

        campos_requeridos = ['nombre', 'apellido', 'username', 'email']
        if not es_edicion:
            campos_requeridos.append('password')

        for campo in campos_requeridos:
            if not data.get(campo):
                add_error(campo, 'Este campo es obligatorio')

        usuario = None

        if es_edicion:
            usuario = User.query.get_or_404(user_id)
            existing_user = User.query.filter(
                User.username == data.get('username'),
                User.id != user_id,
            ).first()
            if existing_user:
                add_error('username', 'El nombre de usuario ya esta en uso')

            existing_email = User.query.filter(
                User.email == data.get('email'),
                User.id != user_id,
            ).first()
            if existing_email:
                add_error('email', 'El email ya esta registrado')
        else:
            if User.query.filter_by(username=data.get('username')).first():
                add_error('username', 'El nombre de usuario ya esta en uso')

            if User.query.filter_by(email=data.get('email')).first():
                add_error('email', 'El email ya esta registrado')

            usuario = User()

        if data.get('password'):
            if not current_user.has_permission('users.reset_password'):
                add_error('password', 'No tienes permisos para asignar o cambiar contrasenas')
            if not validar_password(data.get('password')):
                add_error('password', 'La contrasena no cumple con los requisitos minimos')

        usuario.nombre = data.get('nombre')
        usuario.apellido = data.get('apellido')
        usuario.username = data.get('username')
        usuario.email = data.get('email')
        usuario.telefono = data.get('telefono') or None
        usuario.direccion = data.get('direccion') or None
        usuario.tipo_identificacion = data.get('tipo_identificacion') or None
        usuario.numero_identificacion = data.get('numero_identificacion') or None
        usuario.is_active = parse_checkbox(data.get('is_active', 'on'))

        if not es_edicion:
            usuario.email_confirmed = True

        fecha_nacimiento = data.get('fecha_nacimiento')
        if fecha_nacimiento:
            try:
                usuario.fecha_nacimiento = datetime.strptime(fecha_nacimiento, '%Y-%m-%d').date()
            except ValueError:
                usuario.fecha_nacimiento = None
        else:
            usuario.fecha_nacimiento = None

        role_id = data.get('role_id')
        if role_id:
            role = Role.query.filter_by(id=role_id, active=True).first()
            if not role:
                add_error('role_id', 'El rol seleccionado no es valido')

            if not current_user.has_permission('users.assign_roles'):
                add_error('role_id', 'No tienes permisos para asignar roles')

            if role and current_user.has_permission('users.assign_roles'):
                usuario.set_single_role(role)
        elif not es_edicion:
            add_error('role_id', 'Debes seleccionar un rol para el nuevo usuario')

        if form_errors:
            flash('Corrige los errores del formulario y vuelve a intentarlo', 'error')
            return render_template(
                'usuarios/gestion.html',
                **_build_gestion_context(),
                form_data=form_data,
                form_errors=form_errors,
                open_user_modal=True,
            )

        if data.get('password'):
            usuario.set_password(data.get('password'))

        if not es_edicion:
            db.session.add(usuario)

        db.session.commit()

        accion = 'actualizado' if es_edicion else 'creado'
        flash(f'Usuario {usuario.username} {accion} correctamente', 'success')
        return redirect(url_for('usuarios.gestion'))

    except Exception as e:
        db.session.rollback()
        flash(f'Error al procesar el usuario: {str(e)}', 'error')
        return render_template(
            'usuarios/gestion.html',
            **_build_gestion_context(),
            form_data=request.form.to_dict(flat=True),
            open_user_modal=True,
        )


@usuarios_bp.route('/editar/<int:user_id>')
@login_required
@permission_required('users.view')
def obtener_usuario(user_id):
    """Obtener datos de un usuario para edicion."""
    try:
        usuario = User.query.get_or_404(user_id)
        primary_role = usuario.get_primary_role()

        return jsonify(
            {
                'success': True,
                'usuario': {
                    'id': usuario.id,
                    'nombre': usuario.nombre or '',
                    'apellido': usuario.apellido or '',
                    'username': usuario.username,
                    'email': usuario.email,
                    'telefono': usuario.telefono or '',
                    'fecha_nacimiento': usuario.fecha_nacimiento.isoformat() if usuario.fecha_nacimiento else '',
                    'direccion': usuario.direccion or '',
                    'tipo_identificacion': usuario.tipo_identificacion or '',
                    'numero_identificacion': usuario.numero_identificacion or '',
                    'is_active': usuario.is_active,
                    'role_id': primary_role.id if primary_role else None,
                    'role_name': primary_role.name if primary_role else 'Sin rol',
                },
            }
        )
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error al obtener el usuario: {str(e)}'})


@usuarios_bp.route('/ver/<int:user_id>')
@login_required
@permission_required('users.view')
def ver_usuario(user_id):
    """Ver detalles completos de un usuario."""
    try:
        usuario = User.query.get_or_404(user_id)

        role_badges = ''.join(
            [f'<span class="badge bg-primary me-1">{r.name}</span>' for r in sorted(usuario.roles, key=lambda x: x.id)]
        )
        if not role_badges:
            role_badges = '<span class="badge bg-secondary">Sin rol</span>'

        html = f"""
        <div class="row">
            <div class="col-md-6">
                <h6>Informacion Personal</h6>
                <p><strong>Nombre completo:</strong> {usuario.get_full_name()}</p>
                <p><strong>Username:</strong> {usuario.username}</p>
                <p><strong>Email:</strong> {usuario.email}</p>
                <p><strong>Telefono:</strong> {usuario.telefono or 'No especificado'}</p>
                <p><strong>Fecha de nacimiento:</strong> {usuario.fecha_nacimiento.strftime('%d/%m/%Y') if usuario.fecha_nacimiento else 'No especificada'}</p>
                <p><strong>Direccion:</strong> {usuario.direccion or 'No especificada'}</p>
            </div>
            <div class="col-md-6">
                <h6>Identificacion</h6>
                <p><strong>Tipo:</strong> {dict([('CC', 'Cedula de Ciudadania'), ('CE', 'Cedula de Extranjeria'), ('TI', 'Tarjeta de Identidad'), ('PP', 'Pasaporte'), ('NIT', 'NIT'), ('RC', 'Registro Civil')]).get(usuario.tipo_identificacion, 'No especificado')}</p>
                <p><strong>Numero:</strong> {usuario.numero_identificacion or 'No especificado'}</p>

                <h6 class="mt-3">Estado y Roles</h6>
                <p><strong>Estado:</strong> {'<span class="badge bg-success">Activo</span>' if usuario.is_active else '<span class="badge bg-danger">Inactivo</span>'}</p>
                <p><strong>Email confirmado:</strong> {'<span class="badge bg-success">Si</span>' if usuario.email_confirmed else '<span class="badge bg-warning">No</span>'}</p>
                <p><strong>Rol:</strong><br>{role_badges}</p>
            </div>
        </div>
        <div class="row mt-3">
            <div class="col-12">
                <h6>Informacion del Sistema</h6>
                <p><strong>Fecha de registro:</strong> {usuario.created_at.strftime('%d/%m/%Y %H:%M')}</p>
                <p><strong>Ultimo acceso:</strong> {usuario.last_login.strftime('%d/%m/%Y %H:%M') if usuario.last_login else 'Nunca'}</p>
                <p><strong>ID del usuario:</strong> {usuario.id}</p>
            </div>
        </div>
        """

        return jsonify({'success': True, 'html': html})

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error al obtener los detalles: {str(e)}'})


@usuarios_bp.route('/cambiar-estado/<int:user_id>', methods=['POST'])
@login_required
@permission_required('users.toggle_active')
def cambiar_estado_usuario(user_id):
    """Cambiar el estado activo/inactivo de un usuario."""
    try:
        usuario = User.query.get_or_404(user_id)
        data = request.get_json() or {}

        if usuario.id == current_user.id:
            return jsonify({'success': False, 'message': 'No puedes cambiar tu propio estado'})

        usuario.is_active = bool(data.get('activo', True))
        db.session.commit()

        estado_texto = 'activado' if usuario.is_active else 'desactivado'
        flash(f'Usuario {usuario.username} {estado_texto} correctamente', 'success')
        return jsonify({'success': True, 'message': f'Usuario {estado_texto} correctamente'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error al cambiar el estado: {str(e)}'})


@usuarios_bp.route('/reset-password/<int:user_id>', methods=['POST'])
@login_required
@permission_required('users.reset_password')
def reset_password(user_id):
    """Generar una nueva contrasena temporal para un usuario."""
    try:
        usuario = User.query.get_or_404(user_id)

        if usuario.id == current_user.id:
            return jsonify({'success': False, 'message': 'No puedes resetear tu propia contrasena'})

        caracteres = string.ascii_letters + string.digits + '!@#$%'
        nueva_password = ''.join(secrets.choice(caracteres) for _ in range(12))
        nueva_password = nueva_password[:8] + 'A1!' + nueva_password[8:]

        usuario.set_password(nueva_password)
        db.session.commit()

        return jsonify(
            {
                'success': True,
                'new_password': nueva_password,
                'message': 'Contrasena restablecida correctamente',
            }
        )

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error al restablecer la contrasena: {str(e)}'})


@usuarios_bp.route('/roles-permisos')
@login_required
@permission_required('roles.manage')
def roles_permisos():
    """Pantalla de CRUD de roles y permisos."""
    ensure_rbac_seed()

    roles = Role.query.order_by(Role.is_system.desc(), Role.name.asc()).all()
    permissions = Permission.query.order_by(Permission.module.asc(), Permission.code.asc()).all()

    return render_template(
        'usuarios/roles_permisos.html',
        roles=roles,
        permissions=permissions,
        csrf_token=generate_csrf,
    )


@usuarios_bp.route('/roles', methods=['POST'])
@login_required
@permission_required('roles.manage')
def guardar_rol():
    """Crear o editar rol y su set de permisos."""
    try:
        role_id = request.form.get('id')
        slug = (request.form.get('slug') or '').strip().lower()
        name = (request.form.get('name') or '').strip()
        description = (request.form.get('description') or '').strip() or None
        active = parse_checkbox(request.form.get('active', 'on'))
        permission_ids = request.form.getlist('permission_ids')

        if not slug or not name:
            flash('Slug y nombre son obligatorios', 'error')
            return redirect(url_for('usuarios.roles_permisos'))

        if role_id:
            role = Role.query.get_or_404(role_id)
            if role.is_system and role.slug != slug:
                flash('No puedes cambiar el slug de un rol del sistema', 'error')
                return redirect(url_for('usuarios.roles_permisos'))

            existing = Role.query.filter(Role.slug == slug, Role.id != role.id).first()
            if existing:
                flash('Ya existe un rol con ese slug', 'error')
                return redirect(url_for('usuarios.roles_permisos'))
        else:
            if Role.query.filter_by(slug=slug).first():
                flash('Ya existe un rol con ese slug', 'error')
                return redirect(url_for('usuarios.roles_permisos'))
            role = Role(is_system=False)

        role.slug = slug
        role.name = name
        role.description = description
        role.active = active

        selected_permissions = []
        for pid in permission_ids:
            permission = Permission.query.get(pid)
            if permission:
                selected_permissions.append(permission)
        role.permissions = selected_permissions

        if not role_id:
            db.session.add(role)

        db.session.commit()
        flash('Rol guardado correctamente', 'success')
        return redirect(url_for('usuarios.roles_permisos'))

    except Exception as e:
        db.session.rollback()
        flash(f'Error al guardar rol: {str(e)}', 'error')
        return redirect(url_for('usuarios.roles_permisos'))


@usuarios_bp.route('/roles/<int:role_id>/delete', methods=['POST'])
@login_required
@permission_required('roles.manage')
def eliminar_rol(role_id):
    """Eliminar rol no sistemico sin usuarios asignados."""
    try:
        role = Role.query.get_or_404(role_id)

        if role.is_system:
            flash('No puedes eliminar roles del sistema', 'error')
            return redirect(url_for('usuarios.roles_permisos'))

        if role.users:
            flash('No puedes eliminar un rol que tiene usuarios asignados', 'error')
            return redirect(url_for('usuarios.roles_permisos'))

        db.session.delete(role)
        db.session.commit()
        flash('Rol eliminado correctamente', 'success')
        return redirect(url_for('usuarios.roles_permisos'))

    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar rol: {str(e)}', 'error')
        return redirect(url_for('usuarios.roles_permisos'))


@usuarios_bp.route('/permissions', methods=['POST'])
@login_required
@permission_required('permissions.manage')
def guardar_permiso():
    """Crear o editar permisos."""
    try:
        permission_id = request.form.get('id')
        code = (request.form.get('code') or '').strip().lower()
        name = (request.form.get('name') or '').strip()
        module = (request.form.get('module') or '').strip().lower()
        description = (request.form.get('description') or '').strip() or None
        active = parse_checkbox(request.form.get('active', 'on'))

        if not code or not name or not module:
            flash('Codigo, nombre y modulo son obligatorios', 'error')
            return redirect(url_for('usuarios.roles_permisos'))

        if permission_id:
            permission = Permission.query.get_or_404(permission_id)
            existing = Permission.query.filter(Permission.code == code, Permission.id != permission.id).first()
            if existing:
                flash('Ya existe un permiso con ese codigo', 'error')
                return redirect(url_for('usuarios.roles_permisos'))
        else:
            if Permission.query.filter_by(code=code).first():
                flash('Ya existe un permiso con ese codigo', 'error')
                return redirect(url_for('usuarios.roles_permisos'))
            permission = Permission()

        permission.code = code
        permission.name = name
        permission.module = module
        permission.description = description
        permission.active = active

        if not permission_id:
            db.session.add(permission)

        db.session.commit()
        flash('Permiso guardado correctamente', 'success')
        return redirect(url_for('usuarios.roles_permisos'))

    except Exception as e:
        db.session.rollback()
        flash(f'Error al guardar permiso: {str(e)}', 'error')
        return redirect(url_for('usuarios.roles_permisos'))


@usuarios_bp.route('/permissions/<int:permission_id>/delete', methods=['POST'])
@login_required
@permission_required('permissions.manage')
def eliminar_permiso(permission_id):
    """Eliminar permiso si no esta asignado a roles."""
    try:
        permission = Permission.query.get_or_404(permission_id)

        if permission.roles:
            flash('No puedes eliminar un permiso que esta asignado a roles', 'error')
            return redirect(url_for('usuarios.roles_permisos'))

        db.session.delete(permission)
        db.session.commit()
        flash('Permiso eliminado correctamente', 'success')
        return redirect(url_for('usuarios.roles_permisos'))

    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar permiso: {str(e)}', 'error')
        return redirect(url_for('usuarios.roles_permisos'))
