"""Example NOMAD plugin -- demonstrates the plugin API.

To use: copy this file to your NOMAD data directory's plugins/ folder.
"""
from flask import Blueprint, jsonify

bp = Blueprint('example_plugin', __name__, url_prefix='/api/plugins/example')


@bp.route('/hello')
def hello():
    return jsonify({
        'message': 'Hello from the example plugin!',
        'plugin': 'example_plugin',
        'version': '1.0.0'
    })


def register(app):
    """Called by the NOMAD plugin loader during startup."""
    app.register_blueprint(bp)
