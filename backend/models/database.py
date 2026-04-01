"""WorldSim Database Models"""
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, Float, String, Text, DateTime,
    ForeignKey, JSON, Boolean, inspect, text
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from config import Config

Base = declarative_base()


class Scenario(Base):
    __tablename__ = 'scenarios'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, default='未命名场景')
    background = Column(Text, default='')
    question = Column(Text, default='')
    rules = Column(Text, default='')
    uploaded_files = Column(JSON, default=list)  # [{filename, path, parsed_text}]
    start_year = Column(Integer, default=2026)
    max_rounds = Column(Integer, default=5)
    entity_count = Column(Integer, default=100)
    narrator_persona = Column(Text, default='客观描述局势')
    status = Column(String(20), default='draft')  # draft/ready/running/paused/done
    darkness_base = Column(Float, default=0.0)
    pressure_base = Column(Float, default=0.0)
    stability_base = Column(Float, default=50.0)
    hope_base = Column(Float, default=50.0)
    macro_indicator_schema = Column(JSON, default=list)  # [{"name":"失业率","unit":"%","initial":5.2},...]
    # Tick-based simulation settings
    time_unit = Column(String(10), default='month')  # month/quarter
    total_duration = Column(Integer, default=60)      # total ticks (e.g., 60 months = 5 years)
    summary_interval = Column(Integer, default=6)     # generate summary every N ticks
    # Configurable ending & events
    ending_config = Column(JSON, default=dict)  # configurable ending thresholds
    event_triggers = Column(JSON, default=list)  # major event trigger rules
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    entities = relationship('Entity', back_populates='scenario', cascade='all, delete-orphan')
    rounds = relationship('Round', back_populates='scenario', cascade='all, delete-orphan')
    timeline_events = relationship('TimelineEvent', back_populates='scenario', cascade='all, delete-orphan')
    metrics_history = relationship('MetricsHistory', back_populates='scenario', cascade='all, delete-orphan')
    report = relationship('Report', back_populates='scenario', uselist=False, cascade='all, delete-orphan')


class Entity(Base):
    __tablename__ = 'entities'
    id = Column(Integer, primary_key=True, autoincrement=True)
    scenario_id = Column(Integer, ForeignKey('scenarios.id'), nullable=False)
    name = Column(String(80), nullable=False)
    type = Column(String(30), default='Person')  # Person/Organization/Institution/Force
    faction = Column(String(60), default='')
    personality = Column(Text, default='')
    motivation = Column(Text, default='')
    description = Column(Text, default='')
    initial_status = Column(Text, default='')
    prominence = Column(Integer, default=5)  # 1-10
    # Character card fields (SillyTavern-style)
    persona = Column(Text, default='')
    appearance = Column(Text, default='')
    speech_style = Column(Text, default='')
    tags = Column(String(200), default='')
    # Simulation state
    status = Column(String(20), default='active')  # active/weakened/empowered/transformed/dead
    resources = Column(Integer, default=100)
    pressure = Column(Float, default=50.0)  # Individual stress 0-100
    current_state = Column(Text, default='')
    short_term_goal = Column(Text, default='')  # 短期诉求
    long_term_goal = Column(Text, default='')   # 长期诉求
    short_term_urgency = Column(Float, default=30.0)  # 短期诉求紧迫度 0-100
    backstory = Column(Text, default='')  # 80-120字背景故事
    pressure_desc = Column(Text, default='')  # 压力来源描述
    influence = Column(Float, default=50.0)  # 影响力系数 0-100
    influence_history = Column(JSON, default=list)  # [{round:1, value:55}, ...]
    created_at = Column(DateTime, default=datetime.utcnow)

    scenario = relationship('Scenario', back_populates='entities')
    decisions = relationship('Decision', back_populates='entity', cascade='all, delete-orphan')


class Round(Base):
    __tablename__ = 'rounds'
    id = Column(Integer, primary_key=True, autoincrement=True)
    scenario_id = Column(Integer, ForeignKey('scenarios.id'), nullable=False)
    round_number = Column(Integer, nullable=False)  # now used as tick_number
    year = Column(Integer, nullable=False)
    tick_date = Column(String(20), default='')  # "2026年3月"
    is_summary = Column(Boolean, default=False)  # True if this is a summary tick
    summary_text = Column(Text, default='')
    situation_summary = Column(Text, default='')
    darkness_value = Column(Float, default=0.0)
    pressure_value = Column(Float, default=0.0)
    stability_value = Column(Float, default=50.0)
    hope_value = Column(Float, default=50.0)
    macro_indicators = Column(JSON, default=dict)
    phases = Column(JSON, default=dict)
    resolution_summary = Column(Text, default='')
    created_at = Column(DateTime, default=datetime.utcnow)

    scenario = relationship('Scenario', back_populates='rounds')
    decisions = relationship('Decision', back_populates='round', cascade='all, delete-orphan')


class Decision(Base):
    __tablename__ = 'decisions'
    id = Column(Integer, primary_key=True, autoincrement=True)
    round_id = Column(Integer, ForeignKey('rounds.id'), nullable=False)
    entity_id = Column(Integer, ForeignKey('entities.id'), nullable=False)
    thought = Column(Text, default='')
    action = Column(Text, default='')
    target = Column(Text, default='')
    expected_outcome = Column(Text, default='')
    actual_outcome = Column(Text, default='')
    desire = Column(Text, default='')
    fear = Column(Text, default='')
    urgency_level = Column(String(10), default='normal')
    phase = Column(Integer, default=1)
    reaction_to = Column(String(80), default='')
    # Tick-based fields
    event_timestamp = Column(String(30), default='')  # "2026年3月15日"
    is_major = Column(Boolean, default=False)          # triggered a major event
    action_type = Column(String(20), default='proactive')  # proactive/reactive/wait

    round = relationship('Round', back_populates='decisions')
    entity = relationship('Entity', back_populates='decisions')


class TimelineEvent(Base):
    __tablename__ = 'timeline_events'
    id = Column(Integer, primary_key=True, autoincrement=True)
    scenario_id = Column(Integer, ForeignKey('scenarios.id'), nullable=False)
    round_id = Column(Integer, ForeignKey('rounds.id'), nullable=True)
    event_type = Column(String(20), default='narrative')  # narrative/decision/injected/milestone/ending/major_event
    content = Column(Text, default='')
    year = Column(Integer, default=0)
    round_number = Column(Integer, default=0)
    event_date = Column(String(30), default='')  # precise timestamp "2026年3月15日"
    is_major = Column(Boolean, default=False)    # highlighted major event
    created_at = Column(DateTime, default=datetime.utcnow)

    scenario = relationship('Scenario', back_populates='timeline_events')


class MetricsHistory(Base):
    __tablename__ = 'metrics_history'
    id = Column(Integer, primary_key=True, autoincrement=True)
    scenario_id = Column(Integer, ForeignKey('scenarios.id'), nullable=False)
    round_id = Column(Integer, ForeignKey('rounds.id'), nullable=True)
    darkness = Column(Float, default=0.0)
    pressure = Column(Float, default=0.0)
    stability = Column(Float, default=50.0)
    hope = Column(Float, default=50.0)
    notes = Column(Text, default='')
    created_at = Column(DateTime, default=datetime.utcnow)

    scenario = relationship('Scenario', back_populates='metrics_history')


class Report(Base):
    __tablename__ = 'reports'
    id = Column(Integer, primary_key=True, autoincrement=True)
    scenario_id = Column(Integer, ForeignKey('scenarios.id'), nullable=False, unique=True)
    content = Column(Text, default='')
    ending_type = Column(String(20), default='neutral')  # good/bad/neutral/bittersweet
    created_at = Column(DateTime, default=datetime.utcnow)

    scenario = relationship('Scenario', back_populates='report')


# Database initialization
engine = None
SessionLocal = None


def init_db():
    global engine, SessionLocal
    Config.ensure_dirs()
    db_url = f"sqlite:///{Config.DB_PATH}"
    engine = create_engine(db_url, echo=False)
    SessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)
    _migrate(engine)
    return engine


def _migrate(eng):
    """Add missing columns to existing tables."""
    migrations = [
        ('entities', 'backstory', 'TEXT DEFAULT ""'),
        ('entities', 'pressure_desc', 'TEXT DEFAULT ""'),
        ('entities', 'influence', 'REAL DEFAULT 50.0'),
        ('entities', 'influence_history', 'TEXT DEFAULT "[]"'),
        ('rounds', 'macro_indicators', 'TEXT DEFAULT "{}"'),
        ('rounds', 'phases', 'TEXT DEFAULT "{}"'),
        ('scenarios', 'macro_indicator_schema', 'TEXT DEFAULT "[]"'),
        ('decisions', 'desire', 'TEXT DEFAULT ""'),
        ('decisions', 'fear', 'TEXT DEFAULT ""'),
        ('decisions', 'urgency_level', 'VARCHAR(10) DEFAULT "normal"'),
        ('decisions', 'phase', 'INTEGER DEFAULT 1'),
        ('decisions', 'reaction_to', 'VARCHAR(80) DEFAULT ""'),
        # Tick-based simulation fields
        ('rounds', 'tick_date', 'VARCHAR(20) DEFAULT ""'),
        ('rounds', 'is_summary', 'INTEGER DEFAULT 0'),
        ('rounds', 'summary_text', 'TEXT DEFAULT ""'),
        ('decisions', 'event_timestamp', 'VARCHAR(30) DEFAULT ""'),
        ('decisions', 'is_major', 'INTEGER DEFAULT 0'),
        ('decisions', 'action_type', 'VARCHAR(20) DEFAULT "proactive"'),
        ('decisions', 'is_major', 'INTEGER DEFAULT 0'),
        ('timeline_events', 'event_date', 'VARCHAR(30) DEFAULT ""'),
        ('timeline_events', 'is_major', 'INTEGER DEFAULT 0'),
        ('scenarios', 'time_unit', 'VARCHAR(10) DEFAULT "month"'),
        ('scenarios', 'total_duration', 'INTEGER DEFAULT 60'),
        ('scenarios', 'summary_interval', 'INTEGER DEFAULT 6'),
        ('scenarios', 'stability_base', 'REAL DEFAULT 50.0'),
        ('scenarios', 'hope_base', 'REAL DEFAULT 50.0'),
        ('scenarios', 'ending_config', 'TEXT DEFAULT "{}"'),
        ('scenarios', 'event_triggers', 'TEXT DEFAULT "[]"'),
    ]
    insp = inspect(eng)
    for table, col, coldef in migrations:
        try:
            existing = [c['name'] for c in insp.get_columns(table)]
        except Exception:
            continue
        if col not in existing:
            with eng.connect() as conn:
                conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {col} {coldef}'))
                conn.commit()


def get_session():
    if SessionLocal is None:
        init_db()
    return SessionLocal()


def reset_db():
    """Drop and recreate all tables."""
    if engine is None:
        init_db()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
