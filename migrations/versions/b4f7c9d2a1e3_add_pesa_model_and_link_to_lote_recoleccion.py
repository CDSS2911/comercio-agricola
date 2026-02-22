"""Add pesa model and link to lote_recoleccion

Revision ID: b4f7c9d2a1e3
Revises: 99a8a08c1415
Create Date: 2026-02-13 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b4f7c9d2a1e3'
down_revision = 'c76bca87d0c6'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    table_names = set(insp.get_table_names())

    if 'pesa' not in table_names:
        op.create_table(
            'pesa',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('nombre', sa.String(length=80), nullable=False),
            sa.Column('base_url', sa.String(length=255), nullable=False),
            sa.Column('token_api', sa.String(length=255), nullable=False),
            sa.Column('puerto', sa.String(length=20), nullable=False),
            sa.Column('baud', sa.Integer(), nullable=False),
            sa.Column('tolerancia', sa.Float(), nullable=False),
            sa.Column('reset_threshold', sa.Float(), nullable=False),
            sa.Column('activo', sa.Boolean(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )

    if 'lote_recoleccion' in table_names:
        columns = {c['name'] for c in insp.get_columns('lote_recoleccion')}
        if 'pesa_id' not in columns:
            with op.batch_alter_table('lote_recoleccion', schema=None) as batch_op:
                batch_op.add_column(sa.Column('pesa_id', sa.Integer(), nullable=True))

        fks = insp.get_foreign_keys('lote_recoleccion')
        has_fk = any(
            fk.get('referred_table') == 'pesa' and fk.get('constrained_columns') == ['pesa_id']
            for fk in fks
        )
        if not has_fk:
            with op.batch_alter_table('lote_recoleccion', schema=None) as batch_op:
                batch_op.create_foreign_key(None, 'pesa', ['pesa_id'], ['id'])


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    table_names = set(insp.get_table_names())

    if 'lote_recoleccion' in table_names:
        columns = {c['name'] for c in insp.get_columns('lote_recoleccion')}
        fks = insp.get_foreign_keys('lote_recoleccion')
        pesa_fk_names = [
            fk.get('name')
            for fk in fks
            if fk.get('referred_table') == 'pesa' and fk.get('constrained_columns') == ['pesa_id']
        ]
        if pesa_fk_names:
            with op.batch_alter_table('lote_recoleccion', schema=None) as batch_op:
                for fk_name in pesa_fk_names:
                    if fk_name:
                        batch_op.drop_constraint(fk_name, type_='foreignkey')
        if 'pesa_id' in columns:
            with op.batch_alter_table('lote_recoleccion', schema=None) as batch_op:
                batch_op.drop_column('pesa_id')

    if 'pesa' in table_names:
        op.drop_table('pesa')
