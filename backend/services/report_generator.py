"""Report Generator"""
import logging
from models.database import get_session, Scenario, Entity, Round, TimelineEvent, MetricsHistory, Report
from services.llm_client import llm_client

logger = logging.getLogger(__name__)


class ReportGenerator:
    def generate(self, scenario_id):
        """Generate a full simulation report."""
        session = get_session()
        try:
            scenario = session.query(Scenario).get(scenario_id)
            if not scenario:
                raise ValueError('Scenario not found')

            # Gather timeline
            events = session.query(TimelineEvent).filter_by(scenario_id=scenario_id)\
                .order_by(TimelineEvent.round_number).all()
            timeline_text = '\n\n'.join(
                f'### {e.year}年 (Round {e.round_number})\n{e.content}'
                for e in events
            )

            # Entity final states
            entities = session.query(Entity).filter_by(scenario_id=scenario_id).all()
            active_count = sum(1 for e in entities if e.status == 'active')
            states = '\n'.join(
                f'{e.name}({e.type}/{e.faction}): {e.status} R={e.resources} {e.current_state}'
                for e in entities[:50]
            )

            # Metrics history
            last_metrics = session.query(MetricsHistory).filter_by(scenario_id=scenario_id)\
                .order_by(MetricsHistory.id.desc()).first()
            final_metrics = {
                'darkness': last_metrics.darkness if last_metrics else 0,
                'pressure': last_metrics.pressure if last_metrics else 0,
                'stability': last_metrics.stability if last_metrics else 50,
                'hope': last_metrics.hope if last_metrics else 50,
            }

            # Determine ending type
            ending_type = 'neutral'
            if final_metrics['hope'] > 60 and final_metrics['stability'] > 50:
                ending_type = 'good'
            elif final_metrics['darkness'] > 70 or final_metrics['pressure'] > 80:
                ending_type = 'bad'
            elif final_metrics['hope'] > 40 and final_metrics['darkness'] > 40:
                ending_type = 'bittersweet'

            # Generate report via LLM
            report_content = llm_client.call([
                {'role': 'system', 'content': (
                    '你是社会政策分析师。你的任务是写一份清晰、写实、通俗易懂的推演总结报告。\n'
                    '严格要求：\n'
                    '- 用通俗直白的中文，像给普通读者看的政策分析文章\n'
                    '- 不要编造具体人名、公司名（除非时间线中确实提到）\n'
                    '- 不要讲故事、不要写小说、不要华丽修辞\n'
                    '- 用宏观视角总结趋势和变化，用数据和事实说话\n'
                    '- 每段文字要让普通读者一看就懂\n'
                    '- 不要用"智极智芯""拾光巷""星火"等编造的具体名称'
                )},
                {'role': 'user', 'content': (
                    f'## 推演问题\n{scenario.question}\n\n'
                    f'## 背景\n{scenario.background}\n\n'
                    f'## 时间线（以下为推演过程中生成的局势和事件摘要）\n{timeline_text[:3000]}\n\n'
                    f'## 实体最终状态 ({active_count}个活跃 / {len(entities)}个总计)\n{states}\n\n'
                    f'## 最终指标\n'
                    f'黑暗度:{final_metrics["darkness"]:.0f} '
                    f'压力:{final_metrics["pressure"]:.0f} '
                    f'稳定:{final_metrics["stability"]:.0f} '
                    f'希望:{final_metrics["hope"]:.0f}\n\n'
                    f'请基于以上推演数据，写一份通俗易懂的分析报告。要求：\n'
                    f'1. **结论概要** — 用2-3句话概括整体走向，不要编造数据\n'
                    f'2. **关键转折点** — 按年份列出每年的主要变化，用宏观描述（如"失业率上升""政策调整"），不要编造具体人物\n'
                    f'3. **各阵营命运** — 按阵营类型（政府部门、企业、劳工组织等）总结各自演变，不要编造人名\n'
                    f'4. **社会影响分析** — 从就业、经济、政治、教育四个维度分析，用通俗语言\n'
                    f'5. **回答推演问题** — 直接回答核心问题\n'
                    f'6. **结局评估** — 基于四指标解释为什么是这个结局\n'
                    f'7. **可能的出路** — 提出建议（如有）\n'
                    f'8. **推演局限性** — 本推演的不足之处\n\n'
                    f'再次强调：不要编造人物名字和具体事件细节，只基于上面提供的时间线做宏观总结。'
                )},
            ], temperature=0.5, max_tokens=6000)

            # Save report
            existing = session.query(Report).filter_by(scenario_id=scenario_id).first()
            if existing:
                existing.content = report_content
                existing.ending_type = ending_type
            else:
                session.add(Report(
                    scenario_id=scenario_id,
                    content=report_content,
                    ending_type=ending_type,
                ))
            session.commit()

            return {
                'content': report_content,
                'ending_type': ending_type,
                'metrics': final_metrics,
            }
        finally:
            session.close()
