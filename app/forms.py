from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, SelectField, TextAreaField, DateField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError, Optional
from app.models import User


class LoginForm(FlaskForm):
    username = StringField('Usuario o Email', validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField('Contraseña', validators=[DataRequired()])
    remember_me = BooleanField('Recordarme')
    submit = SubmitField('Iniciar Sesión')


class RegistrationForm(FlaskForm):
    username = StringField('Nombre de Usuario', validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    first_name = StringField('Nombre', validators=[DataRequired(), Length(min=2, max=100)])
    last_name = StringField('Apellido', validators=[DataRequired(), Length(min=2, max=100)])
    password = PasswordField('Contraseña', validators=[DataRequired(), Length(min=6)])
    password2 = PasswordField('Repetir Contraseña', validators=[
        DataRequired(), EqualTo('password', message='Las contraseñas deben coincidir')
    ])
    submit = SubmitField('Registrarse')
    
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Este nombre de usuario ya está en uso.')
    
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Este email ya está registrado.')


class RequestResetForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Solicitar Recuperación')
    
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user is None:
            raise ValidationError('No existe una cuenta con este email.')


class ResetPasswordForm(FlaskForm):
    password = PasswordField('Nueva Contraseña', validators=[DataRequired(), Length(min=6)])
    password2 = PasswordField('Repetir Contraseña', validators=[
        DataRequired(), EqualTo('password', message='Las contraseñas deben coincidir')
    ])
    submit = SubmitField('Cambiar Contraseña')


class EditUserForm(FlaskForm):
    username = StringField('Nombre de Usuario', validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    first_name = StringField('Nombre', validators=[DataRequired(), Length(min=2, max=100)])
    last_name = StringField('Apellido', validators=[DataRequired(), Length(min=2, max=100)])
    is_active = BooleanField('Usuario Activo')
    is_admin = BooleanField('Administrador')
    submit = SubmitField('Actualizar Usuario')
    
    def __init__(self, original_username, original_email, *args, **kwargs):
        super(EditUserForm, self).__init__(*args, **kwargs)
        self.original_username = original_username
        self.original_email = original_email
    
    def validate_username(self, username):
        if username.data != self.original_username:
            user = User.query.filter_by(username=username.data).first()
            if user:
                raise ValidationError('Este nombre de usuario ya está en uso.')
    
    def validate_email(self, email):
        if email.data != self.original_email:
            user = User.query.filter_by(email=email.data).first()
            if user:
                raise ValidationError('Este email ya está registrado.')


class UserProfileForm(FlaskForm):
    """Formulario para que el usuario edite su perfil"""
    nombre = StringField('Nombre', validators=[DataRequired(), Length(min=2, max=100)])
    apellido = StringField('Apellido', validators=[DataRequired(), Length(min=2, max=100)])
    username = StringField('Nombre de Usuario', validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    telefono = StringField('Teléfono', validators=[Optional(), Length(max=20)])
    fecha_nacimiento = DateField('Fecha de Nacimiento', validators=[Optional()])
    direccion = TextAreaField('Dirección', validators=[Optional(), Length(max=500)])
    
    # Campos de identificación
    tipo_identificacion = SelectField('Tipo de Identificación', 
                                    choices=[
                                        ('', 'Seleccionar...'),
                                        ('CC', 'Cédula de Ciudadanía'),
                                        ('CE', 'Cédula de Extranjería'),
                                        ('TI', 'Tarjeta de Identidad'),
                                        ('PP', 'Pasaporte'),
                                        ('NIT', 'NIT'),
                                        ('RC', 'Registro Civil')
                                    ], 
                                    validators=[Optional()])
    numero_identificacion = StringField('Número de Identificación', 
                                      validators=[Optional(), Length(max=20)])
    
    submit = SubmitField('Actualizar Perfil')


class ChangePasswordForm(FlaskForm):
    """Formulario para cambiar contraseña"""
    password_actual = PasswordField('Contraseña Actual', validators=[DataRequired()])
    nueva_password = PasswordField('Nueva Contraseña', validators=[
        DataRequired(), 
        Length(min=8, message='La contraseña debe tener al menos 8 caracteres')
    ])
    confirmar_password = PasswordField('Confirmar Nueva Contraseña', validators=[
        DataRequired(), 
        EqualTo('nueva_password', message='Las contraseñas no coinciden')
    ])
    submit = SubmitField('Cambiar Contraseña')


class AdminUserForm(FlaskForm):
    """Formulario para que los administradores gestionen usuarios"""
    nombre = StringField('Nombre', validators=[DataRequired(), Length(min=2, max=100)])
    apellido = StringField('Apellido', validators=[DataRequired(), Length(min=2, max=100)])
    username = StringField('Nombre de Usuario', validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    telefono = StringField('Teléfono', validators=[Optional(), Length(max=20)])
    fecha_nacimiento = DateField('Fecha de Nacimiento', validators=[Optional()])
    direccion = TextAreaField('Dirección', validators=[Optional(), Length(max=500)])
    
    # Campos de identificación
    tipo_identificacion = SelectField('Tipo de Identificación', 
                                    choices=[
                                        ('', 'Seleccionar...'),
                                        ('CC', 'Cédula de Ciudadanía'),
                                        ('CE', 'Cédula de Extranjería'),
                                        ('TI', 'Tarjeta de Identidad'),
                                        ('PP', 'Pasaporte'),
                                        ('NIT', 'NIT'),
                                        ('RC', 'Registro Civil')
                                    ], 
                                    validators=[Optional()])
    numero_identificacion = StringField('Número de Identificación', 
                                      validators=[Optional(), Length(max=20)])
    
    # Roles
    is_admin = BooleanField('Administrador')
    is_vendedor = BooleanField('Vendedor')
    is_contador = BooleanField('Contador')
    is_active = BooleanField('Usuario Activo', default=True)
    
    # Contraseña (opcional para edición, requerida para creación)
    password = PasswordField('Contraseña', validators=[
        Optional(), 
        Length(min=8, message='La contraseña debe tener al menos 8 caracteres')
    ])
    
    submit = SubmitField('Guardar Usuario')
    
    def __init__(self, user=None, *args, **kwargs):
        super(AdminUserForm, self).__init__(*args, **kwargs)
        self.user = user
        
        # Si es un nuevo usuario, hacer la contraseña requerida
        if not user:
            self.password.validators.append(DataRequired())
    
    def validate_username(self, username):
        if not self.user or username.data != self.user.username:
            user = User.query.filter_by(username=username.data).first()
            if user:
                raise ValidationError('Este nombre de usuario ya está en uso.')
    
    def validate_email(self, email):
        if not self.user or email.data != self.user.email:
            user = User.query.filter_by(email=email.data).first()
            if user:
                raise ValidationError('Este email ya está registrado.')