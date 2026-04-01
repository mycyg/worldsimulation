"""Entity Generator - Batch generation with faction-based organization

Rich entity generation with backstory, pressure, goals system.
"""
import math
import logging
import time
from services.llm_client import llm_client

logger = logging.getLogger(__name__)

MAX_ENTITIES_PER_CALL = 15
MAX_PER_FACTION = 25


def _safe_float(val, default=50.0):
    """Safely convert to float, clamped 0-100."""
    try:
        return min(max(float(val), 0), 100)
    except (TypeError, ValueError):
        return default


def _infer_influence(entity_raw):
    """Infer influence from entity type and prominence as fallback.
    Uses log10 scale: influence = log10(affected_count) * 10.
    """
    etype = (entity_raw.get('t') or entity_raw.get('type') or 'Person').lower()
    prominence = entity_raw.get('pr') or entity_raw.get('prominence') or 5

    # Base affected people count by type
    base_counts = {
        'person': 50,           # Individual affects ~50 people
        'organization': 50000,  # Organization affects ~50K
        'institution': 500000,  # Institution affects ~500K
        'force': 5000000,       # Systemic force affects ~5M
    }
    count = base_counts.get(etype, 50)
    # Scale by prominence (1-10 → 0.3x to 3x)
    multiplier = 0.3 + (prominence / 10) * 2.7
    count = count * multiplier

    return round(math.log10(max(count, 1)) * 10, 1)


class EntityGenerator:
    def generate_all(self, background, question, entity_count, documents=''):
        """Master generation flow: factions -> entities per faction."""
        logger.info(f'Starting generation of {entity_count} entities...')
        framework = self._generate_factions(background, question, entity_count, documents)
        narrator_persona = framework.get('narrator_persona', '客观描述局势')
        factions = framework.get('factions', [])

        if not factions:
            raise ValueError('Faction generation failed')

        logger.info(f'Generated {len(factions)} factions: '
                     f'{", ".join(f["name"] + "(" + str(f["count"]) + ")" for f in factions)}')

        # Phase 2: Generate entities per faction
        all_entities = []
        factions_summary = {}
        for f in factions:
            fname = f['name']
            fcount = f['count']
            logger.info(f'Generating {fcount} entities for [{fname}]...')

            try:
                raw_entities = self._generate_faction_entities(f, background, question, documents)
                for i, e in enumerate(raw_entities):
                    e['faction'] = fname
                    e['prominence'] = e.get('prominence', 5)
                    e['tags'] = f'{e.get("type", "Person")},{fname}'
                all_entities.extend(raw_entities)
                factions_summary[fname] = len(raw_entities)
                logger.info(f'  [{fname}]: {len(raw_entities)} entities')
            except Exception as e:
                logger.error(f'  [{fname}] generation failed: {e}')

            time.sleep(0.5)

        if not all_entities:
            raise ValueError('No entities generated')

        logger.info(f'Total: {len(all_entities)} entities')
        return {
            'entities': all_entities,
            'narrator_persona': narrator_persona,
            'factions_summary': factions_summary,
        }

    def _generate_factions(self, background, question, entity_count, documents=''):
        """Generate 6-8 factions with capped counts."""
        doc_section = ''
        if documents:
            doc_section = (
                f'\n参考素材（请从素材中提炼真实存在的利益群体/组织/阶层）:\n{documents[:2000]}\n\n'
            )

        result = llm_client.call_json([
            {'role': 'system', 'content': '你是世界推演架构师。设计推演阵营。只输出紧凑JSON。阵营名必须写实、专业、接地气。'},
            {'role': 'user', 'content': (
                f'场景:{background[:500]}\n问题:{question}\n\n'
                f'{doc_section}'
                f'设计6-8个阵营，总计{entity_count}个实体。输出JSON:\n'
                f'{{"narrator_persona":"20字","factions":[{{"n":"阵营名","c":数量}}]}}\n\n'
                f'阵营命名要求：写实、专业、符合现实社会用语。用群体/行业/机构类型描述，不要虚构具体名称。\n'
                f'- 好例子: "国家部委","互联网大厂","制造业中小企业","科技创业公司","基层社区工作者","高校研究机构","自由职业者群体"\n'
                f'- 坏例子（禁止）: "黑暗联盟","绝望狂徒","自救军","末日组织"或任何虚构人名/企业名\n'
                + (f'\n- 阵营名必须参考素材中出现的真实组织、群体类型名称\n' if documents else '')
                + f'覆盖政府机构/企业/劳工/金融/教育/社会组织/国际力量。count总和≈{entity_count}。只输出JSON。'
            )},
        ])
        # Normalize keys
        if result.get('factions'):
            result['factions'] = [
                {
                    'name': f.get('n') or f.get('name') or '未知',
                    'count': min(f.get('c') or f.get('count') or 10, MAX_PER_FACTION),
                }
                for f in result['factions']
            ]
        return result

    def _generate_faction_entities(self, faction, background, question, documents=''):
        """Generate entities for a faction in batches - with rich backstory and influence."""
        total = faction['count']
        all_raw = []

        doc_section = ''
        if documents:
            doc_section = (
                f'\n参考素材（实体名称、角色、背景应基于素材中的真实人物/组织）:\n'
                f'{documents[:2500]}\n'
            )

        for offset in range(0, total, MAX_ENTITIES_PER_CALL):
            batch_count = min(MAX_ENTITIES_PER_CALL, total - offset)
            batch_label = (f'({offset + 1}-{offset + batch_count}/{total})'
                           if total > MAX_ENTITIES_PER_CALL else f'({total}个)')

            result = llm_client.call_json([
                {'role': 'system', 'content': (
                    f'为"{faction["name"]}"阵营生成{batch_count}个实体。\n'
                    f'每个实体需要有丰富的背景故事和真实感。\n'
                    f'只输出JSON。'
                )},
                {'role': 'user', 'content': (
                    f'场景背景:{background[:500]}\n核心问题:{question}\n'
                    f'阵营:{faction["name"]}{batch_label}\n'
                    f'{doc_section}\n'
                    f'输出JSON格式:\n'
                    f'{{"entities":[{{'
                    f'"n":"名称",'
                    f'"t":"Person|Organization|Institution|Force",'
                    f'"d":"40字背景描述-说明这个实体是谁、做什么、面临什么处境",'
                    f'"backstory":"80-120字详细背景故事-说明当前面临的具体压力和困境，'
                    f'比如失业风险、经济压力、家庭负担、职业危机、生存威胁等",'
                    f'"p":"性格/立场",'
                    f'"s":"初始状态",'
                    f'"m":"核心动机",'
                    f'"stg":"短期诉求-当前最紧迫的需求（如保住工作、还清贷款、养家糊口）",'
                    f'"ltg":"长期诉求-真正的长期利益（如职业转型、阶层跃升、制度变革）",'
                    f'"stu":50,'
                    f'"pd":"当前面临的主要压力源描述（30字以内）",'
                    f'"pv":50,'
                    f'"pr":5,'
                    f'"inf":50}}]}}\n\n'
                    f'【命名规则——严格禁止虚构人名和公司名！】\n'
                    f'实体名称(n)必须使用通用描述，不要编造具体人名或企业名：\n'
                    f'- Person类型：用职业+群体描述，如"35岁失业程序员"、"基层社区网格员"、"外卖骑手代表"、"应届毕业生"、"中年转行教师"、"小微企业主"\n'
                    f'- Organization类型：用行业+规模描述，如"大型互联网公司"、"中型制造业企业"、"社区基层服务站"、"连锁餐饮品牌"、"地方商业银行"\n'
                    f'- Institution类型：用机构性质描述，如"地方人社局"、"行业协会联合会"、"国家发改委产业司"、"城市统计局"\n'
                    f'- Force类型：用趋势/力量描述，如"AI技术替代浪潮"、"人口老龄化趋势"、"城镇化迁移群体"\n'
                    f'- 禁止示例（绝对不允许）："张伟"、"李明"、"林墨"、"字节跳动"、"阿里巴巴"\n'
                    f'- 正确示例："35岁中年失业产品经理"、"大型电商平台"、"国家工信部"\n\n'
                    f'其他关键要求:\n'
                    f'1. 每个实体要有真实、具体的个人/组织困境，不要泛泛而谈\n'
                    f'2. backstory要体现该实体在当前场景下具体面临什么威胁或机会\n'
                    f'3. 短期诉求和长期诉求要有张力——比如短期要保饭碗vs长期要转型\n'
                    f'4. pv(压力值)要合理：失业边缘的人压力高(70-90)，稳定岗位压力低(20-40)\n'
                    f'5. pr=重要度1-10\n'
                    f'6. inf(影响力)使用对数刻度: inf=round(log10(影响人数)*10,1)\n'
                    f'   举例：国家部委→inf≈75-85；大公司→inf≈60-70；基层→inf≈20-30；失业个人→inf≈10-15\n'
                    f'   只输出JSON。'
                    + (f'\n7. 如果素材中有具体数据（人数、收入、政策名称等），在实体背景中体现这些数据' if documents else '')
                )},
            ], temperature=0.7, max_tokens=4096)

            raw = result.get('entities', [])
            all_raw.extend(raw)

            if raw and len(raw) < batch_count:
                time.sleep(0.3)

        # Normalize
        return [
            {
                'name': e.get('n') or e.get('name') or '未命名',
                'type': e.get('t') or e.get('type') or 'Person',
                'description': e.get('d') or e.get('description') or '',
                'backstory': e.get('backstory') or '',
                'personality': e.get('p') or e.get('personality') or '',
                'initial_status': e.get('s') or e.get('initial_status') or '',
                'motivation': e.get('m') or e.get('motivation') or '',
                'short_term_goal': e.get('stg') or e.get('short_term_goal') or '',
                'long_term_goal': e.get('ltg') or e.get('long_term_goal') or '',
                'short_term_urgency': _safe_float(e.get('stu') or e.get('short_term_urgency'), 50),
                'pressure': _safe_float(e.get('pv') or e.get('pressure'), 50),
                'pressure_desc': e.get('pd') or '',
                'prominence': e.get('pr') or e.get('prominence') or 5,
                'influence': _safe_float(e.get('inf') or e.get('influence'), _infer_influence(e)),
            }
            for e in all_raw
        ]
