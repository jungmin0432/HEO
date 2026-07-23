"""Pluggable LLM 백엔드.

- ClaudeClient : 실제 Claude 로 멀티모달→JSON 추출 (ANTHROPIC_API_KEY 필요)
- StubClient   : 키가 없을 때 도는 규칙기반 스텁. 파이프라인 배선/데모 확인용이며
                 평가 리포트의 '진짜 숫자'로 쓰면 안 된다(그렇게 표시된다).

키를 .env 에 넣는 순간 get_client() 가 ClaudeClient 로 바뀌고 리포트가 실제 값으로 채워진다.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Optional, Protocol

from . import config
from .schema import order_json_schema

SYSTEM_PROMPT_TEMPLATE = """너는 서울 을지로 인쇄·제작 상가의 'AI 제작통역사'다.
방문자의 말/사진/외국어 요청을, 상인이 그대로 승인할 수 있는 한국어 제작요청서(JSON)로 정리한다.
오늘은 {today} 이다.

규칙:
- ★ 모든 값은 반드시 '한국어'로 작성한다. 입력이 영어·중국어여도 item·colors·material·finish·
  pickup_method·due 를 한국어로 번역해 채운다.
  (예: business card/名片→명함, patch→자수패치, navy→남색, red→빨강, heat-seal→열접착,
   matte/哑光→무광, saddle stitch→중철제본, in person→현장수령, ship→배송,
   Friday/星期五→금요일, tomorrow→내일)  단 source_lang 은 코드(ko/en/zh)로 둔다.
- ★ 표기는 상인이 읽는 표준 형식으로 통일한다(주문서마다 제각각이면 안 된다):
  · item 은 업계 표준 품목명으로: 결혼식 초대장→청첩장, 배지/와펜/patch→자수패치,
    걸개형 대형 출력물(banner/横幅)→현수막(거치대형 소형만 배너), lookbook→룩북.
  · size 는 "숫자x숫자단위" 로(예: 3m x 1m, 90x50mm). 미터→m, by→x 로 통일.
    원형은 "직경 Ncm 원형" 형식으로 쓴다(예: 직경 5cm 원형).
  · 시각은 24시 "HH:MM" 으로: "저녁 6시 20분"→"18:20", "저녁 7시"→"19:00".
  · finish 용어 통일: 라미네이션→코팅, 광택→유광. 여러 개면 쉼표 없이 붙여 쓴다(예: 무광 코팅).
- 아래 스키마의 슬롯만 채운다. 입력에서 확정할 수 없는 값은 반드시 null 로 둔다. 절대 지어내지 않는다.
- quantity 는 정수. "두 개"/"a couple"/"两个" 처럼 자연어 수량도 정수로 변환한다.
- pages 는 책자·룩북·카탈로그 등 여러 쪽 인쇄물의 쪽수(정수)일 때만. 그 외는 null.
- print_mode 는 인쇄 방식(컬러/흑백/양면 컬러/별색 등). 인쇄물이 아니면 null.
- 가격·납기 가능여부·재고는 AI가 확정하지 않는다. budget 은 방문자가 명시했을 때만 채운다.
- colors 는 반드시 배열(없으면 []). 재료는 material, 가공/마감은 finish 로 분리한다.
- ★ 가공·마감이 언급되면 절대 빠뜨리지 말고 finish 에 담는다.
  (자수, 방수, 열접착, 코팅, 무광, 유광, 박, 재봉, 마킹, 중철제본, 무선제본, 실사출력, 각인 …)
  "자수로", "방수로", "코팅해서" 처럼 조사가 붙어도 마감이다.
- due 는 한국어로 정규화하되 ★상대 표현은 그대로 유지한다.
  "다음주 월요일"·"내일"·"이번주"·"모레" 는 그대로 쓴다. due 를 달력 날짜로 바꾸지 마라.
  시각만 24시 표기로 바꾼다(예: "오늘 6시반"→"오늘 18:30", 星期五→금요일, Friday→금요일).
- due_date 에는 due 를 오늘({today}) 기준 실제 날짜로 환산해 "YYYY-MM-DD (요일)" 로 적는다.
  (예: 오늘이 화요일이고 due 가 "금요일" → 이번주 금요일 날짜. "다음주 월요일" → 다음주 월요일 날짜.)
  환산이 애매하면(예: "12월 초") null 로 둔다. due 가 null 이면 due_date 도 null.
- source_lang 에 입력 언어(ko/en/zh 등)를 적는다.
- missing_slots 에는 필수 슬롯(item,size,quantity,material_or_finish,due,pickup_method) 중
  입력만으로 확정 불가라 상인 확인이 필요한 항목을 적는다."""


def system_prompt() -> str:
    """호출 시점의 오늘 날짜를 주입한 시스템 프롬프트. due_date 환산의 기준이 된다."""
    import datetime
    now = datetime.date.today()
    weekday = "월화수목금토일"[now.weekday()]
    return SYSTEM_PROMPT_TEMPLATE.format(today=f"{now.isoformat()} ({weekday}요일)")


@dataclass
class LLMResult:
    order: dict
    input_tokens: int
    output_tokens: int
    backend: str  # "claude" | "stub"


class LLMClient(Protocol):
    backend: str
    def translate(self, text: str) -> LLMResult: ...


# --------------------------------------------------------------------------
class ClaudeClient:
    backend = "claude"

    def __init__(self, model: Optional[str] = None):
        import anthropic  # 지연 임포트: 스텁만 쓸 땐 SDK 없어도 됨

        self.model = model or config.MODEL
        self.client = anthropic.Anthropic()
        self._schema = order_json_schema()

    def translate(self, text: str) -> LLMResult:
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=system_prompt(),
            output_config={"format": {"type": "json_schema", "schema": self._schema}},
            messages=[{"role": "user", "content": text}],
        )
        raw = next(b.text for b in resp.content if b.type == "text")
        order = json.loads(raw)
        return LLMResult(
            order=order,
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
            backend=self.backend,
        )


# --------------------------------------------------------------------------
def _extract_json(raw: str) -> str:
    """모델이 앞뒤에 설명을 붙여도 첫 {...} 블록만 안전하게 뽑는다."""
    raw = raw.strip()
    if raw.startswith("```"):  # ```json ... ``` 코드펜스 제거
        raw = raw.split("```", 2)[1].lstrip("json").strip() if raw.count("```") >= 2 else raw
    start = raw.find("{")
    if start == -1:
        return raw
    depth = 0
    for i in range(start, len(raw)):
        if raw[i] == "{":
            depth += 1
        elif raw[i] == "}":
            depth -= 1
            if depth == 0:
                return raw[start:i + 1]
    return raw[start:]


class _OpenAICompatClient:
    """OpenAI 호환 엔드포인트(로컬 GPU vLLM/Ollama · Gemini 등) 공통 호출부.

    structured output 을 JSON Schema 로 강제하되, 서버가 json_schema 를
    지원 안 하면 json_object 모드로 자동 폴백한다.
    """

    backend = "openai_compat"

    def __init__(self, base_url: str, model: str, api_key: str,
                 extra_params: Optional[dict] = None, max_tokens: int = 4096):
        import openai  # 지연 임포트: 이 백엔드 안 쓰면 SDK 없어도 됨

        self.base_url = base_url
        self.model = model
        self.client = openai.OpenAI(base_url=base_url, api_key=api_key)
        self._schema = order_json_schema()
        # 모델별 추가 파라미터(예: gpt-oss reasoning_effort). 미지원 백엔드는 빈 dict.
        self.extra_params = extra_params or {}
        # 사고형(thinking) 모델은 크게(잘림 방지), Groq 처럼 max_tokens 예약분이
        # 분당 한도(TPM)에 카운트되는 곳은 작게.
        self.max_tokens = max_tokens

    def _call(self, text: str, response_format: dict):
        return self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system_prompt()},
                      {"role": "user", "content": text}],
            response_format=response_format,
            temperature=0,
            max_tokens=self.max_tokens,
            **self.extra_params,
        )

    def translate(self, text: str) -> LLMResult:
        import openai
        schema_fmt = {"type": "json_schema",
                      "json_schema": {"name": "order", "schema": self._schema, "strict": True}}
        try:
            resp = self._call(text, schema_fmt)
        except openai.BadRequestError:
            # json_schema 미지원 서버(400)만 json_object 로 폴백.
            # 429(한도)·401(인증) 등은 폴백해도 또 실패 → 헛되이 호출 말고 그대로 올림.
            resp = self._call(text, {"type": "json_object"})

        raw = resp.choices[0].message.content or "{}"
        order = json.loads(_extract_json(raw))
        usage = getattr(resp, "usage", None)
        return LLMResult(
            order=order,
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
            backend=self.backend,
        )


class LocalClient(_OpenAICompatClient):
    """자체 GPU 서버의 오픈모델(Ollama/vLLM). API 과금 없음(비용 0).

    Ollama:  ollama serve  → http://localhost:11434/v1
    vLLM:    python -m vllm.entrypoints.openai.api_server ...  → http://host:8001/v1
    """

    backend = "local"

    def __init__(self):
        super().__init__(config.LOCAL_BASE_URL, config.LOCAL_MODEL, config.LOCAL_API_KEY)


class GeminiClient(_OpenAICompatClient):
    """Google Gemini (무료 티어). aistudio.google.com 에서 키 발급.

    OpenAI 호환 엔드포인트를 그대로 쓴다. 무료 한도 내 사용 → 비용 0 으로 기록.
    """

    backend = "gemini"

    def __init__(self):
        super().__init__(config.GEMINI_BASE_URL, config.GEMINI_MODEL, config.GEMINI_API_KEY)


class GroqClient(_OpenAICompatClient):
    """Groq (무료 티어, 한도 넉넉·매우 빠름). console.groq.com 에서 키 발급(gsk_...).

    오픈모델(Llama 3.3 등)을 OpenAI 호환으로 호출. 무료 한도 내 사용 → 비용 0.
    """

    backend = "groq"

    def __init__(self):
        # gpt-oss 계열은 reasoning_effort 로 사고량↓ → 다국어도 ~1초. (다른 모델엔 미적용)
        extra = {"reasoning_effort": "low"} if "gpt-oss" in config.GROQ_MODEL else {}
        # Groq 는 max_tokens '예약분'이 TPM 에 카운트됨 → 실사용(~250tok)에 맞춰 작게.
        super().__init__(config.GROQ_BASE_URL, config.GROQ_MODEL, config.GROQ_API_KEY,
                         extra_params=extra, max_tokens=1024)


# --------------------------------------------------------------------------
class StubClient:
    """규칙기반 스텁. 한국어 위주의 얕은 추출만 한다.

    존재 이유: 키 없이도 파이프라인 end-to-end 를 돌려보기 위함.
    다국어·자유발화에서 깨지도록 '일부러' 단순하게 뒀다 —
    이 취약함 자체가 평가 기준 2(기술적 공백: 룰 기반이 왜 깨지는가)의 대조군이 된다.
    """

    backend = "stub"

    _ITEMS = ["자수패치", "명함", "포스터", "간판", "스티커", "엽서", "현수막", "유니폼", "책자", "룩북"]
    _FINISH = ["열접착", "코팅", "박", "재봉", "무광", "유광", "중철", "무선제본"]
    _PICKUP = ["현장수령", "픽업", "배송", "택배"]

    def translate(self, text: str) -> LLMResult:
        order = {
            "item": next((w for w in self._ITEMS if w in text), None),
            "size": (m.group(0) if (m := re.search(r"\d+\s*[x×*]\s*\d+\s*mm|[Aa]\d", text)) else None),
            "quantity": (int(m.group(1)) if (m := re.search(r"(\d+)\s*(개|장|권|매|부)", text)) else None),
            "pages": (int(m.group(1)) if (m := re.search(r"(\d+)\s*(쪽|페이지|p)", text)) else None),
            "print_mode": ("컬러" if ("컬러" in text or "칼라" in text) else "흑백" if "흑백" in text else None),
            "material": None,
            "finish": next((w for w in self._FINISH if w in text), None),
            "colors": [c for c in ["남색", "주황", "빨강", "파랑", "검정", "흰색"] if c in text],
            "due": (m.group(0) if (m := re.search(r"오늘|내일|모레|금요일|\d+시", text)) else None),
            "due_date": None,  # 규칙기반은 날짜 환산 불가(대조군의 한계 그대로 둠)
            "pickup_method": next((w for w in self._PICKUP if w in text), None),
            "budget": None,
            "notes": None,
            "source_lang": "ko" if re.search(r"[가-힣]", text) else "unknown",
            "missing_slots": [],
        }
        # 스텁 토큰량은 추정치(대략). 실제 비용 비교에는 쓰지 않는다.
        approx_in = max(1, len(text) // 2)
        return LLMResult(order=order, input_tokens=approx_in, output_tokens=60, backend=self.backend)


def get_client(prefer_stub: bool = False) -> LLMClient:
    """백엔드 자동 선택. 우선순위: 로컬 GPU > Claude > 스텁.

    - EULJIRO_LOCAL_BASE_URL 설정 → LocalClient(자체 GPU 오픈모델, 무료)
    - ANTHROPIC_API_KEY 설정      → ClaudeClient
    - 둘 다 없으면              → StubClient(규칙기반)
    prefer_stub=True 면 강제로 스텁(평가 하네스 대조군용).
    """
    if prefer_stub:
        return StubClient()
    backend = config.active_backend()
    if backend == "local":
        return LocalClient()
    if backend == "groq":
        return GroqClient()
    if backend == "gemini":
        return GeminiClient()
    if backend == "claude":
        return ClaudeClient()
    return StubClient()
