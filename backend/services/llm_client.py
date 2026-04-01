"""LLM Client - OpenAI-compatible API with JSON repair"""
import re
import json
import logging
from openai import OpenAI
from config import Config

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self, api_key=None, base_url=None, model=None):
        self.client = OpenAI(
            api_key=api_key or Config.LLM_API_KEY,
            base_url=base_url or Config.LLM_BASE_URL,
        )
        self.model = model or Config.LLM_MODEL

    def call(self, messages, temperature=0.7, max_tokens=4096):
        """Call LLM and return text response."""
        kwargs = dict(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        # Add reasoning_effort for models that support it (doubao-seed series)
        if 'seed' in self.model or 'ep-' in self.model:
            kwargs['extra_body'] = {'reasoning_effort': 'minimal'}
        resp = self.client.chat.completions.create(**kwargs)
        content = resp.choices[0].message.content
        # Strip <thinkrangle> tags (compatible with some models)
        content = re.sub(r'<think[^>]*>.*?</think[^>]*>', '', content, flags=re.DOTALL).strip()
        if not content:
            raise ValueError('LLM returned empty response')
        return content

    def call_json(self, messages, temperature=0.3, max_tokens=4096):
        """Call LLM and parse JSON response with robust fallback."""
        # Augment last message to request JSON
        augmented = messages[:]
        if augmented and augmented[-1].get('role') == 'user':
            augmented[-1] = {
                **augmented[-1],
                'content': augmented[-1]['content'] + '\n\n[只输出纯JSON，不要输出其他文字，每个字段不超过30字]'
            }

        text = self.call(augmented, temperature, max_tokens)
        return self._parse_json(text)

    @staticmethod
    def _parse_json(text):
        """Parse JSON from LLM response with multiple fallback strategies."""
        if not text or not isinstance(text, str):
            raise ValueError('Empty response')

        # Pre-process: remove leading + from numbers (invalid JSON)
        text = re.sub(r'(?<=[\[:,\s])\+(\d)', r'\1', text)

        # Strategy 1: Direct parse
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            pass

        # Strategy 2: Strip markdown code blocks
        cleaned = re.sub(r'^```(?:json)?\s*\n?', '', text, flags=re.IGNORECASE)
        cleaned = re.sub(r'\n?```\s*$', '', cleaned).strip()
        try:
            return json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            pass

        # Strategy 3: Extract JSON object
        match = re.search(r'\{[\s\S]*\}', cleaned)
        if match:
            try:
                return json.loads(match.group())
            except (json.JSONDecodeError, ValueError):
                pass

        # Strategy 4: Truncation repair
        match = re.search(r'\{[\s\S]*', cleaned)
        if match:
            partial = match.group().rstrip()
            # Try multiple truncation levels
            for trim in range(0, 120):
                p = partial[:len(partial) - trim] if trim > 0 else partial
                # Remove incomplete trailing element in array (partial dict)
                p = re.sub(r',?\s*\{[^}]*$', '', p)
                # Remove incomplete trailing key/value
                p = re.sub(r',?\s*"[^"]*"\s*:?\s*"?[^"]*$', '', p)
                # Count unclosed brackets
                open_b = p.count('{') - p.count('}')
                open_br = p.count('[') - p.count(']')
                for _ in range(max(open_br, 0)):
                    p += ']'
                for _ in range(max(open_b, 0)):
                    p += '}'
                try:
                    return json.loads(p)
                except (json.JSONDecodeError, ValueError):
                    continue

        raise ValueError(f'JSON parse failed: {text[:200]}')


# Singleton
llm_client = LLMClient()
