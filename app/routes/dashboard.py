from flask import Blueprint, render_template

# Developer/testing dashboard. This serves a static HTML page that calls the
# existing API endpoints from the browser. It adds NO backend logic.
bp = Blueprint('dashboard', __name__)


@bp.route('/', methods=['GET'])
def dashboard():
    """Render the developer dashboard (dev/testing only)."""
    return render_template('dashboard.html')
