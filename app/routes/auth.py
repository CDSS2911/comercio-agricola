from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.urls import url_parse
from app import db
from app.models import User, LoginAttempt
from app.forms import LoginForm, RegistrationForm, RequestResetForm, ResetPasswordForm
from app.utils.email import send_password_reset_email, send_confirmation_email

bp = Blueprint('auth', __name__)


@bp.route('/login', methods=['GET', 'POST'])
def login():
    """Página de inicio de sesión"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        # Buscar usuario por username o email
        user = User.query.filter(
            (User.username == form.username.data) | 
            (User.email == form.username.data)
        ).first()
        
        # Registrar intento de login
        login_attempt = LoginAttempt(
            ip_address=request.environ.get('REMOTE_ADDR', 'unknown'),
            username_attempted=form.username.data,
            successful=False,
            user_agent=request.headers.get('User-Agent')
        )
        
        if user is None or not user.check_password(form.password.data):
            db.session.add(login_attempt)
            db.session.commit()
            flash('Usuario o contraseña incorrectos', 'error')
            return redirect(url_for('auth.login'))
        
        if not user.is_active:
            db.session.add(login_attempt)
            db.session.commit()
            flash('Tu cuenta está desactivada. Contacta al administrador.', 'error')
            return redirect(url_for('auth.login'))
        
        # Login exitoso
        login_attempt.successful = True
        user.last_login = datetime.utcnow()
        db.session.add(login_attempt)
        db.session.add(user)
        db.session.commit()
        
        login_user(user, remember=form.remember_me.data)
        
        # Redireccionar a la pagina solicitada o a la mejor pagina segun permisos
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            from app.permissions.service import resolve_home_endpoint
            next_page = url_for(resolve_home_endpoint())
        return redirect(next_page)
    
    return render_template('auth/login.html', title='Iniciar Sesión', form=form)


@bp.route('/logout')
@login_required
def logout():
    """Cerrar sesión"""
    logout_user()
    flash('Has cerrado sesión correctamente.', 'success')
    return redirect(url_for('main.index'))


@bp.route('/register', methods=['GET', 'POST'])
def register():
    """Página de registro de usuarios"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            email=form.email.data,
            first_name=form.first_name.data,
            last_name=form.last_name.data
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        
        # Enviar email de confirmación
        send_confirmation_email(user)
        
        flash('¡Registro exitoso! Revisa tu email para confirmar tu cuenta.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html', title='Registro', form=form)


@bp.route('/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    """Solicitar recuperación de contraseña"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    form = RequestResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            send_password_reset_email(user)
        flash('Revisa tu email para las instrucciones de recuperación de contraseña', 'info')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/reset_password_request.html', title='Recuperar Contraseña', form=form)


@bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Restablecer contraseña usando token"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    user = User.verify_reset_token(token)
    if not user:
        flash('Token inválido o expirado', 'error')
        return redirect(url_for('auth.reset_password_request'))
    
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash('Tu contraseña ha sido actualizada.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/reset_password.html', form=form)


@bp.route('/confirm/<token>')
def confirm_email(token):
    """Confirmar email usando token"""
    if current_user.is_authenticated and current_user.email_confirmed:
        return redirect(url_for('main.dashboard'))
    
    user = User.query.filter_by(id=current_user.id if current_user.is_authenticated else None).first()
    if user and user.confirm_email(token):
        db.session.commit()
        flash('¡Tu email ha sido confirmado!', 'success')
    else:
        flash('El enlace de confirmación es inválido o ha expirado.', 'error')
    
    return redirect(url_for('main.index'))
