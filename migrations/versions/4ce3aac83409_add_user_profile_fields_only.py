"""Add user profile fields only

Revision ID: 4ce3aac83409
Revises: 7cd15bd2f4aa
Create Date: 2025-11-09 14:19:31.691428

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4ce3aac83409'
down_revision = '7cd15bd2f4aa'
branch_labels = None
depends_on = None


def upgrade():
    # ### Add new columns to user table ###
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('telefono', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('fecha_nacimiento', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('direccion', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('tipo_identificacion', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('numero_identificacion', sa.String(length=20), nullable=True))
        batch_op.create_index(batch_op.f('ix_user_numero_identificacion'), ['numero_identificacion'], unique=True)


def downgrade():
    # ### Remove columns from user table ###
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_user_numero_identificacion'))
        batch_op.drop_column('numero_identificacion')
        batch_op.drop_column('tipo_identificacion')
        batch_op.drop_column('direccion')
        batch_op.drop_column('fecha_nacimiento')
        batch_op.drop_column('telefono')
