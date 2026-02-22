"""Add roles and permissions RBAC

Revision ID: d91f4e2b6c11
Revises: b4f7c9d2a1e3
Create Date: 2026-02-13 18:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd91f4e2b6c11'
down_revision = 'b4f7c9d2a1e3'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    table_names = set(insp.get_table_names())

    if 'permission' not in table_names:
        op.create_table(
            'permission',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('code', sa.String(length=100), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('module', sa.String(length=50), nullable=False),
            sa.Column('description', sa.String(length=255), nullable=True),
            sa.Column('active', sa.Boolean(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('permission', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_permission_code'), ['code'], unique=True)
    else:
        idx_names = {idx.get('name') for idx in insp.get_indexes('permission')}
        if 'ix_permission_code' not in idx_names:
            with op.batch_alter_table('permission', schema=None) as batch_op:
                batch_op.create_index(batch_op.f('ix_permission_code'), ['code'], unique=True)

    if 'role' not in table_names:
        op.create_table(
            'role',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('slug', sa.String(length=50), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('description', sa.String(length=255), nullable=True),
            sa.Column('active', sa.Boolean(), nullable=False),
            sa.Column('is_system', sa.Boolean(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('role', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_role_slug'), ['slug'], unique=True)
    else:
        idx_names = {idx.get('name') for idx in insp.get_indexes('role')}
        if 'ix_role_slug' not in idx_names:
            with op.batch_alter_table('role', schema=None) as batch_op:
                batch_op.create_index(batch_op.f('ix_role_slug'), ['slug'], unique=True)

    if 'user_roles' not in table_names:
        op.create_table(
            'user_roles',
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('role_id', sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(['role_id'], ['role.id'], ),
            sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
            sa.PrimaryKeyConstraint('user_id', 'role_id')
        )

    if 'role_permissions' not in table_names:
        op.create_table(
            'role_permissions',
            sa.Column('role_id', sa.Integer(), nullable=False),
            sa.Column('permission_id', sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(['permission_id'], ['permission.id'], ),
            sa.ForeignKeyConstraint(['role_id'], ['role.id'], ),
            sa.PrimaryKeyConstraint('role_id', 'permission_id')
        )

    permissions = [
        ('admin.panel', 'Acceso panel admin', 'admin', 'Acceder al panel administrativo'),
        ('users.view', 'Ver usuarios', 'usuarios', 'Ver listado de usuarios'),
        ('users.create', 'Crear usuarios', 'usuarios', 'Crear nuevos usuarios'),
        ('users.edit', 'Editar usuarios', 'usuarios', 'Editar usuarios existentes'),
        ('users.toggle_active', 'Activar/Inactivar usuarios', 'usuarios', 'Cambiar estado de usuarios'),
        ('users.reset_password', 'Resetear contraseñas', 'usuarios', 'Generar contraseñas temporales'),
        ('users.assign_roles', 'Asignar roles', 'usuarios', 'Asignar roles a usuarios'),
        ('roles.manage', 'Gestionar roles', 'usuarios', 'CRUD de roles'),
        ('permissions.manage', 'Gestionar permisos', 'usuarios', 'CRUD de permisos'),
        ('inventario.access', 'Acceso inventario', 'inventario', 'Acceder a inventario de huevos'),
        ('inventario.config', 'Configurar inventario', 'inventario', 'Administrar categorias y pesas'),
        ('ventas.sell', 'Vender', 'ventas', 'Registrar y gestionar ventas'),
        ('gallinas.novedades', 'Registrar novedades aves', 'gallinas', 'Gestionar novedades de gallinas'),
    ]

    for code, name, module, description in permissions:
        bind.execute(
            sa.text(
                "INSERT INTO permission (code, name, module, description, active, created_at) "
                "SELECT :code, :name, :module, :description, 1, NOW() "
                "WHERE NOT EXISTS (SELECT 1 FROM permission WHERE code = :code)"
            ),
            {"code": code, "name": name, "module": module, "description": description},
        )

    roles = [
        ('superadmin', 'Superadmin', 'Control total del sistema'),
        ('admin', 'Admin', 'Administra operacion sin crear usuarios ni contraseñas'),
        ('operador', 'Operador', 'Inventario huevos, vender y novedades aves'),
    ]
    for slug, name, description in roles:
        bind.execute(
            sa.text(
                "INSERT INTO role (slug, name, description, active, is_system, created_at) "
                "SELECT :slug, :name, :description, 1, 1, NOW() "
                "WHERE NOT EXISTS (SELECT 1 FROM role WHERE slug = :slug)"
            ),
            {"slug": slug, "name": name, "description": description},
        )

    # Asignar permisos por rol
    role_permissions_map = {
        'superadmin': [p[0] for p in permissions],
        'admin': [
            'admin.panel',
            'users.view',
            'users.edit',
            'users.toggle_active',
            'users.assign_roles',
            'inventario.access',
            'inventario.config',
            'ventas.sell',
            'gallinas.novedades',
        ],
        'operador': [
            'inventario.access',
            'ventas.sell',
            'gallinas.novedades',
        ],
    }

    for role_slug, permission_codes in role_permissions_map.items():
        for permission_code in permission_codes:
            bind.execute(
                sa.text(
                    "INSERT INTO role_permissions (role_id, permission_id) "
                    "SELECT r.id, p.id FROM role r, permission p "
                    "WHERE r.slug = :role_slug AND p.code = :permission_code "
                    "AND NOT EXISTS ("
                    "  SELECT 1 FROM role_permissions rp "
                    "  WHERE rp.role_id = r.id AND rp.permission_id = p.id"
                    ")"
                ),
                {"role_slug": role_slug, "permission_code": permission_code},
            )


def downgrade():
    op.drop_table('role_permissions')
    op.drop_table('user_roles')
    with op.batch_alter_table('role', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_role_slug'))
    op.drop_table('role')
    with op.batch_alter_table('permission', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_permission_code'))
    op.drop_table('permission')
