"""Scenario API routes"""
import os
import logging
from flask import Blueprint, request, jsonify
from models.database import get_session, Scenario
from services.file_parser import FileParser
from config import Config

logger = logging.getLogger(__name__)
scenario_bp = Blueprint('scenario', __name__)


@scenario_bp.route('', methods=['POST'])
def create_scenario():
    """Create a new scenario."""
    data = request.json or {}
    session = get_session()
    try:
        scenario = Scenario(
            name=data.get('name', '未命名场景'),
            background=data.get('background', ''),
            question=data.get('question', ''),
            rules=data.get('rules', ''),
            start_year=data.get('start_year', 2026),
            max_rounds=data.get('max_rounds', 5),
            entity_count=data.get('entity_count', 100),
            darkness_base=data.get('darkness_base', 0.0),
            pressure_base=data.get('pressure_base', 0.0),
            stability_base=data.get('stability_base', 50.0),
            hope_base=data.get('hope_base', 50.0),
            time_unit=data.get('time_unit', 'month'),
            total_duration=data.get('total_duration', 60),
            summary_interval=data.get('summary_interval', 6),
            ending_config=data.get('ending_config', {}),
            event_triggers=data.get('event_triggers', []),
        )
        session.add(scenario)
        session.commit()
        return jsonify({'id': scenario.id, 'status': scenario.status}), 201
    finally:
        session.close()


@scenario_bp.route('', methods=['GET'])
def list_scenarios():
    """List all scenarios."""
    session = get_session()
    try:
        scenarios = session.query(Scenario).order_by(Scenario.created_at.desc()).all()
        return jsonify([{
            'id': s.id, 'name': s.name, 'status': s.status,
            'entity_count': s.entity_count, 'max_rounds': s.max_rounds,
            'created_at': s.created_at.isoformat() if s.created_at else None,
        } for s in scenarios])
    finally:
        session.close()


@scenario_bp.route('/<int:scenario_id>', methods=['GET'])
def get_scenario(scenario_id):
    """Get scenario details."""
    session = get_session()
    try:
        scenario = session.query(Scenario).get(scenario_id)
        if not scenario:
            return jsonify({'error': 'Scenario not found'}), 404
        return jsonify({
            'id': scenario.id, 'name': scenario.name,
            'background': scenario.background, 'question': scenario.question,
            'rules': scenario.rules, 'status': scenario.status,
            'start_year': scenario.start_year, 'max_rounds': scenario.max_rounds,
            'entity_count': scenario.entity_count,
            'narrator_persona': scenario.narrator_persona,
            'uploaded_files': scenario.uploaded_files or [],
            'darkness_base': scenario.darkness_base,
            'pressure_base': scenario.pressure_base,
            'stability_base': scenario.stability_base,
            'hope_base': scenario.hope_base,
            'time_unit': scenario.time_unit or 'month',
            'total_duration': scenario.total_duration or 60,
            'summary_interval': scenario.summary_interval or 6,
            'ending_config': scenario.ending_config or {},
            'event_triggers': scenario.event_triggers or [],
        })
    finally:
        session.close()


@scenario_bp.route('/<int:scenario_id>', methods=['PUT'])
def update_scenario(scenario_id):
    """Update scenario."""
    data = request.json or {}
    session = get_session()
    try:
        scenario = session.query(Scenario).get(scenario_id)
        if not scenario:
            return jsonify({'error': 'Scenario not found'}), 404
        for field in ('name', 'background', 'question', 'rules', 'start_year',
                       'max_rounds', 'entity_count', 'narrator_persona',
                       'darkness_base', 'pressure_base',
                       'stability_base', 'hope_base',
                       'time_unit', 'total_duration', 'summary_interval',
                       'ending_config', 'event_triggers', 'status'):
            if field in data:
                setattr(scenario, field, data[field])
        session.commit()
        return jsonify({'id': scenario.id, 'status': scenario.status})
    finally:
        session.close()


@scenario_bp.route('/<int:scenario_id>', methods=['DELETE'])
def delete_scenario(scenario_id):
    """Delete scenario and all related data."""
    session = get_session()
    try:
        scenario = session.query(Scenario).get(scenario_id)
        if not scenario:
            return jsonify({'error': 'Scenario not found'}), 404
        session.delete(scenario)
        session.commit()
        return jsonify({'deleted': True})
    finally:
        session.close()


@scenario_bp.route('/<int:scenario_id>/upload', methods=['POST'])
def upload_files(scenario_id):
    """Upload reference files (PDF/TXT/MD)."""
    session = get_session()
    try:
        scenario = session.query(Scenario).get(scenario_id)
        if not scenario:
            return jsonify({'error': 'Scenario not found'}), 404

        files = request.files.getlist('files')
        if not files:
            return jsonify({'error': 'No files provided'}), 400

        Config.ensure_dirs()
        uploaded = scenario.uploaded_files or []
        parsed_results = []

        for f in files:
            ext = os.path.splitext(f.filename)[1].lower().lstrip('.')
            if ext not in Config.ALLOWED_EXTENSIONS:
                return jsonify({'error': f'Unsupported file type: {ext}'}), 400

            save_path = Config.UPLOAD_DIR / f'{scenario_id}_{f.filename}'
            f.save(str(save_path))

            # Parse immediately
            try:
                text = FileParser.extract_text(str(save_path))
                file_info = {
                    'filename': f.filename,
                    'path': str(save_path),
                    'parsed_text': text,
                    'char_count': len(text),
                }
                uploaded.append(file_info)
                parsed_results.append({'filename': f.filename, 'char_count': len(text)})
            except Exception as e:
                logger.error(f'Parse failed for {f.filename}: {e}')
                return jsonify({'error': f'Failed to parse {f.filename}: {str(e)}'}), 500

        scenario.uploaded_files = uploaded
        session.commit()
        return jsonify({'uploaded': parsed_results})
    finally:
        session.close()


@scenario_bp.route('/<int:scenario_id>/parse-rules', methods=['POST'])
def parse_rules_from_files(scenario_id):
    """Use LLM to extract world rules from uploaded files."""
    session = get_session()
    try:
        scenario = session.query(Scenario).get(scenario_id)
        if not scenario:
            return jsonify({'error': 'Scenario not found'}), 404

        uploaded = scenario.uploaded_files or []
        if not uploaded:
            return jsonify({'error': 'No uploaded files'}), 400

        # Combine all parsed text (limit to first 3000 chars)
        combined = '\n\n'.join(f.get('parsed_text', '')[:1500] for f in uploaded[:3])
        combined = combined[:3000]

        from services.llm_client import llm_client
        rules_text = llm_client.call([
            {'role': 'system', 'content': '你是世界推演规则提取专家。从提供的素材中提炼出5-10条世界规则。'},
            {'role': 'user', 'content': f'从以下素材中提取推演世界规则（每行一条，简洁）：\n\n{combined}'},
        ])

        scenario.rules = rules_text
        session.commit()
        return jsonify({'rules': rules_text})
    finally:
        session.close()


def register_scenario_socket(socketio):
    """Register scenario-related socket events."""
    pass
