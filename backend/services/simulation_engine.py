"""Simulation Engine - Event-driven tick-based simulation

Each tick = 1 month. Entities act autonomously with timestamps.
Major events triggered by rules + LLM judgment. Periodic summaries.
"""
import random
import logging
import threading
import time
from models.database import (
    get_session, Scenario, Entity, Round, Decision,
    TimelineEvent, MetricsHistory
)
from services.llm_client import llm_client
from services.ending_system import EndingSystem
from services.graphiti_service import graphiti_service

logger = logging.getLogger(__name__)

ACTIVE_PER_TICK = 5


class SimulationEngine:
    def __init__(self, scenario_id):
        self.scenario_id = scenario_id
        self.running = False
        self.paused = False
        self.ending_system = EndingSystem()
        self.socketio = None
        self._recent_events = []
        self._init_socketio()

    def _init_socketio(self):
        try:
            from app import socketio
            self.socketio = socketio
        except Exception:
            logger.warning('SocketIO not available')

    def _emit(self, event, data):
        if self.socketio:
            self.socketio.emit(event, data, room=f'scenario_{self.scenario_id}')

    def start(self):
        self.running = True
        self.paused = False
        threading.Thread(target=self._run_loop, daemon=True).start()

    def pause(self):
        self.paused = True
        self._update_status('paused')
        self._emit('sim:progress', {'status': 'paused'})

    def resume(self):
        self.paused = False
        self._update_status('running')
        self._emit('sim:progress', {'status': 'running'})

    def stop(self):
        self.running = False
        self.paused = False
        self._update_status('ready')
        self._emit('sim:progress', {'status': 'stopped'})

    def inject_event(self, event_text):
        session = get_session()
        try:
            scenario = session.query(Scenario).get(self.scenario_id)
            tick = self._get_current_tick(session)
            year, month, date_str = self._tick_date(scenario.start_year, max(tick, 1))
            session.add(TimelineEvent(
                scenario_id=self.scenario_id, event_type='injected',
                content=f'[外部事件] {event_text}',
                year=year, round_number=tick, event_date=date_str,
            ))
            session.commit()
            self._emit('sim:round', {
                'type': 'injected', 'tick': tick,
                'year': year, 'month': month, 'date': date_str,
                'content': event_text,
            })
        finally:
            session.close()

    def _get_current_tick(self, session):
        latest = session.query(Round).filter_by(scenario_id=self.scenario_id)\
            .order_by(Round.round_number.desc()).first()
        return latest.round_number if latest else 0

    def _tick_date(self, start_year, tick):
        year = start_year + (tick - 1) // 12
        month = (tick - 1) % 12 + 1
        return year, month, f'{year}年{month}月'

    def _update_status(self, status):
        session = get_session()
        try:
            scenario = session.query(Scenario).get(self.scenario_id)
            if scenario:
                scenario.status = status
                session.commit()
        finally:
            session.close()

    # ------------------------------------------------------------------ #
    #  Main loop                                                          #
    # ------------------------------------------------------------------ #

    def _run_loop(self):
        session = get_session()
        try:
            scenario = session.query(Scenario).get(self.scenario_id)
            if not scenario:
                logger.error(f'Scenario {self.scenario_id} not found')
                return

            total_ticks = scenario.total_duration or 60
            summary_interval = scenario.summary_interval or 6
            self.ending_system.set_base(
                scenario.darkness_base, scenario.pressure_base,
                scenario.stability_base, scenario.hope_base,
            )
            if scenario.ending_config:
                self.ending_system.set_ending_config(scenario.ending_config)

            current_tick = self._get_current_tick(session)
            if current_tick == 0:
                self._generate_initial_state(session, scenario)
                start_tick = 1
            else:
                last_m = session.query(MetricsHistory)\
                    .filter_by(scenario_id=self.scenario_id)\
                    .order_by(MetricsHistory.id.desc()).first()
                if last_m:
                    self.ending_system.metrics = {
                        'darkness': last_m.darkness, 'pressure': last_m.pressure,
                        'stability': last_m.stability, 'hope': last_m.hope,
                    }
                start_tick = current_tick + 1
                self._update_status('running')

            macro_indicators = {}
            last_round = session.query(Round).filter_by(scenario_id=self.scenario_id)\
                .order_by(Round.round_number.desc()).first()
            if last_round and last_round.macro_indicators:
                macro_indicators = last_round.macro_indicators

            for tick in range(start_tick, total_ticks + 1):
                while self.paused and self.running:
                    time.sleep(0.5)
                if not self.running:
                    break

                year, month, date_str = self._tick_date(scenario.start_year, tick)
                entities = session.query(Entity).filter_by(scenario_id=self.scenario_id).all()
                self._emit('sim:progress', {
                    'status': 'running', 'tick': tick,
                    'total_ticks': total_ticks,
                    'year': year, 'month': month, 'date': date_str,
                })
                logger.info(f'--- Tick {tick} ({date_str}) ---')

                # 1. Situation
                situation = self._get_situation(
                    session, scenario, tick, year, month, entities, macro_indicators)
                # 2. Select entities
                active = self._select_tick_entities(entities, tick)
                # 3. Autonomous actions
                actions = self._generate_autonomous_actions(
                    active, situation, date_str, macro_indicators)
                # 4. Resolve
                resolution = self._resolve_tick(
                    session, scenario, tick, date_str, situation, actions, entities)
                # 5. Knowledge graph
                for d in actions:
                    graphiti_service.add_decision_episode(
                        self.scenario_id, d, year, tick)
                if resolution.get('summary'):
                    graphiti_service.add_resolution_episode(
                        self.scenario_id, resolution['summary'], year, tick)
                # 6. Extreme event check (low-influence, high-pressure entity)
                extreme = self._check_extreme_event(
                    entities, situation, date_str, macro_indicators)
                if extreme:
                    # Chain reaction: all active entities respond
                    chain_actions = self._trigger_chain_reaction(
                        entities, extreme, situation, date_str, macro_indicators)
                    actions = actions + chain_actions
                    major_event = extreme.get('event', '')
                    # Boost trigger entity's influence
                    trigger_name = extreme.get('entity', '')
                    for e in entities:
                        if e.name == trigger_name:
                            boost = random.randint(15, 30)
                            e.influence = min(100, (e.influence or 50) + boost)
                            logger.info(
                                f'Extreme event by {trigger_name}: '
                                f'influence +{boost}')
                            break
                # 7. Update entities
                self._update_entity_states(entities, actions, resolution, session)
                self._update_influence(entities, resolution, tick, session)
                # 7. Macro indicators
                decisions_text = '\n'.join(
                    f'{d["entity"]}: {d.get("action", "?")}' for d in actions)
                if macro_indicators:
                    macro_indicators = self._update_macro_indicators(
                        macro_indicators, situation, decisions_text,
                        resolution.get('summary', ''))
                    self._apply_macro_pressure(entities, macro_indicators, session)
                # 8. Metrics
                alive = [e for e in entities if e.status != 'dead']
                avg_ep = sum(e.pressure for e in alive) / max(len(alive), 1)
                metric_delta = self.ending_system.evaluate_tick(
                    situation, decisions_text,
                    resolution.get('summary', ''), date_str)
                metrics = self.ending_system.get_metrics()
                metrics['pressure'] = round(
                    metrics['pressure'] * 0.6 + avg_ep * 0.4, 1)

                # 9. Major events
                major_event = self._check_event_triggers(
                    session, scenario, tick, date_str, situation, actions)
                if not major_event and tick % 3 == 0:
                    major_event = self._llm_check_major_events(
                        situation, actions, date_str)
                if major_event:
                    self._recent_events.append(f'{date_str}: {major_event}')
                    if len(self._recent_events) > 10:
                        self._recent_events = self._recent_events[-10:]

                # 10. Save tick
                round_obj = Round(
                    scenario_id=self.scenario_id, round_number=tick,
                    year=year, tick_date=date_str,
                    situation_summary=situation,
                    darkness_value=metrics['darkness'],
                    pressure_value=metrics['pressure'],
                    stability_value=metrics['stability'],
                    hope_value=metrics['hope'],
                    macro_indicators=macro_indicators or {},
                    phases={'actions': actions},
                    resolution_summary=resolution.get('summary', ''),
                )
                session.add(round_obj)
                session.flush()

                outcomes = resolution.get('action_outcomes', [])
                outcome_map = {o.get('entity', ''): o for o in outcomes}
                for d in actions:
                    ent = next((e for e in entities
                                if e.name == d.get('entity', '')), None)
                    if ent:
                        actual = ''
                        oc = outcome_map.get(d.get('entity', ''), {})
                        if oc.get('result'):
                            actual = oc['result']
                            if oc.get('impact'):
                                actual += f'（{oc["impact"]}）'
                        session.add(Decision(
                            round_id=round_obj.id, entity_id=ent.id,
                            thought=d.get('thought', ''),
                            action=d.get('action', ''),
                            target=d.get('target', ''),
                            expected_outcome=d.get('expected_outcome', ''),
                            actual_outcome=actual,
                            desire=d.get('desire', ''),
                            fear=d.get('fear', ''),
                            urgency_level=d.get('urgency', 'normal'),
                            event_timestamp=d.get('timestamp', date_str),
                            is_major=d.get('is_major', False),
                            action_type=d.get('action_type', 'proactive'),
                        ))

                session.add(TimelineEvent(
                    scenario_id=self.scenario_id, round_id=round_obj.id,
                    event_type='narrative',
                    content=resolution.get('summary', ''),
                    year=year, round_number=tick, event_date=date_str,
                ))
                if major_event:
                    session.add(TimelineEvent(
                        scenario_id=self.scenario_id, round_id=round_obj.id,
                        event_type='major_event', content=major_event,
                        year=year, round_number=tick,
                        event_date=date_str, is_major=True,
                    ))
                session.add(MetricsHistory(
                    scenario_id=self.scenario_id, round_id=round_obj.id,
                    darkness=metrics['darkness'], pressure=metrics['pressure'],
                    stability=metrics['stability'], hope=metrics['hope'],
                    notes=metric_delta.get('notes', ''),
                ))
                session.commit()

                self._emit('sim:round', {
                    'type': 'tick_result', 'tick': tick,
                    'year': year, 'month': month, 'date': date_str,
                    'situation': situation,
                    'summary': resolution.get('summary', ''),
                    'decisions': actions,
                    'action_outcomes': outcomes,
                    'influence_changes': resolution.get('influence_changes', []),
                    'metrics': metrics,
                    'macro_indicators': macro_indicators,
                    'major_event': major_event,
                    'active_entities': [
                        {'name': e.name, 'status': e.status, 'faction': e.faction,
                         'pressure': round(e.pressure, 1),
                         'influence': round(e.influence, 1)}
                        for e in active
                    ],
                })
                self._emit('sim:metrics', metrics)

                # Periodic summary
                if tick % summary_interval == 0:
                    self._generate_period_summary(
                        session, scenario, tick, date_str)

                # Maybe spawn entities
                try:
                    self._maybe_spawn_entities(session, scenario, year, tick, resolution)
                except Exception as e:
                    logger.warning(f'Spawn entities error: {e}')

                # Check ending
                should_end, ending_type, reason = self.ending_system.check_ending(
                    tick, total_ticks)
                if should_end:
                    logger.info(f'Ending: {ending_type} - {reason}')
                    tl = self._get_timeline_summary(session)
                    desc = self.ending_system.get_ending_description(
                        ending_type, scenario.question, tl)
                    session.add(TimelineEvent(
                        scenario_id=self.scenario_id, round_id=round_obj.id,
                        event_type='ending',
                        content=f'[{ending_type.upper()} END] {desc}',
                        year=year, round_number=tick, event_date=date_str,
                    ))
                    scenario.status = 'done'
                    session.commit()
                    self._emit('sim:ending', {
                        'type': ending_type, 'reason': reason,
                        'description': desc, 'metrics': metrics,
                    })
                    self.running = False
                    break

            if self.running:
                scenario = session.query(Scenario).get(self.scenario_id)
                scenario.status = 'done'
                session.commit()
                self._emit('sim:progress', {'status': 'done'})

        except Exception as e:
            logger.error(f'Simulation error: {e}', exc_info=True)
            self._emit('sim:error', {'error': str(e)})
            self._update_status('ready')
        finally:
            self.running = False
            session.close()

    # ------------------------------------------------------------------ #
    #  Initial state (tick 0)                                             #
    # ------------------------------------------------------------------ #

    def _generate_initial_state(self, session, scenario):
        entities = session.query(Entity).filter_by(
            scenario_id=self.scenario_id).all()
        if not entities:
            self._emit('sim:error', {'error': 'No entities found'})
            return

        active = self._select_tick_entities(entities, 0)
        entity_text = '\n'.join(
            f'{e.faction or e.name}({e.type}): {e.description} [压力:{e.pressure:.0f}]'
            for e in active
        )
        avg_p = sum(e.pressure for e in entities) / max(len(entities), 1)
        high_pct = sum(1 for e in entities if e.pressure >= 70) / max(len(entities), 1) * 100

        macro_indicators = self._generate_macro_schema(scenario)
        macro_ctx = ''
        if macro_indicators:
            macro_ctx = '\n当前宏观指标:\n' + '\n'.join(
                f'- {k}: {v}' for k, v in macro_indicators.items())

        init_summary = llm_client.call([
            {'role': 'system', 'content': (
                f'你是局势分析师。{scenario.narrator_persona}\n'
                '用通俗中文描述，像写新闻报道，不要华丽修辞。\n'
                '要体现各方群体的实际处境和压力。\n'
                '必须使用集体视角，禁止出现人名。')},
            {'role': 'user', 'content': (
                f'请为以下场景写初始局势描述（300字以内）。\n\n'
                f'背景: {scenario.background}\n问题: {scenario.question}\n\n'
                f'关键群体(部分):\n{entity_text}\n\n'
                f'整体压力指标: 平均压力{avg_p:.0f}/100, '
                f'高压力群体占比{high_pct:.0f}%\n'
                f'{macro_ctx}\n\n'
                '要求：\n'
                '1. 描述当前各群体面临的真实处境和压力\n'
                '2. 指出短期利益冲突和潜在矛盾\n'
                '3. 结合宏观指标描述社会整体状态\n'
                '4. 用直白语言，像写新闻背景介绍\n'
                '5. 必须用群体视角，禁止出现个体人名')},
        ])

        im = self.ending_system.metrics
        im['pressure'] = avg_p
        im['darkness'] = high_pct * 0.5

        round_obj = Round(
            scenario_id=self.scenario_id, round_number=0,
            year=scenario.start_year,
            tick_date=f'{scenario.start_year}年1月',
            situation_summary=init_summary,
            darkness_value=im['darkness'], pressure_value=im['pressure'],
            stability_value=im['stability'], hope_value=im['hope'],
            macro_indicators=macro_indicators,
        )
        session.add(round_obj)
        session.add(TimelineEvent(
            scenario_id=self.scenario_id, round_id=round_obj.id,
            event_type='narrative', content=init_summary,
            year=scenario.start_year, round_number=0,
            event_date=f'{scenario.start_year}年1月',
        ))
        session.commit()

        self._emit('sim:round', {
            'type': 'narrative', 'tick': 0,
            'year': scenario.start_year, 'month': 1,
            'date': f'{scenario.start_year}年1月',
            'summary': init_summary,
            'macro_indicators': macro_indicators,
            'active_entities': [
                {'name': e.name, 'type': e.type, 'faction': e.faction}
                for e in active],
        })
        self._emit('sim:metrics', im)

        for e in entities:
            graphiti_service.add_entity_episode(self.scenario_id, {
                'name': e.name, 'type': e.type, 'faction': e.faction,
                'motivation': e.motivation, 'personality': e.personality,
                'description': e.description, 'initial_status': e.initial_status,
                'start_year': scenario.start_year,
            })
            time.sleep(0)
        graphiti_service.build_initial_relationships(self.scenario_id)
        uploaded = scenario.uploaded_files or []
        if uploaded:
            doc = '\n\n'.join(f.get('parsed_text', '')[:3000] for f in uploaded[:3])
            if doc:
                graphiti_service.extract_from_documents(self.scenario_id, doc)
        graphiti_service.add_episode(
            self.scenario_id, 'initial_situation', init_summary,
            scenario.start_year, 0)
        self._update_status('running')

    # ------------------------------------------------------------------ #
    #  Entity selection                                                   #
    # ------------------------------------------------------------------ #

    def _select_tick_entities(self, entities, tick):
        active = [e for e in entities if e.status == 'active']
        sorted_e = sorted(
            active,
            key=lambda e: (e.influence or 50) * 0.6
                         + (e.prominence or 5) * 3
                         + (e.pressure or 50) * 0.05,
            reverse=True,
        )
        top = sorted_e[:3]
        rest = sorted_e[3:]
        if not rest:
            return top[:ACTIVE_PER_TICK]
        idx = (tick * 7) % len(rest)
        rot = rest[idx:idx + ACTIVE_PER_TICK - 3]
        if len(rot) < ACTIVE_PER_TICK - 3 and len(rest) > len(rot):
            rot.extend(rest[:ACTIVE_PER_TICK - 3 - len(rot)])
        return (top + rot)[:ACTIVE_PER_TICK]

    # ------------------------------------------------------------------ #
    #  Situation analysis                                                 #
    # ------------------------------------------------------------------ #

    def _get_situation(self, session, scenario, tick, year, month,
                       entities, macro_indicators=None):
        prev = session.query(Round).filter_by(
            scenario_id=self.scenario_id
        ).order_by(Round.round_number.desc()).limit(3).all()
        prev_text = '\n'.join(
            f'{r.tick_date or r.year}: {r.situation_summary[:200]}'
            for r in reversed(prev))

        injected = session.query(TimelineEvent).filter(
            TimelineEvent.scenario_id == self.scenario_id,
            TimelineEvent.event_type == 'injected',
            TimelineEvent.round_number >= max(0, tick - 2),
        ).order_by(TimelineEvent.round_number.desc()).all()
        inj_text = ''
        if injected:
            inj_text = '\n突发外部事件:\n' + '\n'.join(
                f'- {e.content}' for e in injected)

        recent_text = ''
        if self._recent_events:
            recent_text = '\n近期重大事件:\n' + '\n'.join(
                f'- {ev}' for ev in self._recent_events[-3:])

        alive = [e for e in entities if e.status == 'active'][:30]
        states = '\n'.join(
            f'{e.faction or e.name}({e.type}): 压力{e.pressure:.0f} | {e.current_state}'
            for e in alive)
        avg_p = sum(e.pressure for e in alive) / max(len(alive), 1)
        high_p = sum(1 for e in alive if e.pressure >= 70)
        crit_p = sum(1 for e in alive if e.pressure >= 90)

        macro_text = ''
        if macro_indicators:
            macro_text = '\n宏观指标:\n' + '\n'.join(
                f'- {k}: {v}' for k, v in macro_indicators.items())

        date_str = f'{year}年{month}月'
        return llm_client.call([
            {'role': 'system', 'content': (
                f'你是{date_str}局势分析师。用通俗中文简述局势。\n'
                '要求：直白语言，像新闻报道。重点描述集体压力和冲突。\n'
                '必须使用集体/群体视角，禁止出现人名。')},
            {'role': 'user', 'content': (
                f'前情:\n{prev_text}\n\n'
                f'{inj_text}\n{recent_text}\n'
                f'各方压力:\n{states}\n\n'
                f'平均{avg_p:.0f}/100, 高压≥70: {high_p}, 临界≥90: {crit_p}\n'
                f'{macro_text}\n\n'
                f'核心问题: {scenario.question}\n\n'
                f'用150-250字描述{date_str}局势。')},
        ])

    # ------------------------------------------------------------------ #
    #  Autonomous actions                                                 #
    # ------------------------------------------------------------------ #

    def _generate_autonomous_actions(self, entities, situation, date_str,
                                     macro_indicators=None):
        """Two-phase action generation for causal chain between entities.

        Phase 1: Top-influence entities act first (days 1-15).
        Phase 2: Remaining entities react to Phase 1 (days 10-28).
        """
        if len(entities) <= 3:
            return self._gen_actions_batch(entities, situation, date_str,
                                           macro_indicators, phase_label='initiator')

        # --- Phase 1: Initiators (top 3 by influence) ---
        initiators = sorted(
            entities,
            key=lambda e: (e.influence or 50) * 0.6
                         + (e.prominence or 5) * 3,
            reverse=True,
        )[:3]

        p1_actions = self._gen_actions_batch(
            initiators, situation, date_str, macro_indicators,
            phase_label='initiator', day_range=(1, 15))

        # --- Phase 2: Responders (rest) see Phase 1 results ---
        initiator_names = {e.name for e in initiators}
        responders = [e for e in entities if e.name not in initiator_names]

        if not responders:
            return p1_actions

        p1_summary = '\n'.join(
            f'[{a.get("timestamp", date_str)}] {a["entity"]}: '
            f'{a.get("action", "?")} → {a.get("target", "?")}'
            for a in p1_actions)

        p2_actions = self._gen_actions_batch(
            responders, situation, date_str, macro_indicators,
            phase_label='responder', day_range=(10, 28),
            prior_actions=p1_summary)

        # Merge & sort by day
        all_actions = p1_actions + p2_actions
        all_actions.sort(key=lambda a: a.get('day', 15))
        return all_actions

    def _gen_actions_batch(self, entities, situation, date_str,
                           macro_indicators, phase_label='initiator',
                           day_range=(1, 28), prior_actions=None):
        """Generate actions for a batch of entities."""
        blocks = []
        for e in entities:
            b = f'【{e.name}】{e.type} | {e.faction}'
            if e.description: b += f'\n  身份: {e.description}'
            if e.backstory:   b += f'\n  背景: {e.backstory}'
            if e.personality: b += f'\n  性格: {e.personality}'
            if e.motivation:  b += f'\n  动机: {e.motivation}'
            if e.pressure_desc: b += f'\n  压力来源: {e.pressure_desc}'
            if e.current_state: b += f'\n  现状: {e.current_state}'
            b += f'\n  压力: {e.pressure:.0f}/100'
            if e.short_term_goal: b += f'\n  短期诉求: {e.short_term_goal}'
            if e.long_term_goal:  b += f'\n  长期诉求: {e.long_term_goal}'
            b += f'\n  短期紧迫度: {e.short_term_urgency:.0f}/100'
            blocks.append(b)

        ent_text = '\n\n'.join(blocks)
        macro_text = ''
        if macro_indicators:
            macro_text = '\n宏观指标:\n' + '\n'.join(
                f'- {k}: {v}' for k, v in macro_indicators.items())

        # Build prompt based on phase
        if phase_label == 'responder' and prior_actions:
            phase_instruction = (
                f'你是第二波行动者。本月已有人先行动，你需要根据他们的行动做出反应。\n\n'
                f'本月先行者的行动:\n{prior_actions}\n\n'
                '要求：\n'
                '- 必须对先行者的行动做出反应（支持/反对/利用/回避/联合）\n'
                '- 行动要体现因果关系，不能无视先行者的行动\n'
                '- 可以针对先行者采取对抗、联合、利用等策略\n'
                '- 日期范围必须在{day_range[0]}-{day_range[1]}日之间\n'
            )
        else:
            phase_instruction = (
                '你是高影响力先行者。你要率先采取行动，你的行动会影响后续其他实体的反应。\n'
                f'- 日期范围必须在{day_range[0]}-{day_range[1]}日之间\n'
            )

        result = llm_client.call_json([
            {'role': 'system', 'content': (
                f'让{len(entities)}个实体在{date_str}自主行动。\n\n'
                f'{phase_instruction}\n'
                '行为指导（马斯洛+博弈论）:\n'
                '- 压力≥90: 极端行动\n'
                '- 压力≥80: 积极寻求改变\n'
                '- 压力≥60: 策略性行动\n'
                '- 压力<60: 维持现状\n\n'
                '输出JSON:\n'
                '{"d":[{"e":"实体名",'
                '"t":"内心独白(50-70字)",'
                '"df":"渴望(10-15字)",'
                '"fr":"恐惧(10-15字)",'
                '"a":"行动(25-35字)",'
                '"g":"行动对象",'
                '"o":"预期结果(15-25字)",'
                f'"day":日期{day_range[0]}-{day_range[1]},'
                '"at":"proactive|reactive|wait",'
                '"urgency":"紧迫|正常|长远"}]}')},
            {'role': 'user', 'content': (
                f'{date_str}局势:\n{(situation or "")[:300]}\n'
                f'{macro_text}\n\n'
                f'参与行动实体:\n{ent_text}\n\n'
                '请让每个实体自主行动。')},
        ], temperature=0.7, max_tokens=4096)

        raw = result.get('d') or result.get('decisions') or []
        actions = []
        for d in raw:
            day = d.get('day', random.randint(day_range[0], day_range[1]))
            try:
                day = max(day_range[0], min(day_range[1], int(day)))
            except (TypeError, ValueError):
                day = random.randint(day_range[0], day_range[1])
            actions.append({
                'entity': d.get('e') or d.get('entity') or '',
                'thought': d.get('t') or d.get('thought') or '',
                'desire': d.get('df') or d.get('desire') or '',
                'fear': d.get('fr') or d.get('fear') or '',
                'action': d.get('a') or d.get('action') or '',
                'target': d.get('g') or d.get('target') or '',
                'expected_outcome': d.get('o') or d.get('expected_outcome') or '',
                'urgency': d.get('urgency') or 'normal',
                'action_type': d.get('at') or 'proactive',
                'timestamp': f'{date_str}{day}日',
                'day': day,
                'phase': phase_label,
            })
        return actions

    # ------------------------------------------------------------------ #
    #  Resolve tick                                                       #
    # ------------------------------------------------------------------ #

    def _resolve_tick(self, session, scenario, tick, date_str,
                      situation, actions, entities):
        fmap = {e.name: (e.faction or e.type) for e in entities}
        pnames = {e.name: (e.faction or e.type) for e in entities
                  if e.type == 'Person'}

        a_text = '\n'.join(
            f'[{a.get("timestamp", date_str)}] '
            f'{a["entity"]}({fmap.get(a["entity"], "")}): '
            f'{a.get("action", "?")} → {a.get("target", "?")}'
            for a in actions)

        states = '\n'.join(
            f'{e.faction or e.name}({e.type}): '
            f'压力={e.pressure:.0f} 影响力={e.influence:.0f} | {e.current_state}'
            for e in entities if e.status != 'dead')[:3000]

        injected = session.query(TimelineEvent).filter(
            TimelineEvent.scenario_id == self.scenario_id,
            TimelineEvent.event_type == 'injected',
            TimelineEvent.round_number >= max(0, tick - 2),
        ).all()
        inj_ctx = ''
        if injected:
            inj_ctx = '\n突发外部事件:\n' + '\n'.join(
                f'- {e.content}' for e in injected)

        result = llm_client.call_json([
            {'role': 'system', 'content': (
                f'你是推演裁判。综合评估{date_str}各方行动结果。\n\n'
                '要求：\n'
                '- summary用群体视角，150-250字，禁止出现Person人名\n'
                '- action_outcomes对每个行动给结果\n'
                '- influence_changes指出影响力变化\n\n'
                '影响力规则：暴力/抗议→弱势群体+20~30；政府失误→-20~30；'
                '成功+5~15；正常±3~5\n\n'
                '输出JSON:\n'
                '{"summary":"150-250字总结",'
                '"action_outcomes":[{"entity":"名","result":"结果","impact":"影响"}],'
                '"entity_updates":[{"name":"名","status":"active|weakened|dead",'
                '"resources":0-100,"pressure_delta":-20~+20,"new_status":"简述",'
                '"urgency_delta":-30~+30}],'
                '"influence_changes":[{"name":"名","delta":±N,"reason":"原因"}]}')},
            {'role': 'user', 'content': (
                f'{date_str}局势:\n{situation}\n\n'
                f'{inj_ctx}\n\n'
                f'各方行动:\n{a_text}\n\n'
                f'当前实体状态:\n{states}\n\n'
                '请综合评估。')},
        ], max_tokens=8192)

        if result and result.get('summary'):
            s = result['summary']
            for pn, fac in pnames.items():
                s = s.replace(pn, fac)
            result['summary'] = s
        return result

    # ------------------------------------------------------------------ #
    #  Stubs — appended in Part 2                                         #
    # ------------------------------------------------------------------ #

    # ------------------------------------------------------------------ #
    #  Extreme events + chain reactions                                   #
    # ------------------------------------------------------------------ #

    def _check_extreme_event(self, entities, situation, date_str,
                             macro_indicators=None):
        """Check if a low-influence high-pressure entity triggers an extreme event.

        Probability = (pressure - 70) / 100 for entities with influence < 40.
        Higher pressure = higher chance. Pressure >= 95 = almost certain.
        """
        candidates = [
            e for e in entities
            if e.status == 'active'
            and e.pressure >= 75
            and (e.influence or 50) < 45
        ]
        if not candidates:
            return None

        # Sort by pressure desc, pick highest-pressure candidate
        candidates.sort(key=lambda e: e.pressure, reverse=True)
        for e in candidates:
            # Probability: 0% at 75, ~25% at 90, 60% at 95, 100% at 100
            prob = max(0, (e.pressure - 70) / 50.0)
            if random.random() < prob:
                # LLM generates the extreme event
                try:
                    result = llm_client.call_json([
                        {'role': 'system', 'content': (
                            '生成一个极端事件。一个被边缘化、高压力的实体爆发了极端行为。\n'
                            '事件要求：\n'
                            '- 必须与该实体的压力来源直接相关\n'
                            '- 事件要有破坏性/震撼性\n'
                            '- 事件会影响多个群体\n\n'
                            '输出JSON:\n'
                            '{"event":"事件描述(30字)",'
                            '"type":"暴力|抗议|自毁|逃亡|破坏|揭露",'
                            '"impact":"对社会的影响(20字)",'
                            '"affected":["受影响的群体1","群体2"]}')},
                        {'role': 'user', 'content': (
                            f'时间: {date_str}\n'
                            f'局势:\n{situation[:200]}\n\n'
                            f'爆发实体: {e.name} | {e.type} | {e.faction}\n'
                            f'身份: {e.description}\n'
                            f'压力来源: {e.pressure_desc}\n'
                            f'当前状态: {e.current_state}\n'
                            f'压力值: {e.pressure:.0f}/100\n'
                            f'影响力: {e.influence:.0f}/100 (极低)\n\n'
                            '该实体爆发了什么极端事件？')},
                    ], temperature=0.8, max_tokens=512)
                    return {
                        'entity': e.name,
                        'event': result.get('event', f'{e.name}爆发极端事件'),
                        'type': result.get('type', '暴力'),
                        'impact': result.get('impact', ''),
                        'affected': result.get('affected', []),
                    }
                except Exception as ex:
                    logger.error(f'Extreme event gen failed: {ex}')
                    return None
        return None

    def _trigger_chain_reaction(self, entities, extreme_event, situation,
                                date_str, macro_indicators=None):
        """All active entities react to an extreme event."""
        trigger_name = extreme_event.get('entity', '')
        event_desc = extreme_event.get('event', '')

        # Only entities NOT already in this tick's actions react
        responders = [e for e in entities
                      if e.status == 'active' and e.name != trigger_name]
        if not responders:
            return []

        macro_text = ''
        if macro_indicators:
            macro_text = '\n宏观指标:\n' + '\n'.join(
                f'- {k}: {v}' for k, v in macro_indicators.items())

        # Build brief entity descriptions for responders
        ent_blocks = []
        for e in responders[:15]:  # cap at 15 to avoid token overflow
            b = f'【{e.name}】{e.type} | {e.faction} | 压力:{e.pressure:.0f}'
            if e.current_state:
                b += f'\n  现状: {e.current_state}'
            ent_blocks.append(b)
        ent_text = '\n\n'.join(ent_blocks)

        result = llm_client.call_json([
            {'role': 'system', 'content': (
                f'突发极端事件！所有实体必须立即做出反应。\n\n'
                f'事件: {event_desc}\n'
                f'触发者: {trigger_name}\n'
                f'影响: {extreme_event.get("impact", "")}\n'
                f'受影响群体: {", ".join(extreme_event.get("affected", []))}\n\n'
                '每个实体必须做出反应：\n'
                '- 可以谴责、支持、利用、恐慌、镇压、保护\n'
                '- 反应要快（紧急行动），不需要长远规划\n'
                '- 高压力实体的反应更激烈\n\n'
                '输出JSON:\n'
                '{"d":[{"e":"实体名",'
                '"t":"即时反应思考(30-50字)",'
                '"a":"紧急反应行动(15-25字)",'
                '"g":"反应对象/目标",'
                '"urgency":"紧迫"}]}')},
            {'role': 'user', 'content': (
                f'{date_str}局势:\n{(situation or "")[:200]}\n'
                f'{macro_text}\n\n'
                f'突发极端事件: {event_desc}\n'
                f'由 {trigger_name} 触发\n\n'
                f'需要立即反应的实体:\n{ent_text}\n\n'
                '每个实体必须做出紧急反应。')},
        ], temperature=0.7, max_tokens=4096)

        raw = result.get('d') or result.get('decisions') or []
        chain = []
        for d in raw:
            day = random.randint(15, 28)
            chain.append({
                'entity': d.get('e') or d.get('entity') or '',
                'thought': d.get('t') or d.get('thought') or '',
                'desire': '', 'fear': '',
                'action': d.get('a') or d.get('action') or '',
                'target': d.get('g') or d.get('target') or '',
                'expected_outcome': '',
                'urgency': '紧迫',
                'action_type': 'reactive',
                'timestamp': f'{date_str}{day}日',
                'day': day,
                'phase': 'chain_reaction',
                'is_major': True,
            })
        return chain

    # ------------------------------------------------------------------ #
    #  Entity state + influence updates                                   #
    # ------------------------------------------------------------------ #

    def _update_entity_states(self, entities, actions, resolution, session):
        if not resolution.get('entity_updates'):
            return
        for u in resolution['entity_updates']:
            ent = next((e for e in entities if e.name == u.get('name')), None)
            if not ent:
                continue
            if u.get('status'):
                ent.status = u['status']
            if u.get('resources') is not None:
                ent.resources = max(0, min(100, int(u['resources'])))
            if u.get('pressure_delta'):
                ent.pressure = max(0, min(100,
                    ent.pressure + float(u['pressure_delta'])))
            if u.get('urgency_delta'):
                ent.short_term_urgency = max(0, min(100,
                    ent.short_term_urgency + float(u['urgency_delta'])))
            if u.get('new_status'):
                ent.current_state = u['new_status']
            if ent.short_term_urgency >= 80:
                ent.short_term_goal = f'[紧急] {ent.short_term_goal}'

    def _update_influence(self, entities, resolution, tick, session):
        changes = resolution.get('influence_changes', [])
        change_map = {c.get('name'): c.get('delta', 0) for c in changes}
        for e in entities:
            if e.status == 'dead':
                continue
            prom = (e.prominence or 5) / 10.0 * 100
            pres = e.pressure or 50
            res = e.resources or 50
            spike = abs(change_map.get(e.name, 0))
            base = 0.4 * prom + 0.2 * pres + 0.1 * res + 0.1 * spike
            delta = change_map.get(e.name, 0)
            new_inf = max(0, min(100,
                base * 0.3 + (e.influence or 50) * 0.7 + delta))
            e.influence = round(new_inf, 1)
            hist = e.influence_history or []
            hist.append({'tick': tick, 'value': round(new_inf, 1)})
            if len(hist) > 50:
                hist = hist[-50:]
            e.influence_history = hist

    # ------------------------------------------------------------------ #
    #  Major event triggers (hybrid: rules + LLM)                         #
    # ------------------------------------------------------------------ #

    def _check_event_triggers(self, session, scenario, tick, date_str,
                              situation, actions):
        """Check user-defined event trigger rules."""
        triggers = scenario.event_triggers or []
        for rule in triggers:
            condition = rule.get('condition', '')
            if not condition:
                continue
            try:
                result = llm_client.call_json([
                    {'role': 'system', 'content': (
                        '判断事件触发条件是否满足。只输出JSON。')},
                    {'role': 'user', 'content': (
                        f'当前时间: {date_str}\n'
                        f'当前局势:\n{situation[:300]}\n\n'
                        f'触发条件: {condition}\n\n'
                        f'判断条件是否满足。输出JSON:\n'
                        f'{{"triggered": true/false, '
                        f'"event": "触发后的事件描述(30字以内)"}}')},
                ], temperature=0.2, max_tokens=256)
                if result.get('triggered'):
                    event_desc = result.get('event', condition)
                    logger.info(f'Rule triggered: {event_desc}')
                    return event_desc
            except Exception as e:
                logger.debug(f'Trigger check failed: {e}')
        return None

    def _llm_check_major_events(self, situation, actions, date_str):
        """LLM autonomously judges if a major event should occur."""
        actions_text = '\n'.join(
            f'- {a["entity"]}: {a.get("action", "?")}'
            for a in actions)
        try:
            result = llm_client.call_json([
                {'role': 'system', 'content': (
                    '你是推演事件判断师。判断当前局势是否应该触发重大事件。\n'
                    '重大事件标准：社会动荡、政策变革、自然灾害、技术突破、'
                    '战争冲突、经济崩溃等改变格局的事件。\n'
                    '通常不应频繁触发，大部分tick不应有重大事件。\n'
                    '输出JSON: {"triggered": true/false, '
                    '"event": "事件描述(30字)"}')},
                {'role': 'user', 'content': (
                    f'时间: {date_str}\n'
                    f'局势:\n{situation[:300]}\n\n'
                    f'各方行动:\n{actions_text}\n\n'
                    '是否应触发重大事件？')},
            ], temperature=0.5, max_tokens=256)
            if result.get('triggered'):
                return result.get('event', '')
        except Exception as e:
            logger.debug(f'LLM major event check failed: {e}')
        return None

    # ------------------------------------------------------------------ #
    #  Periodic summary                                                   #
    # ------------------------------------------------------------------ #

    def _generate_period_summary(self, session, scenario, tick, date_str):
        """Generate a periodic summary every N ticks."""
        recent = session.query(Round).filter(
            Round.scenario_id == self.scenario_id,
            Round.round_number >= tick - scenario.summary_interval + 1,
            Round.round_number <= tick,
        ).order_by(Round.round_number).all()

        if not recent:
            return

        events_text = '\n\n'.join(
            f'{r.tick_date or f"Tick {r.round_number}"}: '
            f'{r.situation_summary[:150]}'
            for r in recent)

        try:
            summary = llm_client.call([
                {'role': 'system', 'content': (
                    '你是推演总结分析师。用通俗中文写阶段性总结。\n'
                    '要求：群体视角，不要人名，150-250字。')},
                {'role': 'user', 'content': (
                    f'以下是从{recent[0].tick_date}到{date_str}的事件:\n\n'
                    f'{events_text}\n\n'
                    f'请写阶段性总结。')},
            ])
            round_obj = Round(
                scenario_id=self.scenario_id,
                round_number=tick,
                year=recent[-1].year,
                tick_date=date_str,
                is_summary=True,
                summary_text=summary,
                situation_summary=f'[阶段总结] {summary[:200]}',
            )
            session.add(round_obj)
            session.add(TimelineEvent(
                scenario_id=self.scenario_id,
                event_type='milestone',
                content=f'[阶段总结] {summary}',
                year=recent[-1].year,
                round_number=tick,
                event_date=date_str,
            ))
            session.commit()
            self._emit('sim:summary', {
                'tick': tick, 'date': date_str, 'summary': summary,
            })
        except Exception as e:
            logger.error(f'Period summary failed: {e}')

    # ------------------------------------------------------------------ #
    #  Entity spawning                                                    #
    # ------------------------------------------------------------------ #

    def _maybe_spawn_entities(self, session, scenario, year, tick, resolution):
        try:
            existing = session.query(Entity).filter_by(
                scenario_id=self.scenario_id).all()
            if len(existing) >= 30:
                return

            names = [e.name for e in existing]
            factions = list(set(e.faction for e in existing if e.faction))
            summary = resolution.get('summary', '')[:500]
            if not summary or len(summary) < 50:
                return

            result = llm_client.call_json([
                {'role': 'system', 'content': (
                    '判断本轮是否催生了新关键行动主体。\n'
                    '输出JSON:\n'
                    '{"spawn": true/false, "entities": '
                    '[{"name":"名","type":"Person|Organization|Institution|Force",'
                    '"faction":"阵营","description":"30字","motivation":"动机",'
                    '"personality":"性格","pressure":0-100,"prominence":1-10,'
                    '"backstory":"80字","reason":"为什么涌现"}]}')},
                {'role': 'user', 'content': (
                    f'本轮摘要:\n{summary}\n\n'
                    f'现有实体: {", ".join(names[:20])}\n'
                    f'现有阵营: {", ".join(factions[:10])}\n\n'
                    '是否有新的关键行动主体涌现？最多2个。')},
            ], temperature=0.5)

            if not result.get('spawn'):
                return
            for ent in result.get('entities', [])[:2]:
                name = ent.get('name', '').strip()
                if not name or name in names:
                    continue
                ne = Entity(
                    scenario_id=self.scenario_id, name=name,
                    type=ent.get('type', 'Organization'),
                    faction=ent.get('faction', ''),
                    description=ent.get('description', ''),
                    motivation=ent.get('motivation', ''),
                    personality=ent.get('personality', ''),
                    pressure=float(ent.get('pressure', 50)),
                    prominence=int(ent.get('prominence', 5)),
                    backstory=ent.get('backstory', ''),
                    influence=40.0,
                    initial_status=ent.get('description', ''),
                    current_state=ent.get('description', ''),
                    short_term_goal=ent.get('motivation', ''),
                    long_term_goal=ent.get('motivation', ''),
                )
                session.add(ne)
                names.append(name)
                self._emit('sim:entity_spawned', {
                    'entity': {'name': name, 'type': ne.type,
                               'faction': ne.faction,
                               'description': ne.description},
                    'tick': tick, 'reason': ent.get('reason', ''),
                })
                logger.info(f'Spawned: {name} ({ne.type})')
            session.commit()
        except Exception as e:
            logger.error(f'Spawn failed: {e}')

    # ------------------------------------------------------------------ #
    #  Timeline summary                                                   #
    # ------------------------------------------------------------------ #

    def _get_timeline_summary(self, session):
        events = session.query(TimelineEvent).filter_by(
            scenario_id=self.scenario_id
        ).order_by(TimelineEvent.round_number).all()
        return '\n\n'.join(
            f'### {e.event_date or f"{e.year}年"} '
            f'(Tick {e.round_number})\n{e.content}'
            for e in events)

    # ------------------------------------------------------------------ #
    #  Macro indicators                                                   #
    # ------------------------------------------------------------------ #

    def _generate_macro_schema(self, scenario):
        result = llm_client.call_json([
            {'role': 'system', 'content': (
                '根据场景设计5-8个宏观指标。只输出JSON。')},
            {'role': 'user', 'content': (
                f'背景: {scenario.background[:300]}\n'
                f'问题: {scenario.question}\n\n'
                '设计5-8个相关宏观指标。JSON:\n'
                '{"indicators":[{"name":"名","unit":"单位",'
                '"initial":数值,"desc":"10字描述"}]}\n\n'
                '指标名用中文，如失业率、GDP增速。')},
        ], temperature=0.5)
        indicators = result.get('indicators', [])
        scenario.macro_indicator_schema = indicators
        return {i['name']: i.get('initial', 50)
                for i in indicators if i.get('name')}

    def _update_macro_indicators(self, indicators, situation, decisions,
                                 resolution):
        if not indicators:
            return {}
        ind_text = '\n'.join(f'- {k}: {v}' for k, v in indicators.items())
        result = llm_client.call_json([
            {'role': 'system', 'content': '更新宏观指标。只输出JSON。'},
            {'role': 'user', 'content': (
                f'当前指标:\n{ind_text}\n\n'
                f'局势: {(situation or "")[:200]}\n'
                f'决策: {(decisions or "")[:200]}\n'
                f'结果: {(resolution or "")[:200]}\n\n'
                '更新指标。JSON: {"updates":{"指标名":新值}}\n'
                '变化幅度通常±0.5~3。')},
        ], temperature=0.3)
        for k, v in result.get('updates', {}).items():
            if k in indicators:
                try:
                    indicators[k] = float(v)
                except (TypeError, ValueError):
                    pass
        return indicators

    def _apply_macro_pressure(self, entities, indicators, session):
        if not indicators:
            return
        ind_text = '\n'.join(f'- {k}: {v}' for k, v in indicators.items())
        alive = [e for e in entities if e.status != 'dead'][:30]
        ent_text = '\n'.join(
            f'{e.faction or e.name}({e.type}): 压力{e.pressure:.0f}, '
            f'{e.current_state or e.description}'
            for e in alive)
        result = llm_client.call_json([
            {'role': 'system', 'content': '根据宏观指标调整实体压力。只输出JSON。'},
            {'role': 'user', 'content': (
                f'宏观指标:\n{ind_text}\n\n'
                f'实体:\n{ent_text}\n\n'
                '给出需调整的实体(最多10个)。JSON:\n'
                '{"adjustments":[{"name":"名","delta":-5~+5,"reason":"原因"}]}\n'
                '只输出有变化的。')},
        ], temperature=0.3)
        for adj in result.get('adjustments', []):
            ent = next((e for e in entities if e.name == adj.get('name')),
                       None)
            if ent and adj.get('delta'):
                try:
                    ent.pressure = max(0, min(100,
                        ent.pressure + float(adj['delta'])))
                except (TypeError, ValueError):
                    pass
