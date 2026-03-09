from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer as Serializer
from flask import current_app
from app import db, login_manager


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


user_roles = db.Table(
    'user_roles',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('role_id', db.Integer, db.ForeignKey('role.id'), primary_key=True)
)


role_permissions = db.Table(
    'role_permissions',
    db.Column('role_id', db.Integer, db.ForeignKey('role.id'), primary_key=True),
    db.Column('permission_id', db.Integer, db.ForeignKey('permission.id'), primary_key=True)
)


class Permission(db.Model):
    __tablename__ = 'permission'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(100), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    module = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Permission {self.code}>'


class Role(db.Model):
    __tablename__ = 'role'

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    active = db.Column(db.Boolean, default=True, nullable=False)
    is_system = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    permissions = db.relationship(
        'Permission',
        secondary=role_permissions,
        lazy='subquery',
        backref=db.backref('roles', lazy=True)
    )

    users = db.relationship(
        'User',
        secondary=user_roles,
        lazy='subquery',
        backref=db.backref('roles', lazy=True)
    )

    def __repr__(self):
        return f'<Role {self.slug}>'


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    
    # Información adicional del usuario
    telefono = db.Column(db.String(20), nullable=True)
    fecha_nacimiento = db.Column(db.Date, nullable=True)
    direccion = db.Column(db.Text, nullable=True)
    
    # Identificación
    tipo_identificacion = db.Column(db.String(20), nullable=True)  # CC, CE, TI, PP, etc.
    numero_identificacion = db.Column(db.String(20), nullable=True, unique=True, index=True)
    
    # Estados y roles
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    is_vendedor = db.Column(db.Boolean, default=False, nullable=False)
    is_contador = db.Column(db.Boolean, default=False, nullable=False)
    email_confirmed = db.Column(db.Boolean, default=False, nullable=False)
    
    # Fechas
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    def __repr__(self):
        return f'<User {self.username}>'
    
    def set_password(self, password):
        """Establece la contraseña del usuario (hasheada)"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Verifica si la contraseña es correcta"""
        return check_password_hash(self.password_hash, password)
    
    def get_full_name(self):
        """Retorna el nombre completo del usuario"""
        return f"{self.first_name} {self.last_name}"
    
    # Propiedades para compatibilidad con formularios
    @property
    def nombre(self):
        return self.first_name
    
    @nombre.setter
    def nombre(self, value):
        self.first_name = value
    
    @property
    def apellido(self):
        return self.last_name
    
    @apellido.setter
    def apellido(self, value):
        self.last_name = value
    
    @property
    def activo(self):
        return self.is_active
    
    @activo.setter
    def activo(self, value):
        self.is_active = value
    
    def generate_reset_token(self, expires_sec=1800):
        """Genera un token para recuperación de contraseña"""
        s = Serializer(current_app.config['SECRET_KEY'])
        return s.dumps({'user_id': self.id})
    
    @staticmethod
    def verify_reset_token(token, expires_sec=1800):
        """Verifica el token de recuperación de contraseña"""
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            user_id = s.loads(token, max_age=expires_sec)['user_id']
        except:
            return None
        return User.query.get(user_id)
    
    def generate_confirmation_token(self, expires_sec=3600):
        """Genera un token para confirmación de email"""
        s = Serializer(current_app.config['SECRET_KEY'])
        return s.dumps({'confirm': self.id})

    @staticmethod
    def verify_confirmation_token(token, expires_sec=3600):
        """Verifica token de confirmación y retorna el usuario."""
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            user_id = s.loads(token, max_age=expires_sec).get('confirm')
        except Exception:
            return None
        if not user_id:
            return None
        return User.query.get(user_id)
    
    def confirm_email(self, token, expires_sec=3600):
        """Confirma el email usando el token"""
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token, max_age=expires_sec)
        except:
            return False
        if data.get('confirm') != self.id:
            return False
        self.email_confirmed = True
        db.session.add(self)
        return True

    def has_role(self, role_slug):
        if not role_slug:
            return False
        return any(r.slug == role_slug and r.active for r in self.roles)

    def get_primary_role(self):
        if not self.roles:
            return None
        return sorted(self.roles, key=lambda r: r.id)[0]

    def set_single_role(self, role):
        self.roles = []
        if role:
            self.roles.append(role)
        self.sync_legacy_flags_from_roles()

    def sync_legacy_flags_from_roles(self):
        if not self.roles:
            return
        if self.has_role('superadmin'):
            self.is_admin = True
            self.is_vendedor = True
            self.is_contador = True
            return
        if self.has_role('admin'):
            self.is_admin = True
            self.is_vendedor = False
            self.is_contador = False
            return
        if self.has_role('operador'):
            self.is_admin = False
            self.is_vendedor = True
            self.is_contador = False
            return
        self.is_admin = False
        self.is_vendedor = False
        self.is_contador = False

    def has_permission(self, permission_code):
        if not permission_code:
            return False

        # RBAC priority when user has assigned roles.
        if self.roles:
            if self.has_role('superadmin'):
                return True
            role_permission_codes = {
                p.code
                for role in self.roles if role.active
                for p in role.permissions if p.active
            }
            return permission_code in role_permission_codes

        # Legacy fallback for users without roles yet.
        legacy_permissions = set()
        if self.is_admin:
            legacy_permissions.update({
                'admin.panel',
                'users.view',
                'users.create',
                'users.edit',
                'users.toggle_active',
                'users.reset_password',
                'users.assign_roles',
                'roles.manage',
                'permissions.manage',
                'inventario.access',
                'inventario.config',
                'ventas.sell',
                'ventas.dashboard.view',
                'ventas.sale.create',
                'ventas.history.view',
                'ventas.clients.view',
                'ventas.clients.manage',
                'ventas.payments.manage',
                'ventas.sale.cancel',
                'ventas.export',
                'gallinas.novedades',
            })
        if self.is_vendedor or self.is_contador:
            legacy_permissions.update({
                'ventas.sell',
                'ventas.dashboard.view',
                'ventas.sale.create',
            })

        return permission_code in legacy_permissions


class LoginAttempt(db.Model):
    """Modelo para registrar intentos de login (para seguridad)"""
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45), nullable=False)  # IPv6 compatible
    username_attempted = db.Column(db.String(80), nullable=False)
    successful = db.Column(db.Boolean, default=False, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_agent = db.Column(db.Text)
    
    def __repr__(self):
        return f'<LoginAttempt {self.username_attempted} - {self.ip_address}>'


# =============================================================================
# MODELOS DE INVENTARIO DE HUEVOS
# =============================================================================

class CategoriaHuevo(db.Model):
    """Categorías de huevos basadas en peso"""
    __tablename__ = 'categoria_huevo'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), nullable=False)  # XL, L, M, S, etc.
    peso_min = db.Column(db.Float, nullable=False)     # Peso mínimo en gramos
    peso_max = db.Column(db.Float, nullable=False)     # Peso máximo en gramos
    precio_venta = db.Column(db.Numeric(10, 2), default=0)  # Precio por unidad
    activo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relación con huevos
    huevos = db.relationship('Huevo', backref='categoria', lazy=True)
    
    def __repr__(self):
        return f'<CategoriaHuevo {self.nombre} ({self.peso_min}-{self.peso_max}g)>'
    
    @staticmethod
    def clasificar_por_peso(peso):
        """Clasifica un huevo según su peso"""
        categoria = CategoriaHuevo.query.filter(
            CategoriaHuevo.peso_min <= peso,
            CategoriaHuevo.peso_max >= peso,
            CategoriaHuevo.activo == True
        ).first()
        return categoria

class Pesa(db.Model):
    """Configuracion de una balanza para pesaje automatico"""
    __tablename__ = 'pesa'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(80), nullable=False)
    base_url = db.Column(db.String(255), nullable=False)
    token_api = db.Column(db.String(255), nullable=False)
    puerto = db.Column(db.String(20), nullable=False)
    baud = db.Column(db.Integer, default=9600, nullable=False)
    tolerancia = db.Column(db.Float, default=1.0, nullable=False)
    reset_threshold = db.Column(db.Float, default=1.0, nullable=False)
    activo = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    lotes = db.relationship('LoteRecoleccion', backref='pesa', lazy=True)

    def __repr__(self):
        return f'<Pesa {self.id} - {self.nombre}>'

class LoteRecoleccion(db.Model):
    """Lote de recolección de huevos"""
    __tablename__ = 'lote_recoleccion'
    
    id = db.Column(db.Integer, primary_key=True)
    numero_lote = db.Column(db.String(20), unique=True, nullable=False)
    fecha_recoleccion = db.Column(db.Date, nullable=False, default=datetime.utcnow().date)
    hora_inicio = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    hora_fin = db.Column(db.DateTime, nullable=True)
    
    # Usuario que realiza la recolección
    usuario_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    usuario = db.relationship('User', backref='lotes_recoleccion')
    
    # Relación con lote de gallinas
    lote_gallinas_id = db.Column(db.Integer, db.ForeignKey('lote_gallinas.id'), nullable=True)
    lote_gallinas = db.relationship('LoteGallinas', backref='recolecciones')
    semana_produccion = db.Column(db.Integer, nullable=True)  # Semana de producción del lote

    pesa_id = db.Column(db.Integer, db.ForeignKey('pesa.id'), nullable=True)
    
    # Estado del lote
    estado = db.Column(db.String(20), default='EN_PROCESO')  # EN_PROCESO, COMPLETADO, CANCELADO
    observaciones = db.Column(db.Text, nullable=True)
    
    # Estadísticas del lote
    total_huevos = db.Column(db.Integer, default=0)
    total_peso = db.Column(db.Float, default=0)
    huevos_rotos = db.Column(db.Integer, default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relación con huevos
    huevos = db.relationship('Huevo', backref='lote', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<LoteRecoleccion {self.numero_lote} - {self.fecha_recoleccion}>'
    
    def generar_numero_lote(self):
        """Genera un número de lote automático"""
        fecha = datetime.now().strftime('%Y%m%d')
        ultimo_lote = LoteRecoleccion.query.filter(
            LoteRecoleccion.numero_lote.like(f'{fecha}%')
        ).order_by(LoteRecoleccion.id.desc()).first()
        
        if ultimo_lote:
            ultimo_num = int(ultimo_lote.numero_lote[-3:])
            nuevo_num = str(ultimo_num + 1).zfill(3)
        else:
            nuevo_num = '001'
        
        self.numero_lote = f'{fecha}-{nuevo_num}'
        return self.numero_lote
    
    def completar_lote(self):
        """Marca el lote como completado"""
        self.estado = 'COMPLETADO'
        self.hora_fin = datetime.utcnow()
        self.actualizar_estadisticas()
    
    def actualizar_estadisticas(self):
        """Actualiza las estadisticas del lote"""
        self.total_huevos = (
            db.session.query(db.func.count(Huevo.id))
            .filter(Huevo.lote_id == self.id, Huevo.roto == False)
            .scalar()
            or 0
        )
        self.huevos_rotos = (
            db.session.query(db.func.count(Huevo.id))
            .filter(Huevo.lote_id == self.id, Huevo.roto == True)
            .scalar()
            or 0
        )
        self.total_peso = float(
            db.session.query(db.func.coalesce(db.func.sum(Huevo.peso), 0.0))
            .filter(Huevo.lote_id == self.id, Huevo.roto == False)
            .scalar()
            or 0.0
        )


class Huevo(db.Model):
    """Huevo individual pesado"""
    __tablename__ = 'huevo'
    
    id = db.Column(db.Integer, primary_key=True)
    peso = db.Column(db.Float, nullable=False)  # Peso en gramos
    roto = db.Column(db.Boolean, default=False, nullable=False)  # Si está roto
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relaciones
    lote_id = db.Column(db.Integer, db.ForeignKey('lote_recoleccion.id'), nullable=False)
    categoria_id = db.Column(db.Integer, db.ForeignKey('categoria_huevo.id'), nullable=True)
    
    # Estado del huevo
    vendido = db.Column(db.Boolean, default=False)
    fecha_venta = db.Column(db.DateTime, nullable=True)
    
    def __repr__(self):
        return f'<Huevo {self.peso}g - {"Roto" if self.roto else "OK"}>'
    
    def clasificar(self):
        """Clasifica el huevo según su peso"""
        if not self.roto:
            categoria = CategoriaHuevo.clasificar_por_peso(self.peso)
            if categoria:
                self.categoria_id = categoria.id
        return self.categoria_id
    
    @staticmethod
    def procesar_desde_archivo(file_path, lote_id):
        """Procesa huevos desde un archivo de texto"""
        huevos_procesados = []
        try:
            with open(file_path, 'r') as file:
                for line in file:
                    peso_str = line.strip()
                    if peso_str and peso_str.replace('.', '').isdigit():
                        peso = float(peso_str)
                        huevo = Huevo(
                            peso=peso,
                            lote_id=lote_id
                        )
                        huevo.clasificar()
                        huevos_procesados.append(huevo)
        except Exception as e:
            print(f"Error procesando archivo: {e}")
        
        return huevos_procesados


class InventarioHuevos(db.Model):
    """Inventario consolidado de huevos por categoría"""
    __tablename__ = 'inventario_huevos'
    
    id = db.Column(db.Integer, primary_key=True)
    categoria_id = db.Column(db.Integer, db.ForeignKey('categoria_huevo.id'), nullable=False)
    categoria = db.relationship('CategoriaHuevo', backref='inventario')
    
    cantidad_disponible = db.Column(db.Integer, default=0)
    cantidad_vendida = db.Column(db.Integer, default=0)
    cantidad_rota = db.Column(db.Integer, default=0)
    
    ultima_actualizacion = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<InventarioHuevos {self.categoria.nombre}: {self.cantidad_disponible}>'
    
    @staticmethod
    def actualizar_inventario():
        """Actualiza el inventario completo basado en los huevos registrados"""
        # Limpiar inventario actual
        InventarioHuevos.query.delete()
        
        # Obtener estadísticas por categoría
        from sqlalchemy import func
        
        stats = db.session.query(
            Huevo.categoria_id,
            func.sum(db.case([(Huevo.roto == False, 1)], else_=0)).label('disponibles'),
            func.sum(db.case([(Huevo.vendido == True, 1)], else_=0)).label('vendidos'),
            func.sum(db.case([(Huevo.roto == True, 1)], else_=0)).label('rotos')
        ).filter(Huevo.categoria_id.isnot(None)).group_by(Huevo.categoria_id).all()
        
        # Crear registros de inventario
        for stat in stats:
            inventario = InventarioHuevos(
                categoria_id=stat.categoria_id,
                cantidad_disponible=stat.disponibles or 0,
                cantidad_vendida=stat.vendidos or 0,
                cantidad_rota=stat.rotos or 0
            )
            db.session.add(inventario)
        
        db.session.commit()


# ===========================
# MODELOS DE GESTIÓN DE GALLINAS (LEVANTE)
# ===========================

class Gasto(db.Model):
    """Registro de gastos operativos"""
    __tablename__ = 'gasto'

    id = db.Column(db.Integer, primary_key=True)
    fecha_hora = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    valor = db.Column(db.Numeric(12, 2), nullable=False)
    tipo = db.Column(db.String(20), nullable=False, index=True)  # insumos, servicios, otros
    descripcion = db.Column(db.Text, nullable=False)

    usuario_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    usuario = db.relationship('User', backref=db.backref('gastos_registrados', lazy='dynamic'))

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<Gasto {self.id} {self.tipo} ${self.valor}>'

class LoteGallinas(db.Model):
    """Modelo para gestionar lotes de gallinas ponedoras"""
    __tablename__ = 'lote_gallinas'
    
    id = db.Column(db.Integer, primary_key=True)
    numero_lote = db.Column(db.String(50), unique=True, nullable=False, index=True)
    
    # Información del lote
    cantidad_inicial = db.Column(db.Integer, nullable=False)  # Cantidad de gallinas al inicio
    cantidad_actual = db.Column(db.Integer, nullable=False)  # Cantidad actual de gallinas vivas
    raza = db.Column(db.String(100), nullable=True)  # Raza de las gallinas
    
    # Fechas importantes
    fecha_ingreso = db.Column(db.Date, nullable=False)  # Fecha de entrada del lote
    fecha_inicio_produccion = db.Column(db.Date, nullable=True)  # Fecha de primera postura
    fecha_fin_produccion = db.Column(db.Date, nullable=True)  # Fecha estimada/real fin producción
    
    # Control de edad y producción
    edad_semanas_ingreso = db.Column(db.Integer, default=0)  # Edad en semanas al ingresar
    semanas_produccion_maximas = db.Column(db.Integer, default=80)  # Semanas máximas de producción
    
    # Estado del lote
    estado = db.Column(db.String(20), default='ACTIVO')  # ACTIVO, FINALIZADO, VENDIDO
    ubicacion = db.Column(db.String(100), nullable=True)  # Ubicación física del lote (gallinero)
    
    # Costos
    costo_unitario = db.Column(db.Numeric(10, 2), nullable=True)  # Costo por gallina
    costo_total = db.Column(db.Numeric(12, 2), nullable=True)  # Costo total del lote
    
    # Observaciones
    observaciones = db.Column(db.Text, nullable=True)
    
    # Fechas de registro
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Usuario responsable
    usuario_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    usuario = db.relationship('User', backref='lotes_gallinas')
    
    # Relaciones
    registros_mortalidad = db.relationship('RegistroMortalidad', backref='lote_gallinas', lazy='dynamic', cascade='all, delete-orphan')
    registros_venta_gallinas = db.relationship('VentaGallinas', backref='lote_gallinas', lazy='dynamic', cascade='all, delete-orphan')
    registros_sanitarios = db.relationship('RegistroSanitario', backref='lote_gallinas', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<LoteGallinas {self.numero_lote} - {self.cantidad_actual} gallinas>'
    
    def get_edad_actual_semanas(self):
        """Calcula la edad actual del lote en semanas"""
        if not self.fecha_ingreso:
            return 0
        dias = (datetime.now().date() - self.fecha_ingreso).days
        return (dias // 7) + self.edad_semanas_ingreso
    
    def get_semanas_produccion(self):
        """Calcula las semanas de producción del lote basado en la última recolección"""
        if not self.fecha_inicio_produccion:
            return 0
        
        # Buscar la última recolección de este lote
        from app.models import LoteRecoleccion
        ultima_recoleccion = LoteRecoleccion.query.filter_by(
            lote_gallinas_id=self.id
        ).order_by(
            LoteRecoleccion.semana_produccion.desc()
        ).first()
        
        if ultima_recoleccion and ultima_recoleccion.semana_produccion:
            return ultima_recoleccion.semana_produccion
        
        # Si no hay recolecciones, calcular por fecha (fallback)
        dias = (datetime.now().date() - self.fecha_inicio_produccion).days
        # Si es el mismo día o dentro de la primera semana, retornar 1
        if dias < 7:
            return 1 if dias >= 0 else 0
        return (dias // 7) + 1
    
    def get_semanas_restantes(self):
        """Calcula las semanas restantes basado en la edad actual del lote (máximo 80 semanas de vida)"""
        edad_actual = self.get_edad_actual_semanas()
        return max(0, self.semanas_produccion_maximas - edad_actual)
    
    def get_porcentaje_vida_util(self):
        """Calcula el porcentaje de vida útil consumido basado en edad actual (máximo 80 semanas)"""
        if self.semanas_produccion_maximas == 0:
            return 100
        edad_actual = self.get_edad_actual_semanas()
        return min(100, (edad_actual / self.semanas_produccion_maximas) * 100)
    
    def get_alerta_nivel(self):
        """Retorna el nivel de alerta basado en las semanas restantes"""
        semanas_restantes = self.get_semanas_restantes()
        if semanas_restantes <= 2:
            return 'CRITICO'  # Rojo - Vender inmediatamente
        elif semanas_restantes <= 4:
            return 'ALTO'  # Naranja - Planear venta
        elif semanas_restantes <= 8:
            return 'MEDIO'  # Amarillo - Monitorear
        else:
            return 'BAJO'  # Verde - Normal
    
    def get_mortalidad_total(self):
        """Calcula el total de gallinas muertas"""
        return self.registros_mortalidad.with_entities(
            db.func.sum(RegistroMortalidad.cantidad)
        ).scalar() or 0
    
    def get_vendidas_total(self):
        """Calcula el total de gallinas vendidas"""
        return self.registros_venta_gallinas.with_entities(
            db.func.sum(VentaGallinas.cantidad)
        ).scalar() or 0
    
    def get_tasa_mortalidad(self):
        """Calcula la tasa de mortalidad del lote"""
        if self.cantidad_inicial == 0:
            return 0
        return (self.get_mortalidad_total() / self.cantidad_inicial) * 100
    
    def actualizar_cantidad_actual(self):
        """Actualiza la cantidad actual de gallinas"""
        mortalidad = self.get_mortalidad_total()
        vendidas = self.get_vendidas_total()
        self.cantidad_actual = self.cantidad_inicial - mortalidad - vendidas
        
    def get_produccion_semanal(self, semana=None):
        """Obtiene la producción de huevos de una semana específica"""
        if semana is None:
            semana = self.get_semanas_produccion()
        
        # Calcular fechas de la semana
        fecha_inicio_semana = self.fecha_inicio_produccion + timedelta(weeks=semana)
        fecha_fin_semana = fecha_inicio_semana + timedelta(days=7)
        
        # Consultar huevos recolectados en esa semana
        from app.models import LoteRecoleccion, Huevo
        total_huevos = db.session.query(db.func.count(Huevo.id)).join(
            LoteRecoleccion
        ).filter(
            LoteRecoleccion.lote_gallinas_id == self.id,
            LoteRecoleccion.fecha_recoleccion >= fecha_inicio_semana,
            LoteRecoleccion.fecha_recoleccion < fecha_fin_semana
        ).scalar() or 0
        
        return total_huevos


class RegistroMortalidad(db.Model):
    """Registro de muertes de gallinas en un lote"""
    __tablename__ = 'registro_mortalidad'
    
    id = db.Column(db.Integer, primary_key=True)
    lote_gallinas_id = db.Column(db.Integer, db.ForeignKey('lote_gallinas.id'), nullable=False)
    
    fecha_registro = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    cantidad = db.Column(db.Integer, nullable=False)
    
    # Causa de muerte
    causa = db.Column(db.String(100), nullable=True)  # Enfermedad, Depredador, Natural, Desconocida
    observaciones = db.Column(db.Text, nullable=True)
    
    # Gallinas separadas por enfermedad
    gallinas_separadas = db.Column(db.Integer, default=0, nullable=True)
    ubicacion_separacion = db.Column(db.String(100), nullable=True)  # Dónde se separaron
    
    # Evidencia fotográfica
    imagen = db.Column(db.String(255), nullable=True)  # Ruta de la imagen
    
    # Usuario que registra
    usuario_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    usuario = db.relationship('User', backref='registros_mortalidad')
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<RegistroMortalidad {self.cantidad} gallinas - {self.fecha_registro}>'


class VentaGallinas(db.Model):
    """Registro de venta de gallinas al final de su ciclo productivo"""
    __tablename__ = 'venta_gallinas'
    
    id = db.Column(db.Integer, primary_key=True)
    lote_gallinas_id = db.Column(db.Integer, db.ForeignKey('lote_gallinas.id'), nullable=False)
    
    fecha_venta = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    cantidad = db.Column(db.Integer, nullable=False)
    
    # Información de venta
    precio_unitario = db.Column(db.Numeric(10, 2), nullable=True)
    precio_total = db.Column(db.Numeric(12, 2), nullable=True)
    
    # Cliente (opcional)
    comprador = db.Column(db.String(200), nullable=True)
    
    observaciones = db.Column(db.Text, nullable=True)
    
    # Usuario que registra
    usuario_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    usuario = db.relationship('User', backref='ventas_gallinas_registradas')
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<VentaGallinas {self.numero_venta} - {self.cantidad} gallinas>'


class RegistroSanitario(db.Model):
    """Registro de tratamientos sanitarios y vacunación de gallinas"""
    __tablename__ = 'registro_sanitario'
    
    id = db.Column(db.Integer, primary_key=True)
    lote_gallinas_id = db.Column(db.Integer, db.ForeignKey('lote_gallinas.id'), nullable=False)
    
    fecha_aplicacion = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    tipo_tratamiento = db.Column(db.String(50), nullable=False)  # VACUNA, DESPARASITACION, VITAMINAS, ANTIBIOTICO
    
    # Detalles del tratamiento
    producto = db.Column(db.String(200), nullable=False)
    dosis = db.Column(db.String(100), nullable=True)
    
    # Próxima aplicación
    fecha_proxima_aplicacion = db.Column(db.Date, nullable=True)
    
    observaciones = db.Column(db.Text, nullable=True)
    
    # Gallinas separadas por enfermedad (para tratamientos específicos)
    gallinas_separadas = db.Column(db.Integer, default=0, nullable=True)
    ubicacion_separacion = db.Column(db.String(100), nullable=True)
    
    # Evidencia fotográfica
    imagen = db.Column(db.String(255), nullable=True)
    
    # Usuario que registra
    usuario_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    usuario = db.relationship('User', backref='registros_sanitarios')
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<RegistroSanitario {self.tipo_tratamiento} - {self.producto}>'


class SeparacionGallinas(db.Model):
    """Registro independiente de separación de gallinas por enfermedad o cuarentena"""
    __tablename__ = 'separacion_gallinas'
    
    id = db.Column(db.Integer, primary_key=True)
    lote_gallinas_id = db.Column(db.Integer, db.ForeignKey('lote_gallinas.id'), nullable=False)
    
    # Fecha y hora de separación
    fecha_separacion = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    hora_separacion = db.Column(db.Time, nullable=False, default=datetime.utcnow().time)
    
    # Cantidad de gallinas separadas
    cantidad = db.Column(db.Integer, nullable=False)
    
    # Peso promedio de las gallinas separadas
    peso_promedio = db.Column(db.Numeric(5, 2), nullable=True)  # En kilogramos
    
    # Motivo y ubicación
    motivo = db.Column(db.String(200), nullable=False)  # Enfermedad, cuarentena, tratamiento, etc.
    ubicacion = db.Column(db.String(100), nullable=False)  # Dónde fueron separadas
    
    # Estado de las gallinas separadas
    estado = db.Column(db.String(20), default='Separada', nullable=False)  # Separada, Recuperada, Muerta, Vendida
    
    # Fecha de resolución (cuando regresan o mueren)
    fecha_resolucion = db.Column(db.Date, nullable=True)
    observaciones_resolucion = db.Column(db.Text, nullable=True)
    
    # Observaciones iniciales
    observaciones = db.Column(db.Text, nullable=True)
    
    # Evidencia fotográfica
    imagen = db.Column(db.String(255), nullable=True)
    
    # Usuario que registra
    usuario_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    usuario = db.relationship('User', backref='separaciones_gallinas')
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<SeparacionGallinas {self.cantidad} gallinas - {self.fecha_separacion}>'


# ===========================
# MODELOS DE VENTAS
# ===========================

class Cliente(db.Model):
    """Modelo para clientes del sistema de ventas"""
    __tablename__ = 'cliente'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Información personal
    nombre = db.Column(db.String(100), nullable=False)
    apellido = db.Column(db.String(100), nullable=False)
    telefono = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    direccion = db.Column(db.Text, nullable=True)
    
    # Identificación
    tipo_identificacion = db.Column(db.String(20), nullable=True)  # CC, CE, TI, PP, etc.
    numero_identificacion = db.Column(db.String(20), nullable=True, unique=True, index=True)
    
    # Estado del cliente
    activo = db.Column(db.Boolean, default=True, nullable=False)
    limite_credito = db.Column(db.Numeric(10, 2), default=0.00)  # Límite de crédito en pesos
    
    # Fechas
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relaciones
    ventas = db.relationship('Venta', backref='cliente', lazy='dynamic')
    pagos = db.relationship('Pago', backref='cliente', lazy='dynamic')
    
    def __repr__(self):
        return f'<Cliente {self.nombre} {self.apellido}>'
    
    def get_nombre_completo(self):
        return f'{self.nombre} {self.apellido}'
    
    def get_saldo_pendiente(self):
        """Calcula el saldo pendiente del cliente"""
        total_ventas = self.ventas.filter_by(tipo_pago='credito').filter(
            Venta.estado.in_(['pendiente', 'parcial'])
        ).with_entities(db.func.sum(Venta.total)).scalar() or 0
        
        total_pagos = self.pagos.with_entities(db.func.sum(Pago.monto)).scalar() or 0
        
        saldo = float(total_ventas) - float(total_pagos)
        return max(0, saldo)
    
    def puede_comprar_a_credito(self, monto):
        """Verifica si el cliente puede comprar a crédito por el monto especificado"""
        if not self.activo:
            return False
        saldo_actual = self.get_saldo_pendiente()
        return (saldo_actual + float(monto)) <= float(self.limite_credito)
    
    def get_credito_disponible(self):
        """Calcula el crédito disponible del cliente"""
        saldo_pendiente = self.get_saldo_pendiente()
        credito_disponible = float(self.limite_credito) - saldo_pendiente
        return max(0, credito_disponible)


class Venta(db.Model):
    """Modelo para registrar las ventas de huevos"""
    __tablename__ = 'venta'
    
    id = db.Column(db.Integer, primary_key=True)
    numero_venta = db.Column(db.String(20), unique=True, nullable=False, index=True)
    
    # Cliente (opcional para ventas de contado)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=True)
    
    # Vendedor
    vendedor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Tipo de venta
    tipo_pago = db.Column(db.String(20), nullable=False)  # 'contado' o 'credito'
    estado = db.Column(db.String(20), default='completada', nullable=False)  # 'completada', 'pendiente', 'parcial', 'cancelada'
    
    # Totales
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    descuento = db.Column(db.Numeric(10, 2), default=0.00)
    total = db.Column(db.Numeric(10, 2), nullable=False)
    
    # Fechas
    fecha_venta = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_vencimiento = db.Column(db.DateTime, nullable=True)  # Para ventas a crédito
    
    # Observaciones
    observaciones = db.Column(db.Text, nullable=True)
    
    # Relaciones
    detalles = db.relationship('DetalleVenta', backref='venta', lazy='dynamic', cascade='all, delete-orphan')
    pagos = db.relationship('Pago', backref='venta', lazy='dynamic')
    vendedor = db.relationship('User', backref='ventas_realizadas')
    
    def __repr__(self):
        return f'<Venta {self.numero_venta}>'
    
    def get_monto_pagado(self):
        """Calcula el monto total pagado de la venta"""
        return self.pagos.with_entities(db.func.sum(Pago.monto)).scalar() or 0
    
    def get_saldo_pendiente(self):
        """Calcula el saldo pendiente de la venta"""
        return float(self.total) - float(self.get_monto_pagado())
    
    def actualizar_estado(self):
        """Actualiza el estado de la venta basado en los pagos"""
        if self.tipo_pago == 'contado':
            self.estado = 'completada'
        else:
            saldo = self.get_saldo_pendiente()
            if saldo <= 0:
                self.estado = 'completada'
            elif saldo < float(self.total):
                self.estado = 'parcial'
            else:
                self.estado = 'pendiente'


class DetalleVenta(db.Model):
    """Modelo para los detalles de cada venta"""
    __tablename__ = 'detalle_venta'
    
    id = db.Column(db.Integer, primary_key=True)
    venta_id = db.Column(db.Integer, db.ForeignKey('venta.id'), nullable=False)
    categoria_id = db.Column(db.Integer, db.ForeignKey('categoria_huevo.id'), nullable=False)
    
    # Detalles del producto
    cantidad_huevos = db.Column(db.Integer, nullable=False)
    cantidad_paneles = db.Column(db.Integer, nullable=False)  # 1 panel = 30 huevos
    precio_unitario = db.Column(db.Numeric(8, 2), nullable=False)  # Precio por huevo
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    
    # Relaciones
    categoria = db.relationship('CategoriaHuevo', backref='ventas_detalle')
    
    def __repr__(self):
        return f'<DetalleVenta {self.cantidad_huevos} huevos {self.categoria.nombre if self.categoria else ""}>'


class Pago(db.Model):
    """Modelo para registrar los pagos de las ventas a crédito"""
    __tablename__ = 'pago'
    
    id = db.Column(db.Integer, primary_key=True)
    numero_pago = db.Column(db.String(20), unique=True, nullable=False, index=True)
    numero_recibo = db.Column(db.String(20), unique=True, index=True, nullable=True)
    
    # Relaciones
    venta_id = db.Column(db.Integer, db.ForeignKey('venta.id'), nullable=False)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=False)
    recibido_por = db.Column('usuario_id', db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Detalles del pago
    monto = db.Column(db.Numeric(10, 2), nullable=False)
    forma_pago = db.Column(db.String(20), nullable=False)  # 'efectivo', 'transferencia', 'cheque'
    
    # Referencias
    referencia = db.Column(db.String(100), nullable=True)  # Número de transferencia, cheque, etc.
    
    # Fechas
    fecha_pago = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Observaciones
    observaciones = db.Column(db.Text, nullable=True)
    
    # Relación con usuario que recibe el pago
    receptor = db.relationship('User', backref='pagos_recibidos', foreign_keys=[recibido_por])
    
    def __repr__(self):
        return f'<Pago {self.numero_pago} - ${self.monto}>'


class ConfiguracionVenta(db.Model):
    """Configuraciones generales del sistema de ventas"""
    __tablename__ = 'configuracion_venta'
    
    id = db.Column(db.Integer, primary_key=True)
    clave = db.Column(db.String(50), unique=True, nullable=False)
    valor = db.Column(db.Text, nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    
    # Fecha de modificación
    fecha_modificacion = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    modificado_por = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    def __repr__(self):
        return f'<ConfiguracionVenta {self.clave}>'



