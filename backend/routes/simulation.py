"""Simulation API routes"""
import logging
from flask import Blueprint, request, jsonify
from models.database import get_session, Scenario
from services.simulation_engine import SimulationEngine
from services.graphiti_service import graphiti_service

logger = logging.getLogger(__name__)
simulation_bp = Blueprint('simulation', __name__)

# Active simulation engines
_engines = {}


def get_engine(scenario_id):
    if scenario_id not in _engines:
        _engines[scenario_id] = SimulationEngine(scenario_id)
    return _engines[scenario_id]


@simulation_bp.route('/<int:scenario_id>/start', methods=['POST'])
def start_simulation(scenario_id):
    """Start simulation."""
    session = get_session()
    try:
        scenario = session.query(Scenario).get(scenario_id)
        if not scenario:
            return jsonify({'error': 'Scenario not found'}), 404
        if scenario.status not in ('ready', 'paused'):
            return jsonify({'error': f'Cannot start from status: {scenario.status}'}), 400
        session.close()
    except:
        session.close()
        raise

    engine = get_engine(scenario_id)
    engine.start()
    return jsonify({'status': 'running'})


@simulation_bp.route('/<int:scenario_id>/pause', methods=['POST'])
def pause_simulation(scenario_id):
    engine = get_engine(scenario_id)
    engine.pause()
    return jsonify({'status': 'paused'})


@simulation_bp.route('/<int:scenario_id>/resume', methods=['POST'])
def resume_simulation(scenario_id):
    engine = get_engine(scenario_id)
    engine.resume()
    return jsonify({'status': 'running'})


@simulation_bp.route('/<int:scenario_id>/stop', methods=['POST'])
def stop_simulation(scenario_id):
    engine = get_engine(scenario_id)
    engine.stop()
    return jsonify({'status': 'stopped'})


@simulation_bp.route('/<int:scenario_id>/reset', methods=['POST'])
def reset_simulation(scenario_id):
    """Reset simulation: clear all rounds/decisions/timeline/metrics, restore entities."""
    session = get_session()
    try:
        scenario = session.query(Scenario).get(scenario_id)
        if not scenario:
            return jsonify({'error': 'Scenario not found'}), 404

        from models.database import Round, Decision, TimelineEvent, MetricsHistory, Report, Entity

        # Delete all rounds (cascades to decisions)
        rounds = session.query(Round).filter_by(scenario_id=scenario_id).all()
        for r in rounds:
            session.query(Decision).filter_by(round_id=r.id).delete()
        session.query(Round).filter_by(scenario_id=scenario_id).delete()

        # Delete timeline, metrics, report
        session.query(TimelineEvent).filter_by(scenario_id=scenario_id).delete()
        session.query(MetricsHistory).filter_by(scenario_id=scenario_id).delete()
        session.query(Report).filter_by(scenario_id=scenario_id).delete()

        # Reset entity states to initial
        entities = session.query(Entity).filter_by(scenario_id=scenario_id).all()
        for e in entities:
            e.status = 'active'
            e.resources = 100
            e.pressure = 50.0
            e.current_state = e.initial_status or ''
            e.short_term_urgency = 30.0
            # Keep influence as-is (set during generation based on entity type)
            e.influence_history = []

        scenario.status = 'ready'
        session.commit()

        # Remove stale engine
        _engines.pop(scenario_id, None)

        return jsonify({'status': 'ready'})
    except Exception as e:
        session.rollback()
        logger.error(f'Reset failed: {e}')
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@simulation_bp.route('/<int:scenario_id>/inject', methods=['POST'])
def inject_event(scenario_id):
    data = request.json or {}
    event_text = data.get('event', '').strip()
    if not event_text:
        return jsonify({'error': 'No event provided'}), 400
    engine = get_engine(scenario_id)
    engine.inject_event(event_text)
    return jsonify({'injected': True})


@simulation_bp.route('/<int:scenario_id>/state', methods=['GET'])
def get_state(scenario_id):
    session = get_session()
    try:
        scenario = session.query(Scenario).get(scenario_id)
        if not scenario:
            return jsonify({'error': 'Scenario not found'}), 404

        from models.database import Round, MetricsHistory, TimelineEvent
        latest_round = session.query(Round).filter_by(scenario_id=scenario_id)\
            .order_by(Round.round_number.desc()).first()

        metrics = session.query(MetricsHistory).filter_by(scenario_id=scenario_id)\
            .order_by(MetricsHistory.id.desc()).all()

        return jsonify({
            'status': scenario.status,
            'current_tick': latest_round.round_number if latest_round else 0,
            'total_ticks': scenario.total_duration or 60,
            'current_year': latest_round.year if latest_round else scenario.start_year,
            'current_date': latest_round.tick_date if latest_round else '',
            'start_year': scenario.start_year,
            'time_unit': scenario.time_unit or 'month',
            'summary_interval': scenario.summary_interval or 6,
            'max_rounds': scenario.max_rounds,
            'metrics': [{
                'darkness': m.darkness, 'pressure': m.pressure,
                'stability': m.stability, 'hope': m.hope,
                'round': m.round_id,
            } for m in metrics],
        })
    finally:
        session.close()


@simulation_bp.route('/<int:scenario_id>/metrics', methods=['GET'])
def get_metrics(scenario_id):
    session = get_session()
    try:
        from models.database import MetricsHistory, Round
        metrics = session.query(MetricsHistory).filter_by(scenario_id=scenario_id)\
            .order_by(MetricsHistory.id).all()
        return jsonify([{
            'id': m.id, 'darkness': m.darkness, 'pressure': m.pressure,
            'stability': m.stability, 'hope': m.hope, 'notes': m.notes,
        } for m in metrics])
    finally:
        session.close()


@simulation_bp.route('/<int:scenario_id>/timeline', methods=['GET'])
def get_timeline(scenario_id):
    session = get_session()
    try:
        from models.database import TimelineEvent
        events = session.query(TimelineEvent).filter_by(scenario_id=scenario_id)\
            .order_by(TimelineEvent.round_number).all()
        return jsonify([{
            'id': e.id, 'type': e.event_type, 'content': e.content,
            'year': e.year, 'round': e.round_number,
            'event_date': e.event_date, 'is_major': e.is_major,
        } for e in events])
    finally:
        session.close()


@simulation_bp.route('/<int:scenario_id>/rounds', methods=['GET'])
def get_rounds(scenario_id):
    """Get all rounds with decisions for a scenario."""
    session = get_session()
    try:
        from models.database import Round, Decision, Entity
        rounds = session.query(Round).filter_by(scenario_id=scenario_id)\
            .order_by(Round.round_number).all()
        result = []
        for r in rounds:
            decisions = session.query(Decision).filter_by(round_id=r.id).all()
            decision_list = []
            action_outcomes = []
            for d in decisions:
                entity = session.query(Entity).get(d.entity_id)
                decision_list.append({
                    'entity': entity.name if entity else '?',
                    'thought': d.thought,
                    'action': d.action,
                    'target': d.target,
                    'expected_outcome': d.expected_outcome,
                    'desire': d.desire,
                    'fear': d.fear,
                    'urgency': d.urgency_level,
                })
                if d.actual_outcome:
                    action_outcomes.append({
                        'entity': entity.name if entity else '?',
                        'result': d.actual_outcome,
                    })
            result.append({
                'round': r.round_number,
                'year': r.year,
                'tick_date': r.tick_date or '',
                'is_summary': r.is_summary or False,
                'summary_text': r.summary_text or '',
                'situation': r.situation_summary,
                'resolution': r.resolution_summary,
                'decisions': decision_list,
                'actionOutcomes': action_outcomes,
                'phases': r.phases or {},
                'macro_indicators': r.macro_indicators,
                'metrics': {
                    'darkness': r.darkness_value,
                    'pressure': r.pressure_value,
                    'stability': r.stability_value,
                    'hope': r.hope_value,
                } if r.round_number > 0 else None,
            })
        return jsonify(result)
    finally:
        session.close()


def register_simulation_socket(socketio):
    """Register simulation socket events."""
    @socketio.on('connect')
    def handle_connect():
        logger.info('Client connected')

    @socketio.on('disconnect')
    def handle_disconnect():
        logger.info('Client disconnected')

    @socketio.on('join_scenario')
    def handle_join(data):
        from flask_socketio import join_room
        scenario_id = data.get('scenario_id')
        if scenario_id:
            join_room(f'scenario_{scenario_id}')


# --- Knowledge Graph API ---

@simulation_bp.route('/<int:scenario_id>/graph', methods=['GET'])
def get_graph(scenario_id):
    """Get knowledge graph data for D3.js visualisation."""
    data = graphiti_service.get_graph_data(scenario_id)
    return jsonify(data)


@simulation_bp.route('/<int:scenario_id>/graph/search', methods=['POST'])
def search_graph(scenario_id):
    """Search the knowledge graph."""
    query = (request.json or {}).get('query', '')
    if not query:
        return jsonify({'error': 'No query provided'}), 400
    results = graphiti_service.search_full(scenario_id, query)
    return jsonify(results)
