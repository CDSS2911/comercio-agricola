from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import User, LoginAttempt
from app.forms import EditUserForm
from functools import wraps

bp = Blueprint('admin', __name__)


def admin_required(f):
    """Decorador para requerir permisos de administrador"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Acceso denegado. Necesitas permisos de administrador.', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function


@bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    """Panel de administración"""
    total_users = User.query.count()
    active_users = User.query.filter_by(is_active=True).count()
    recent_logins = LoginAttempt.query.filter_by(successful=True).order_by(
        LoginAttempt.timestamp.desc()
    ).limit(10).all()
    
    return render_template('admin/dashboard.html', 
                         title='Panel de Administración',
                         total_users=total_users,
                         active_users=active_users,
                         recent_logins=recent_logins)


@bp.route('/users')
@bp.route('/users/<int:page>')
@login_required
@admin_required
def users(page=1):
    """Lista de usuarios"""
    users = User.query.paginate(
        page=page, per_page=10, error_out=False
    )
    return render_template('admin/users.html', title='Gestión de Usuarios', users=users)


@bp.route('/user/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(id):
    """Editar usuario"""
    user = User.query.get_or_404(id)
    form = EditUserForm(user.username, user.email, obj=user)
    
    if form.validate_on_submit():
        user.username = form.username.data
        user.email = form.email.data
        user.first_name = form.first_name.data
        user.last_name = form.last_name.data
        user.is_active = form.is_active.data
        user.is_admin = form.is_admin.data
        db.session.commit()
        flash(f'Usuario {user.username} actualizado correctamente.', 'success')
        return redirect(url_for('admin.users'))
    
    return render_template('admin/edit_user.html', title='Editar Usuario', form=form, user=user)


@bp.route('/user/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(id):
    """Eliminar usuario"""
    user = User.query.get_or_404(id)
    if user.id == current_user.id:
        flash('No puedes eliminar tu propia cuenta.', 'error')
        return redirect(url_for('admin.users'))
    
    db.session.delete(user)
    db.session.commit()
    flash(f'Usuario {user.username} eliminado correctamente.', 'success')
    return redirect(url_for('admin.users'))


@bp.route('/security')
@login_required
@admin_required
def security():
    """Registro de intentos de login"""
    page = request.args.get('page', 1, type=int)
    attempts = LoginAttempt.query.order_by(
        LoginAttempt.timestamp.desc()
    ).paginate(
        page=page, per_page=20, error_out=False
    )
    return render_template('admin/security.html', 
                         title='Seguridad - Intentos de Login', 
                         attempts=attempts)