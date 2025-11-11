"""
Volc Ark LLM Client
- 支持 https://ark.cn-beijing.volces.com/api/v3/chat/completions
- 使用配置或环境变量：
  - api_base: 完整URL
  - api_key: 明文Key（可用环境变量 VOLC_API_KEY 覆盖）
  - model_id: 例如 ep-20241217194410-r674k
"""

from typing import List, Dict, Optional
import os


class VolcLLM:
    def __init__(self, api_base: str, api_key: str, model_id: str):
        self.api_base = api_base
        self.api_key = os.getenv("VOLC_API_KEY", api_key)
        self.model_id = model_id

    def chat(self, messages: List[Dict], temperature: float = 0.2, max_tokens: Optional[int] = None) -> str:
        import requests

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": self.model_id,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        r = requests.post(self.api_base, headers=headers, json=payload, timeout=15)
        r.raise_for_status()
        data = r.json()
        # 兼容 Ark 返回结构（参考 OpenAI 样式）
        try:
            return data["choices"][0]["message"]["content"]
        except Exception:
            # 尝试其它字段
            return str(data)


def build_volc_from_config(cfg: Dict) -> Optional[VolcLLM]:
    llm_cfg = cfg.get("llm", {})
    provider = llm_cfg.get("provider")
    if provider != "volc":
        return None
    api_base = llm_cfg.get("api_base")
    api_key = llm_cfg.get("api_key")
    model_id = llm_cfg.get("model_id")
    if not (api_base and (os.getenv("VOLC_API_KEY") or api_key) and model_id):
        return None
    return VolcLLM(api_base=api_base, api_key=api_key or "", model_id=model_id)