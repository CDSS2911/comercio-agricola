"""add gasto table

Revision ID: e3c4f1a9b7d2
Revises: f2a1b7c8d9e0
Create Date: 2026-02-22 11:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e3c4f1a9b7d2'
down_revision = 'f2a1b7c8d9e0'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'gasto',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('fecha_hora', sa.DateTime(), nullable=False),
        sa.Column('valor', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('tipo', sa.String(length=20), nullable=False),
        sa.Column('descripcion', sa.Text(), nullable=False),
        sa.Column('usuario_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['usuario_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_gasto_fecha_hora'), 'gasto', ['fecha_hora'], unique=False)
    op.create_index(op.f('ix_gasto_tipo'), 'gasto', ['tipo'], unique=False)
    op.create_index(op.f('ix_gasto_usuario_id'), 'gasto', ['usuario_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_gasto_usuario_id'), table_name='gasto')
    op.drop_index(op.f('ix_gasto_tipo'), table_name='gasto')
    op.drop_index(op.f('ix_gasto_fecha_hora'), table_name='gasto')
    op.drop_table('gasto')
