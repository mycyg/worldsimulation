"""Ending System - Configurable metrics and ending evaluation"""
import logging
from services.llm_client import llm_client

logger = logging.getLogger(__name__)

DEFAULT_ENDING_CONFIG = {
    'bad_darkness': 90,
    'bad_pressure': 95,
    'good_hope': 85,
    'good_stability': 60,
    'bittersweet_hope': 40,
    'bittersweet_darkness': 40,
    'final_good_hope': 60,
    'final_good_stability': 50,
    'final_bad_darkness': 70,
    'final_bad_pressure': 80,
    'max_delta': 15,
}


class EndingSystem:
    def __init__(self):
        self.metrics = {
            'darkness': 0.0,
            'pressure': 0.0,
            'stability': 50.0,
            'hope': 50.0,
        }
        self.ending_config = dict(DEFAULT_ENDING_CONFIG)

    def set_base(self, darkness_base=0.0, pressure_base=0.0, stability_base=50.0, hope_base=50.0):
        self.metrics['darkness'] = darkness_base
        self.metrics['pressure'] = pressure_base
        self.metrics['stability'] = stability_base
        self.metrics['hope'] = hope_base

    def set_ending_config(self, config):
        if config:
            self.ending_config = {**DEFAULT_ENDING_CONFIG, **config}

    def evaluate_tick(self, situation, decisions_text, resolution, date_str):
        """Evaluate metric changes for a tick using LLM."""
        max_delta = self.ending_config.get('max_delta', 15)
        prompt = f"""## {date_str} 事件
局势: {situation[:300]}
决策: {decisions_text[:300]}
结果: {resolution[:300]}

根据以上事件，评估以下四个指标的变化（每个指标变化范围 -{max_delta} ~ +{max_delta}）：
- darkness（黑暗度）: 战争、崩溃、压迫、灾难增加则上升
- pressure（压力值）: 失业、冲突、恐慌、资源匮乏增加则上升
- stability（稳定度）: 秩序、合作、制度完善则上升
- hope（希望值）: 创新、适应、进步、团结则上升

只输出合法JSON(数字不带+号): {{"darkness": 5, "pressure": -3, "stability": 2, "hope": 8, "notes": "简短说明"}}"""

        try:
            delta = llm_client.call_json([
                {'role': 'system', 'content': '你是世界推演指标评估师。根据事件评估指标变化。只输出JSON。'},
                {'role': 'user', 'content': prompt},
            ])

            for key in ('darkness', 'pressure', 'stability', 'hope'):
                val = delta.get(key, 0)
                delta[key] = max(-max_delta, min(max_delta, float(val)))

            for key in ('darkness', 'pressure', 'stability', 'hope'):
                self.metrics[key] = max(0, min(100, self.metrics[key] + delta.get(key, 0)))

            logger.info(f'Metrics: D={self.metrics["darkness"]:.1f} '
                        f'P={self.metrics["pressure"]:.1f} '
                        f'S={self.metrics["stability"]:.1f} '
                        f'H={self.metrics["hope"]:.1f}')
            return delta
        except Exception as e:
            logger.error(f'Metric evaluation failed: {e}')
            return {'darkness': 0, 'pressure': 0, 'stability': 0, 'hope': 0, 'notes': str(e)}

    def check_ending(self, tick, total_ticks):
        """Check if an ending should be triggered."""
        m = self.metrics
        cfg = self.ending_config

        if m['darkness'] >= cfg.get('bad_darkness', 90):
            return True, 'bad', '世界崩坏 - 黑暗值达到极点'
        if m['pressure'] >= cfg.get('bad_pressure', 95):
            return True, 'bad', '全面崩溃 - 社会压力无法承受'
        if (m['hope'] >= cfg.get('good_hope', 85)
                and m['stability'] >= cfg.get('good_stability', 60)):
            return True, 'good', '和平转型 - 希望与稳定共存'
        if tick >= total_ticks:
            return True, self._determine_ending_type(), '推演结束'
        return False, '', ''

    def _determine_ending_type(self):
        m = self.metrics
        cfg = self.ending_config
        if (m['hope'] > cfg.get('final_good_hope', 60)
                and m['stability'] > cfg.get('final_good_stability', 50)):
            return 'good'
        elif (m['darkness'] > cfg.get('final_bad_darkness', 70)
              or m['pressure'] > cfg.get('final_bad_pressure', 80)):
            return 'bad'
        elif (m['hope'] > cfg.get('bittersweet_hope', 40)
              and m['darkness'] > cfg.get('bittersweet_darkness', 40)):
            return 'bittersweet'
        else:
            return 'neutral'

    def get_ending_description(self, ending_type, scenario_question, timeline_summary):
        ending_labels = {
            'good': 'Good End - 曙光初现',
            'bad': 'Bad End - 黑暗降临',
            'bittersweet': 'Bittersweet End - 苦乐参半',
            'neutral': 'Neutral End - 未完之局',
        }
        label = ending_labels.get(ending_type, 'Unknown End')

        description = llm_client.call([
            {'role': 'system', 'content': (
                '你是推演总结分析师。写清晰、写实、易懂的结局总结。\n'
                '要求：\n'
                '- 用通俗中文，不要文言、不要华丽修辞\n'
                '- 不要编造具体人名或虚构事件，只基于提供的时间线总结\n'
                '- 从宏观角度总结：社会整体走向、主要矛盾如何演变、最终局面\n'
                '- 用数据和事实说话，不要讲故事\n'
            )},
            {'role': 'user', 'content': (
                f'推演问题: {scenario_question}\n'
                f'结局类型: {label}\n'
                f'最终指标 - 黑暗:{self.metrics["darkness"]:.0f} '
                f'压力:{self.metrics["pressure"]:.0f} '
                f'稳定:{self.metrics["stability"]:.0f} '
                f'希望:{self.metrics["hope"]:.0f}\n\n'
                f'时间线摘要:\n{timeline_summary[:1500]}\n\n'
                f'请用150-250字，从宏观角度总结这个推演的结局。要求：\n'
                f'1. 用通俗直白的语言\n'
                f'2. 总结社会整体演变方向\n'
                f'3. 说明最终各主要群体的状况\n'
                f'4. 不要编造具体人物名字\n'
                f'5. 体现{label}的基调'
            )},
        ])
        return description

    def get_metrics(self):
        return dict(self.metrics)
