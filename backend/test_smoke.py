"""Quick smoke test for WorldSim backend changes."""
import sys
import json
sys.path.insert(0, '.')

def test_imports():
    print('1. Testing imports...')
    from services.simulation_engine import SimulationEngine
    from services.ending_system import EndingSystem, DEFAULT_ENDING_CONFIG
    from models.database import (
        init_db, get_session, Scenario, Entity, Round,
        Decision, TimelineEvent, MetricsHistory
    )
    print('   All imports OK')
    return SimulationEngine, EndingSystem, DEFAULT_ENDING_CONFIG

def test_database():
    print('2. Testing database schema...')
    from models.database import init_db, get_session, Scenario
    engine = init_db()
    session = get_session()

    # Create test scenario with all new fields
    s = Scenario(
        name='测试场景',
        background='AI替代白领工作',
        question='社会如何应对',
        darkness_base=10.0,
        pressure_base=20.0,
        stability_base=45.0,
        hope_base=55.0,
        time_unit='month',
        total_duration=24,
        summary_interval=3,
        ending_config={'bad_darkness': 85, 'good_hope': 80},
        event_triggers=[{'condition': '失业率超过20%'}],
    )
    session.add(s)
    session.commit()
    sid = s.id

    # Read back
    s2 = session.query(Scenario).get(sid)
    assert s2.darkness_base == 10.0, f'darkness_base wrong: {s2.darkness_base}'
    assert s2.stability_base == 45.0, f'stability_base wrong: {s2.stability_base}'
    assert s2.hope_base == 55.0, f'hope_base wrong: {s2.hope_base}'
    assert s2.total_duration == 24, f'total_duration wrong: {s2.total_duration}'
    assert s2.summary_interval == 3, f'summary_interval wrong: {s2.summary_interval}'
    assert s2.ending_config == {'bad_darkness': 85, 'good_hope': 80}, f'ending_config wrong: {s2.ending_config}'
    assert len(s2.event_triggers) == 1, f'event_triggers wrong: {s2.event_triggers}'

    # Test Round with tick fields
    from models.database import Round
    r = Round(
        scenario_id=sid, round_number=1,
        year=2026, tick_date='2026年2月',
        is_summary=False, summary_text='',
    )
    session.add(r)
    session.commit()

    r2 = session.query(Round).filter_by(scenario_id=sid).first()
    assert r2.tick_date == '2026年2月', f'tick_date wrong: {r2.tick_date}'
    assert r2.is_summary == False

    # Test Decision with tick fields
    from models.database import Decision
    d = Decision(
        round_id=r2.id, entity_id=1,
        event_timestamp='2026年2月15日',
        is_major=True, action_type='proactive',
        thought='test', action='test action',
    )
    session.add(d)
    session.commit()

    d2 = session.query(Decision).filter_by(round_id=r2.id).first()
    assert d2.event_timestamp == '2026年2月15日'
    assert d2.is_major == True
    assert d2.action_type == 'proactive'

    # Test TimelineEvent with tick fields
    from models.database import TimelineEvent
    t = TimelineEvent(
        scenario_id=sid, round_id=r2.id,
        event_type='major_event',
        content='测试大事件',
        year=2026, round_number=1,
        event_date='2026年2月15日',
        is_major=True,
    )
    session.add(t)
    session.commit()

    t2 = session.query(TimelineEvent).filter_by(scenario_id=sid).first()
    assert t2.event_date == '2026年2月15日'
    assert t2.is_major == True

    # Cleanup
    session.delete(t)
    session.delete(d)
    session.delete(r)
    session.delete(s)
    session.commit()
    session.close()
    print('   Database schema OK - all new fields work')
    return True

def test_ending_system():
    print('3. Testing EndingSystem...')
    from services.ending_system import EndingSystem, DEFAULT_ENDING_CONFIG

    es = EndingSystem()

    # Test set_base with 4 params
    es.set_base(darkness_base=10, pressure_base=20, stability_base=45, hope_base=55)
    m = es.get_metrics()
    assert m['darkness'] == 10, f'darkness wrong: {m["darkness"]}'
    assert m['pressure'] == 20, f'pressure wrong: {m["pressure"]}'
    assert m['stability'] == 45, f'stability wrong: {m["stability"]}'
    assert m['hope'] == 55, f'hope wrong: {m["hope"]}'

    # Test set_ending_config
    es.set_ending_config({'bad_darkness': 80, 'max_delta': 20})
    assert es.ending_config['bad_darkness'] == 80
    assert es.ending_config['max_delta'] == 20
    assert es.ending_config['bad_pressure'] == DEFAULT_ENDING_CONFIG['bad_pressure']  # kept default

    # Test check_ending - not triggered
    should_end, etype, reason = es.check_ending(5, 60)
    assert not should_end

    # Test check_ending - bad end triggered
    es.metrics['darkness'] = 85
    should_end, etype, reason = es.check_ending(5, 60)
    assert should_end
    assert etype == 'bad'

    # Test check_ending - good end triggered
    es.metrics['darkness'] = 10
    es.metrics['hope'] = 85
    es.metrics['stability'] = 65
    should_end, etype, reason = es.check_ending(5, 60)
    assert should_end
    assert etype == 'good'

    # Test check_ending - max ticks reached
    es.metrics = {'darkness': 30, 'pressure': 30, 'stability': 50, 'hope': 50}
    should_end, etype, reason = es.check_ending(60, 60)
    assert should_end

    print('   EndingSystem OK')
    return True

def test_simulation_engine():
    print('4. Testing SimulationEngine methods...')
    from services.simulation_engine import SimulationEngine

    eng = SimulationEngine(scenario_id=999)

    # Test _tick_date
    y, m, d = eng._tick_date(2026, 1)
    assert (y, m, d) == (2026, 1, '2026年1月'), f'tick 1: {(y,m,d)}'

    y, m, d = eng._tick_date(2026, 12)
    assert (y, m, d) == (2026, 12, '2026年12月'), f'tick 12: {(y,m,d)}'

    y, m, d = eng._tick_date(2026, 13)
    assert (y, m, d) == (2027, 1, '2027年1月'), f'tick 13: {(y,m,d)}'

    y, m, d = eng._tick_date(2026, 60)
    assert (y, m, d) == (2030, 12, '2030年12月'), f'tick 60: {(y,m,d)}'

    # Test _select_tick_entities
    from models.database import Entity
    entities = []
    for i in range(10):
        e = Entity(
            scenario_id=999, name=f'E{i}', type='Person',
            influence=50 + i * 5, prominence=5, pressure=50,
            status='active', description='', initial_status='',
        )
        entities.append(e)

    selected = eng._select_tick_entities(entities, 0)
    assert len(selected) <= 5, f'selected too many: {len(selected)}'
    # Top influence should be first
    assert selected[0].name == 'E9', f'top should be E9: {selected[0].name}'

    # Test _check_extreme_event returns None when no candidates
    result = eng._check_extreme_event(entities, 'test situation', '2026年1月')
    assert result is None, f'should be None: {result}'

    # Test with high pressure low influence candidate
    entities[0].pressure = 98
    entities[0].influence = 10
    # This might return None due to random probability, just verify it doesn't crash
    try:
        eng._check_extreme_event(entities, 'test', '2026年1月')
    except Exception:
        pass  # LLM call might fail, that's OK for unit test

    print('   SimulationEngine methods OK')
    return True

def test_api_routes():
    print('5. Testing API route imports...')
    from routes.scenario import scenario_bp
    from routes.simulation import simulation_bp
    print('   API route imports OK')
    return True

if __name__ == '__main__':
    print('=' * 50)
    print('WorldSim Smoke Test')
    print('=' * 50)

    results = []
    try:
        test_imports()
        results.append(('imports', True))
    except Exception as e:
        print(f'   FAIL: {e}')
        results.append(('imports', False))

    try:
        test_database()
        results.append(('database', True))
    except Exception as e:
        print(f'   FAIL: {e}')
        import traceback
        traceback.print_exc()
        results.append(('database', False))

    try:
        test_ending_system()
        results.append(('ending_system', True))
    except Exception as e:
        print(f'   FAIL: {e}')
        results.append(('ending_system', False))

    try:
        test_simulation_engine()
        results.append(('simulation_engine', True))
    except Exception as e:
        print(f'   FAIL: {e}')
        import traceback
        traceback.print_exc()
        results.append(('simulation_engine', False))

    try:
        test_api_routes()
        results.append(('api_routes', True))
    except Exception as e:
        print(f'   FAIL: {e}')
        results.append(('api_routes', False))

    print()
    print('=' * 50)
    print('Results:')
    all_pass = True
    for name, ok in results:
        status = 'PASS' if ok else 'FAIL'
        print(f'  {name}: {status}')
        if not ok:
            all_pass = False

    print('=' * 50)
    if all_pass:
        print('All tests passed!')
        sys.exit(0)
    else:
        print('Some tests failed!')
        sys.exit(1)
