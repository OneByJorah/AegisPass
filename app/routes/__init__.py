from app.routes.api import bp as api_bp
from app.routes.ui import bp as ui_bp
from app.routes.workflows import bp as workflows_bp
from app.routes.enrollment import bp as enrollment_bp

__all__ = ["api_bp", "ui_bp", "workflows_bp", "enrollment_bp"]
