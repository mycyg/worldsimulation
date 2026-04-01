"""Report API routes"""
import logging
from flask import Blueprint, request, jsonify, send_file
from models.database import get_session, Scenario, Report
from services.report_generator import ReportGenerator

logger = logging.getLogger(__name__)
report_bp = Blueprint('report', __name__)


@report_bp.route('/<int:scenario_id>', methods=['GET'])
def get_report(scenario_id):
    session = get_session()
    try:
        report = session.query(Report).filter_by(scenario_id=scenario_id).first()
        if not report:
            return jsonify({'error': 'Report not found'}), 404
        return jsonify({
            'id': report.id,
            'content': report.content,
            'ending_type': report.ending_type,
            'created_at': report.created_at.isoformat() if report.created_at else None,
        })
    finally:
        session.close()


@report_bp.route('/<int:scenario_id>/generate', methods=['POST'])
def generate_report(scenario_id):
    session = get_session()
    try:
        scenario = session.query(Scenario).get(scenario_id)
        if not scenario:
            return jsonify({'error': 'Scenario not found'}), 404
        session.close()

        generator = ReportGenerator()
        result = generator.generate(scenario_id)

        return jsonify(result)
    except Exception as e:
        logger.error(f'Report generation failed: {e}')
        return jsonify({'error': str(e)}), 500
    finally:
        try:
            session.close()
        except:
            pass


@report_bp.route('/<int:scenario_id>/export/<format>', methods=['GET'])
def export_report(scenario_id, format):
    """Export report as md or txt."""
    session = get_session()
    try:
        report = session.query(Report).filter_by(scenario_id=scenario_id).first()
        if not report:
            return jsonify({'error': 'Report not found'}), 404

        content = report.content
        filename = f'worldsim_report_{scenario_id}.{format}'

        import tempfile
        tmp = tempfile.NamedTemporaryFile(mode='w', suffix=f'.{format}',
                                           encoding='utf-8', delete=False)
        tmp.write(content)
        tmp.close()

        return send_file(tmp.name, as_attachment=True, download_name=filename)
    finally:
        session.close()
