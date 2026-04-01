"""WorldSim Flask Application"""
import logging

from flask import Flask, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO
from config import Config
from models.database import init_db

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.json.ensure_ascii = False

    CORS(app, resources={r"/api/*": {"origins": "*"}})
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

    # Init database
    init_db()

    # Register routes
    from routes.scenario import scenario_bp, register_scenario_socket
    from routes.entity import entity_bp
    from routes.simulation import simulation_bp, register_simulation_socket
    from routes.report import report_bp

    app.register_blueprint(scenario_bp, url_prefix='/api/scenarios')
    app.register_blueprint(entity_bp, url_prefix='/api')
    app.register_blueprint(simulation_bp, url_prefix='/api/simulations')
    app.register_blueprint(report_bp, url_prefix='/api/reports')

    register_scenario_socket(socketio)
    register_simulation_socket(socketio)

    # Health check
    @app.route('/health')
    def health():
        return jsonify({'status': 'ok', 'service': 'WorldSim'})

    # Request logging
    @app.before_request
    def log_request():
        from flask import request
        logger.debug(f'{request.method} {request.path}')

    return app, socketio


app, socketio = create_app()

if __name__ == '__main__':
    logger.info(f'WorldSim starting on port {Config.PORT}')
    socketio.run(app, host='0.0.0.0', port=Config.PORT, debug=Config.DEBUG)
