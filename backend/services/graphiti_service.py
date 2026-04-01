"""Knowledge Graph Service using Kuzu (synchronous API)

Three-layer relationship injection (inspired by MiroFish's Zep GraphRAG):
  Layer 1: Faction-based initial relationships (entity generation time)
  Layer 2: Document-based relationships (from uploaded reference files)
  Layer 3: Simulation-event relationships (decisions + resolutions + LLM extraction)
"""
import logging
import uuid as _uuid
from config import Config

logger = logging.getLogger(__name__)
import kuzu


class KnowledgeGraphService:
    """Synchronous knowledge graph backed by Kuzu for WorldSim."""

    def __init__(self):
        self.db = None
        self.conn = None
        self.enabled = False
        self._initialized = False

    def _ensure_init(self):
        if self._initialized:
            return
        self._initialized = True
        try:
            db_path = str(Config.DATA_DIR / 'knowledge.kuzu')
            self.db = kuzu.Database(db_path)
            self.conn = kuzu.Connection(self.db)
            self._create_schema()
            self.enabled = True
            logger.info('Knowledge graph initialized with Kuzu at %s', db_path)
        except Exception as exc:
            logger.error('Knowledge graph init failed: %s', exc)
            self.enabled = False

    def _create_schema(self):
        for ddl in [
            ("CREATE NODE TABLE IF NOT EXISTS Entity("
             "uuid STRING PRIMARY KEY, name STRING, type STRING, "
             "faction STRING, summary STRING, group_id STRING)"),
            ("CREATE NODE TABLE IF NOT EXISTS Event("
             "uuid STRING PRIMARY KEY, name STRING, content STRING, "
             "event_type STRING, year INT64, round_num INT64, group_id STRING)"),
            ("CREATE REL TABLE IF NOT EXISTS RELATES_TO("
             "FROM Entity TO Entity, fact STRING, year INT64, round_num INT64)"),
            ("CREATE REL TABLE IF NOT EXISTS INVOLVED_IN("
             "FROM Entity TO Event, role STRING)"),
        ]:
            try:
                self.conn.execute(ddl)
            except Exception:
                pass

    # -- helpers ------------------------------------------------------------

    @staticmethod
    def _uid():
        return str(_uuid.uuid4())

    def _esc(self, s):
        return str(s).replace("'", "''")[:500]

    def _gid(self, scenario_id):
        return f'worldsim_{scenario_id}'

    def _get_entity_names(self, scenario_id, limit=300):
        """Get all entity names for a scenario."""
        self._ensure_init()
        if not self.enabled:
            return []
        try:
            gid = self._gid(scenario_id)
            r = self.conn.execute(
                f"MATCH (e:Entity) WHERE e.group_id='{gid}' RETURN e.name AS name LIMIT {limit}"
            )
            return [row['name'] for row in r.get_as_df().to_dict('records')]
        except Exception:
            return []

    def _get_entities_by_faction(self, scenario_id):
        """Get entities grouped by faction."""
        self._ensure_init()
        if not self.enabled:
            return {}
        try:
            gid = self._gid(scenario_id)
            r = self.conn.execute(
                f"MATCH (e:Entity) WHERE e.group_id='{gid}' "
                f"RETURN e.name AS name, e.faction AS faction"
            )
            factions = {}
            for row in r.get_as_df().to_dict('records'):
                f = row['faction'] or 'unknown'
                factions.setdefault(f, []).append(row['name'])
            return factions
        except Exception:
            return {}

    # -- public API ---------------------------------------------------------

    def add_entity(self, scenario_id, entity_data):
        self._ensure_init()
        if not self.enabled:
            return
        try:
            uid = self._uid()
            gid = self._gid(scenario_id)
            name = self._esc(entity_data.get('name', '?'))
            etype = self._esc(entity_data.get('type', 'Person'))
            faction = self._esc(entity_data.get('faction', ''))
            desc = self._esc(entity_data.get('description', ''))
            self.conn.execute(
                f"CREATE (e:Entity {{uuid:'{uid}', name:'{name}', type:'{etype}', "
                f"faction:'{faction}', summary:'{desc}', group_id:'{gid}'}})"
            )
        except Exception as exc:
            logger.error('KG add_entity failed: %s', exc)

    def add_event(self, scenario_id, name, content, event_type, year, round_num):
        self._ensure_init()
        if not self.enabled:
            return
        try:
            uid = self._uid()
            gid = self._gid(scenario_id)
            self.conn.execute(
                f"CREATE (ev:Event {{uuid:'{uid}', name:'{self._esc(name)}', "
                f"content:'{self._esc(content)}', event_type:'{event_type}', "
                f"year:{int(year)}, round_num:{int(round_num)}, group_id:'{gid}'}})"
            )
        except Exception as exc:
            logger.error('KG add_event failed: %s', exc)

    def add_relationship(self, scenario_id, entity_a, entity_b, fact, year=0, round_num=0):
        self._ensure_init()
        if not self.enabled:
            return
        if not entity_a or not entity_b or entity_a == entity_b:
            return
        try:
            gid = self._gid(scenario_id)
            self.conn.execute(
                f"MATCH (a:Entity {{name:'{self._esc(entity_a)}', group_id:'{gid}'}}),"
                f"      (b:Entity {{name:'{self._esc(entity_b)}', group_id:'{gid}'}}) "
                f"CREATE (a)-[:RELATES_TO {{fact:'{self._esc(fact)}', "
                f"year:{int(year)}, round_num:{int(round_num)}}}]->(b)"
            )
        except Exception as exc:
            logger.error('KG add_relationship failed: %s', exc)

    def link_entity_event(self, scenario_id, entity_name, event_name, role='participant'):
        self._ensure_init()
        if not self.enabled:
            return
        try:
            gid = self._gid(scenario_id)
            self.conn.execute(
                f"MATCH (e:Entity {{name:'{self._esc(entity_name)}', group_id:'{gid}'}}),"
                f"      (ev:Event {{name:'{self._esc(event_name)}', group_id:'{gid}'}}) "
                f"CREATE (e)-[:INVOLVED_IN {{role:'{self._esc(role)}'}}]->(ev)"
            )
        except Exception as exc:
            logger.error('KG link_entity_event failed: %s', exc)

    # -- Layer 1: Faction-based initial relationships -----------------------

    def build_initial_relationships(self, scenario_id):
        """Build initial relationships based on factions and entity descriptions.
        Called after entity generation.
        """
        self._ensure_init()
        if not self.enabled:
            return

        factions = self._get_entities_by_faction(scenario_id)
        if not factions:
            return

        # Same-faction relationships: allies / colleagues
        for faction_name, members in factions.items():
            for i in range(len(members)):
                # Connect each member to 2-3 random others in same faction
                for j in range(i + 1, min(i + 3, len(members))):
                    self.add_relationship(
                        scenario_id, members[i], members[j],
                        f'{faction_name}盟友', 0, 0,
                    )

        # Cross-faction: pick 1-2 entities from each faction pair
        faction_names = list(factions.keys())
        for i in range(len(faction_names)):
            for j in range(i + 1, len(faction_names)):
                fa, fb = factions[faction_names[i]], factions[faction_names[j]]
                if fa and fb:
                    self.add_relationship(
                        scenario_id, fa[0], fb[0],
                        f'{faction_names[i]}与{faction_names[j]}博弈', 0, 0,
                    )

        logger.info(f'KG initial relationships built: {len(factions)} factions')

    # -- Layer 2: Document-based relationships ------------------------------

    def extract_from_documents(self, scenario_id, documents_text):
        """Extract entity relationships from uploaded reference documents.
        Splits text into chunks and extracts relationships from each chunk.
        """
        self._ensure_init()
        if not self.enabled or not documents_text:
            return

        known_names = self._get_entity_names(scenario_id)
        if len(known_names) < 2:
            return

        # Split into ~800-char chunks
        chunk_size = 800
        chunks = [documents_text[i:i + chunk_size] for i in range(0, len(documents_text), chunk_size)]
        # Process up to 8 chunks (most impactful parts)
        chunks = chunks[:8]

        from services.llm_client import llm_client
        names_str = ', '.join(known_names[:60])

        for idx, chunk in enumerate(chunks):
            try:
                result = llm_client.call_json([
                    {'role': 'system', 'content': '从文本中提取实体间关系。只输出JSON。'},
                    {'role': 'user', 'content': (
                        f'已知实体: {names_str}\n\n'
                        f'文本片段:\n{chunk}\n\n'
                        f'提取文本中提到的实体间关系（可以包含不在已知列表中的隐含关系）:\n'
                        f'{{"relations":[{{"a":"实体A","b":"实体B","rel":"关系"}}]}}\n'
                        f'最多8条关系，每条rel不超过20字。'
                    )},
                ], temperature=0.2, max_tokens=512)

                added = 0
                for rel in result.get('relations', []):
                    a, b = rel.get('a', ''), rel.get('b', '')
                    fact = rel.get('rel', '')
                    if a and b and fact:
                        # Allow if at least one entity is known
                        if a in known_names or b in known_names:
                            self.add_relationship(scenario_id, a, b, f'文档:{fact}', 0, 0)
                            added += 1

                logger.info(f'KG doc chunk {idx}: extracted {added} relationships')
                import time
                time.sleep(0.1)
            except Exception as exc:
                logger.debug(f'KG doc chunk {idx} failed (non-critical): {exc}')

    # -- Layer 3: Simulation-event relationships ----------------------------

    def add_entity_episode(self, scenario_id, entity_data):
        self.add_entity(scenario_id, entity_data)

    def add_decision_episode(self, scenario_id, decision, year, round_num):
        entity = decision.get('entity', '?')
        action = decision.get('action', '?')
        target = decision.get('target', '')
        thought = decision.get('thought', '')
        content = f"{entity}决定: {action} → {target} (思考: {thought})"
        event_name = f'decision_{entity}_r{round_num}'
        self.add_event(scenario_id, event_name, content, 'decision', year, round_num)
        self.link_entity_event(scenario_id, entity, event_name, 'decision_maker')
        if target:
            self.link_entity_event(scenario_id, target, event_name, 'target')
            self.add_relationship(scenario_id, entity, target, action or '作用于', year, round_num)

    def add_resolution_episode(self, scenario_id, resolution, year, round_num):
        self.add_event(scenario_id, f'resolution_r{round_num}',
                       resolution, 'resolution', year, round_num)
        # Extract entity relationships from resolution text
        self._extract_relationships(scenario_id, resolution, year, round_num)

    def add_episode(self, scenario_id, name, content, year, round_num):
        self.add_event(scenario_id, name, content, 'episode', year, round_num)

    def _extract_relationships(self, scenario_id, text, year, round_num):
        """Use LLM to extract entity relationships from text and add to graph."""
        if not self.enabled or not text:
            return
        try:
            known_names = self._get_entity_names(scenario_id)
            if len(known_names) < 2:
                return

            names_str = ', '.join(known_names[:50])
            from services.llm_client import llm_client
            result = llm_client.call_json([
                {'role': 'system', 'content': '从文本中提取实体间关系。只输出JSON。'},
                {'role': 'user', 'content': (
                    f'已知实体: {names_str}\n\n'
                    f'文本: {text[:600]}\n\n'
                    f'提取文本中出现的实体间关系:\n'
                    f'{{"relations":[{{"a":"实体A","b":"实体B","rel":"关系描述"}}]}}\n'
                    f'最多10条关系，rel不超过15字。'
                )},
            ], temperature=0.2, max_tokens=512)

            for rel in result.get('relations', []):
                a, b = rel.get('a', ''), rel.get('b', '')
                fact = rel.get('rel', '')
                if a and b and fact and a in known_names and b in known_names:
                    self.add_relationship(scenario_id, a, b, fact, year, round_num)
        except Exception as exc:
            logger.debug('KG extract_relationships failed (non-critical): %s', exc)

    # -- Search -------------------------------------------------------------

    def search(self, scenario_id, query, num_results=10):
        self._ensure_init()
        if not self.enabled:
            return []
        try:
            gid = self._gid(scenario_id)
            r = self.conn.execute(
                f"MATCH (a:Entity)-[r:RELATES_TO]->(b:Entity) "
                f"WHERE a.group_id='{gid}' AND r.fact CONTAINS '{self._esc(query)}' "
                f"RETURN a.name AS source, b.name AS target, r.fact AS fact "
                f"LIMIT {num_results}"
            )
            return r.get_as_df().to_dict('records')
        except Exception as exc:
            logger.error('KG search failed: %s', exc)
            return []

    # -- Visualisation data for D3.js --------------------------------------

    def get_graph_data(self, scenario_id):
        self._ensure_init()
        if not self.enabled:
            return {'nodes': [], 'edges': [], 'communities': []}
        try:
            gid = self._gid(scenario_id)

            nodes_r = self.conn.execute(
                f"MATCH (e:Entity) WHERE e.group_id='{gid}' "
                f"RETURN e.uuid AS id, e.name AS name, e.type AS type, "
                f"e.faction AS faction, e.summary AS summary")
            nodes = nodes_r.get_as_df().to_dict('records')

            edges_r = self.conn.execute(
                f"MATCH (a:Entity)-[r:RELATES_TO]->(b:Entity) "
                f"WHERE a.group_id='{gid}' "
                f"RETURN a.uuid AS source, b.uuid AS target, "
                f"a.name AS sourceName, b.name AS targetName, r.fact AS fact")
            edges = edges_r.get_as_df().to_dict('records')

            events_r = self.conn.execute(
                f"MATCH (e:Event) WHERE e.group_id='{gid}' "
                f"AND e.event_type <> 'decision' "
                f"RETURN e.uuid AS id, e.name AS name, e.event_type AS type, "
                f"e.year AS year, e.round_num AS round")
            events = events_r.get_as_df().to_dict('records')

            # Only get INVOLVED_IN for non-decision events
            ee_r = self.conn.execute(
                f"MATCH (e:Entity)-[r:INVOLVED_IN]->(ev:Event) "
                f"WHERE e.group_id='{gid}' AND ev.event_type <> 'decision' "
                f"RETURN e.uuid AS source, ev.uuid AS target, "
                f"e.name AS sourceName, ev.name AS targetName, r.role AS fact")
            ee = ee_r.get_as_df().to_dict('records')

            # Convert int64 to int for JSON serialization
            for node in nodes + events:
                for k, v in node.items():
                    if hasattr(v, 'item'):
                        node[k] = v.item()
            for edge in edges + ee:
                for k, v in edge.items():
                    if hasattr(v, 'item'):
                        edge[k] = v.item()

            return {
                'nodes': nodes + events,
                'edges': edges + ee,
                'communities': [],
            }
        except Exception as exc:
            logger.error('KG get_graph_data failed: %s', exc)
            return {'nodes': [], 'edges': [], 'communities': []}

    def search_full(self, scenario_id, query):
        self._ensure_init()
        if not self.enabled:
            return {'nodes': [], 'edges': [], 'episodes': []}
        try:
            gid = self._gid(scenario_id)
            sq = self._esc(query)
            nodes_r = self.conn.execute(
                f"MATCH (e:Entity) WHERE e.group_id='{gid}' "
                f"AND (e.name CONTAINS '{sq}' OR e.summary CONTAINS '{sq}') "
                f"RETURN e.uuid AS id, e.name AS name, e.summary AS summary")
            edges_r = self.conn.execute(
                f"MATCH (a:Entity)-[r:RELATES_TO]->(b:Entity) "
                f"WHERE a.group_id='{gid}' AND r.fact CONTAINS '{sq}' "
                f"RETURN a.uuid AS source, b.uuid AS target, r.fact AS fact")
            return {
                'nodes': nodes_r.get_as_df().to_dict('records'),
                'edges': edges_r.get_as_df().to_dict('records'),
                'episodes': [],
            }
        except Exception as exc:
            logger.error('KG search_full failed: %s', exc)
            return {'nodes': [], 'edges': [], 'episodes': []}


# Singleton — no heavy work at import time
graphiti_service = KnowledgeGraphService()
