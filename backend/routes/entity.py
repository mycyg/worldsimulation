"""Entity/Character Card API routes"""
import logging
from flask import Blueprint, request, jsonify
from models.database import get_session, Entity, Scenario
from services.entity_generator import EntityGenerator

logger = logging.getLogger(__name__)
entity_bp = Blueprint('entity', __name__)


@entity_bp.route('/scenarios/<int:scenario_id>/entities', methods=['GET'])
def list_entities(scenario_id):
    """List all entities for a scenario."""
    session = get_session()
    try:
        entities = session.query(Entity).filter_by(scenario_id=scenario_id).all()
        # Group by faction
        factions = {}
        for e in entities:
            faction = e.faction or '未分组'
            if faction not in factions:
                factions[faction] = []
            factions[faction].append({
                'id': e.id, 'name': e.name, 'type': e.type,
                'faction': e.faction, 'description': e.description,
                'personality': e.personality, 'motivation': e.motivation,
                'initial_status': e.initial_status, 'prominence': e.prominence,
                'persona': e.persona, 'appearance': e.appearance,
                'speech_style': e.speech_style, 'tags': e.tags,
                'status': e.status, 'resources': e.resources,
                'pressure': e.pressure, 'current_state': e.current_state,
                'short_term_goal': e.short_term_goal,
                'long_term_goal': e.long_term_goal,
                'short_term_urgency': e.short_term_urgency,
                'backstory': e.backstory,
                'pressure_desc': e.pressure_desc,
                'influence': e.influence,
            })
        return jsonify({
            'total': len(entities),
            'factions': factions,
        })
    finally:
        session.close()


@entity_bp.route('/scenarios/<int:scenario_id>/generate', methods=['POST'])
def generate_entities(scenario_id):
    """Trigger batch entity generation for a scenario."""
    session = get_session()
    try:
        scenario = session.query(Scenario).get(scenario_id)
        if not scenario:
            return jsonify({'error': 'Scenario not found'}), 404

        # Clear existing entities
        session.query(Entity).filter_by(scenario_id=scenario_id).delete()
        session.commit()

        # Start generation (synchronous for now)
        generator = EntityGenerator()
        # Extract document content separately for entity grounding
        documents_text = ''
        uploaded = scenario.uploaded_files or []
        if uploaded:
            documents_text = '\n\n'.join(
                f'=== {f.get("filename", "文档")} ===\n{f.get("parsed_text", "")[:2000]}'
                for f in uploaded[:3]
            )[:6000]

        result = generator.generate_all(
            background=scenario.background,
            question=scenario.question,
            entity_count=scenario.entity_count,
            documents=documents_text,
        )

        # Save entities
        entities = []
        for raw in result['entities']:
            # Calculate influence from type/prominence if LLM didn't provide meaningful value
            influence = raw.get('influence', 50.0)
            if not influence or influence == 50.0 or influence == 50:
                import math
                etype = raw.get('type', 'Person')
                prominence = raw.get('prominence', 5)
                # log10 scale: person~50 people=17, org~10K=40, institution~1M=60, force~100M=80
                base_people = {'Person': 50, 'Organization': 10000, 'Institution': 1000000, 'Force': 100000000}
                count = base_people.get(etype, 50) * (0.5 + prominence * 0.25)
                influence = round(math.log10(max(count, 1)) * 10, 1)
            entity = Entity(
                scenario_id=scenario_id,
                name=raw['name'],
                type=raw.get('type', 'Person'),
                faction=raw.get('faction', ''),
                personality=raw.get('personality', ''),
                motivation=raw.get('motivation', ''),
                description=raw.get('description', ''),
                initial_status=raw.get('initial_status', ''),
                prominence=raw.get('prominence', 5),
                persona=raw.get('persona', ''),
                appearance=raw.get('appearance', ''),
                speech_style=raw.get('speech_style', ''),
                tags=raw.get('tags', ''),
                current_state=raw.get('initial_status', ''),
                pressure=raw.get('pressure', 50.0),
                short_term_goal=raw.get('short_term_goal', ''),
                long_term_goal=raw.get('long_term_goal', ''),
                short_term_urgency=raw.get('short_term_urgency', 30.0),
                backstory=raw.get('backstory', ''),
                pressure_desc=raw.get('pressure_desc', ''),
                influence=influence,
            )
            session.add(entity)
            entities.append(raw)

        scenario.narrator_persona = result.get('narrator_persona', '客观描述局势')
        scenario.status = 'ready'
        session.commit()

        return jsonify({
            'total': len(entities),
            'narrator_persona': scenario.narrator_persona,
            'factions': result.get('factions_summary', {}),
        })
    except Exception as e:
        session.rollback()
        logger.error(f'Entity generation failed: {e}')
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@entity_bp.route('/entities/<int:entity_id>', methods=['PUT'])
def update_entity(entity_id):
    """Edit a character card."""
    data = request.json or {}
    session = get_session()
    try:
        entity = session.query(Entity).get(entity_id)
        if not entity:
            return jsonify({'error': 'Entity not found'}), 404
        for field in ('name', 'type', 'faction', 'personality', 'motivation',
                       'description', 'initial_status', 'prominence',
                       'persona', 'appearance', 'speech_style', 'tags',
                       'backstory', 'pressure_desc'):
            if field in data:
                setattr(entity, field, data[field])
        if 'influence' in data:
            entity.influence = data['influence']
        session.commit()
        return jsonify({'id': entity.id, 'name': entity.name})
    finally:
        session.close()


@entity_bp.route('/entities/<int:entity_id>', methods=['DELETE'])
def delete_entity(entity_id):
    """Delete an entity."""
    session = get_session()
    try:
        entity = session.query(Entity).get(entity_id)
        if not entity:
            return jsonify({'error': 'Entity not found'}), 404
        session.delete(entity)
        session.commit()
        return jsonify({'deleted': True})
    finally:
        session.close()


@entity_bp.route('/scenarios/<int:scenario_id>/entities', methods=['POST'])
def add_entity(scenario_id):
    """Manually add a single entity."""
    data = request.json or {}
    session = get_session()
    try:
        entity = Entity(
            scenario_id=scenario_id,
            name=data.get('name', '未命名'),
            type=data.get('type', 'Person'),
            faction=data.get('faction', ''),
            personality=data.get('personality', ''),
            motivation=data.get('motivation', ''),
            description=data.get('description', ''),
            initial_status=data.get('initial_status', ''),
            prominence=data.get('prominence', 5),
            persona=data.get('persona', ''),
            appearance=data.get('appearance', ''),
            speech_style=data.get('speech_style', ''),
            tags=data.get('tags', ''),
            current_state=data.get('initial_status', ''),
        )
        session.add(entity)
        session.commit()
        return jsonify({'id': entity.id, 'name': entity.name}), 201
    finally:
        session.close()
