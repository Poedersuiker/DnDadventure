from flask import Blueprint

admin_bp = Blueprint('admin', __name__, template_folder='../templates/admin', url_prefix='/admin')

from . import routes  # Import routes after blueprint creation
