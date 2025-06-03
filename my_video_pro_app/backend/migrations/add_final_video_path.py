"""Add final_video_path column to jobs table"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = 'add_final_video_path'
down_revision = None  # Update this to your last migration
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('jobs', sa.Column('final_video_path', sa.String(500), nullable=True))

def downgrade():
    op.drop_column('jobs', 'final_video_path') 