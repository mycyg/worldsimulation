"""Zep Knowledge Graph Service

Integrates with Zep Cloud for temporal knowledge graph during simulation.
"""
import logging
from config import Config

logger = logging.getLogger(__name__)


class ZepService:
    """Wraps Zep Cloud SDK for world simulation knowledge graph."""

    def __init__(self):
        self.client = None
        self.enabled = bool(Config.ZEP_API_KEY)
        if self.enabled:
            try:
                from zep_cloud.client import Zep
                self.client = Zep(api_key=Config.ZEP_API_KEY)
                logger.info('Zep Cloud client initialized')
            except ImportError:
                logger.warning('zep-cloud package not installed, knowledge graph disabled')
                self.enabled = False
            except Exception as e:
                logger.error(f'Zep init failed: {e}')
                self.enabled = False

    def _get_graph_id(self, scenario_id):
        return f'worldsim_{scenario_id}'

    def add_entity(self, scenario_id, entity_data):
        """Add an entity to the knowledge graph."""
        if not self.enabled:
            return
        try:
            graph_id = self._get_graph_id(scenario_id)
            name = entity_data.get('name', 'Unknown')
            facts = [
                f'{name} is a {entity_data.get("type", "Person")} in faction {entity_data.get("faction", "unknown")}',
                f'{name} motivation: {entity_data.get("motivation", "")}',
                f'{name} initial status: {entity_data.get("initial_status", "")}',
            ]
            for fact in facts:
                if fact and len(fact) > 20:
                    self.client.graph.add(
                        user_id=graph_id,
                        data=fact,
                        type='text',
                    )
        except Exception as e:
            logger.error(f'Zep add_entity failed: {e}')

    def add_event(self, scenario_id, event_text, year, round_num):
        """Add a timeline event to the knowledge graph."""
        if not self.enabled:
            return
        try:
            graph_id = self._get_graph_id(scenario_id)
            self.client.graph.add(
                user_id=graph_id,
                data=f'Year {year} (Round {round_num}): {event_text}',
                type='text',
            )
        except Exception as e:
            logger.error(f'Zep add_event failed: {e}')

    def add_relationship(self, scenario_id, entity_a, entity_b, relation):
        """Record a relationship between entities."""
        if not self.enabled:
            return
        try:
            graph_id = self._get_graph_id(scenario_id)
            self.client.graph.add(
                user_id=graph_id,
                data=f'{entity_a} {relation} {entity_b}',
                type='text',
            )
        except Exception as e:
            logger.error(f'Zep add_relationship failed: {e}')

    def query_context(self, scenario_id, query):
        """Query relevant context from knowledge graph."""
        if not self.enabled:
            return ''
        try:
            graph_id = self._get_graph_id(scenario_id)
            result = self.client.graph.search(
                user_id=graph_id,
                query=query,
            )
            if result and result.edges:
                return '\n'.join(e.fact for e in result.edges[:5])
            return ''
        except Exception as e:
            logger.error(f'Zep query failed: {e}')
            return ''

    def get_entity_history(self, scenario_id, entity_name):
        """Get entity history from knowledge graph."""
        if not self.enabled:
            return ''
        try:
            return self.query_context(scenario_id, f'{entity_name} 的历史和变化')
        except Exception as e:
            logger.error(f'Zep entity history failed: {e}')
            return ''


# Singleton
zep_service = ZepService()
