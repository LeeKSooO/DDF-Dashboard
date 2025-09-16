"""
Large Language Model service with fallback structure
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional, Union
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseLanguageModel

from app.core.config import settings
from app.core.exceptions import LLMServiceException, ConfigurationException

logger = logging.getLogger(__name__)


class LLMService:
    """Service for LLM operations with fallback structure using top-performing models"""

    def __init__(self):
        self.primary_llm: Optional[BaseLanguageModel] = None
        self.fallback_llms: List[BaseLanguageModel] = []
        self.langchain_llm: Optional[BaseLanguageModel] = None
        self.current_model_name: str = "unknown"
        self._initialized = False
        self._health_status = False
        self.enable_cot = True
        self.reasoning_steps: List[str] = []

        # Model configurations based on user request (새로운 폴백 순서)
        self.model_configs = [
            {
                "name": "GPT-4o-mini",
                "type": "openai",
                "model_id": "gpt-4o-mini",
                "score": 0.960,
                "priority": 1,
                "description": "OpenAI GPT-4o Mini 모델 (1순위)"
            },
            {
                "name": "Claude-4-Sonnet",
                "type": "anthropic",
                "model_id": "claude-3-5-sonnet-20241022",
                "score": 0.975,
                "priority": 2,
                "description": "Anthropic Claude 4 Sonnet 모델 (2순위)"
            },
            {
                "name": "GPT-5-Chat-Latest",
                "type": "openai",
                "model_id": "gpt-5-chat-latest",
                "score": 0.985,
                "priority": 3,
                "description": "OpenAI 최신 GPT-5 Chat Latest 모델 (3순위 폴백)"
            }
        ]

    async def initialize(self) -> None:
        """Initialize LLM service with fallback structure"""

        if self._initialized:
            return

        logger.info("🚀 Initializing LLM service with fallback structure...")

        try:
            # Initialize models in priority order
            initialized_models = []

            for config in self.model_configs:
                try:
                    model = await self._create_model(config)
                    if model:
                        initialized_models.append({
                            "model": model,
                            "config": config
                        })
                        logger.info(f"✅ {config['name']} initialized successfully")
                    else:
                        logger.warning(f"⚠️ Failed to initialize {config['name']}")

                except Exception as e:
                    logger.warning(f"⚠️ {config['name']} initialization failed: {e}")
                    continue

            if not initialized_models:
                raise LLMServiceException("No models could be initialized")

            # Set primary and fallback models
            self.primary_llm = initialized_models[0]["model"]
            self.current_model_name = initialized_models[0]["config"]["name"]
            self.langchain_llm = self.primary_llm

            # Set fallback models
            self.fallback_llms = [item["model"] for item in initialized_models[1:]]

            logger.info(f"🎯 Primary model: {self.current_model_name}")
            logger.info(f"🔄 Fallback models: {len(self.fallback_llms)} available")

            # Test primary model
            await self._test_connection()

            self._initialized = True
            self._health_status = True

            logger.info("✅ LLM service with fallback structure initialized successfully")

        except Exception as e:
            self._health_status = False
            logger.error(f"❌ Failed to initialize LLM service: {e}")
            raise LLMServiceException(f"LLM service initialization failed: {str(e)}")

    async def _create_model(self, config: Dict[str, Any]) -> Optional[BaseLanguageModel]:
        """Create model instance based on configuration"""

        try:
            if config["type"] == "openai":
                if not settings.OPENAI_API_KEY:
                    logger.warning(f"OpenAI API key not found, skipping {config['name']}")
                    return None

                return ChatOpenAI(
                    model=config["model_id"],
                    temperature=0.05 if self.enable_cot else 0.1,
                    max_tokens=8000,
                    api_key=settings.OPENAI_API_KEY,
                    request_timeout=120
                )

            elif config["type"] == "anthropic":
                if not settings.ANTHROPIC_API_KEY:
                    logger.warning(f"Anthropic API key not found, skipping {config['name']}")
                    return None

                return ChatAnthropic(
                    model=config["model_id"],
                    temperature=0.05 if self.enable_cot else 0.1,
                    max_tokens=8000,
                    api_key=settings.ANTHROPIC_API_KEY,
                    timeout=120
                )

            else:
                logger.warning(f"Unknown model type: {config['type']}")
                return None

        except Exception as e:
            logger.error(f"Failed to create {config['name']}: {e}")
            return None

    async def _test_connection(self) -> None:
        """Test primary model connection"""

        try:
            if not self.primary_llm:
                raise Exception("No primary model available")

            # Simple test generation
            test_prompt = "Test connection: What is 1+1? Answer briefly."
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.primary_llm.invoke(test_prompt)
            )

            if not response or not response.content:
                raise Exception("Empty response from primary model")

            logger.info(f"✅ {self.current_model_name} connection test successful")

        except Exception as e:
            logger.error(f"❌ {self.current_model_name} connection test failed: {e}")
            raise

    async def generate_text(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> str:
        """Generate text with fallback mechanism"""

        if not self._initialized:
            raise LLMServiceException("LLM service not initialized")

        # CoT 프롬프트 개선 적용
        if self.enable_cot and "단계별" not in prompt and "step-by-step" not in prompt:
            prompt = self._enhance_prompt_with_cot(prompt)

        # Try primary model first
        models_to_try = [self.primary_llm] + self.fallback_llms
        last_error = None

        for i, model in enumerate(models_to_try):
            try:
                logger.debug(f"Attempting generation with model {i+1}/{len(models_to_try)}")

                response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: model.invoke(prompt)
                )

                # Extract content from response
                if hasattr(response, 'content'):
                    response_text = response.content
                else:
                    response_text = str(response)

                if not response_text:
                    raise Exception("Empty response")

                # CoT 추론 단계 추출
                if self.enable_cot:
                    self._extract_reasoning_steps(response_text)

                # Update current model if fallback was used
                if i > 0:
                    model_config = self.model_configs[min(i, len(self.model_configs)-1)]
                    logger.warning(f"🔄 Switched to fallback model: {model_config['name']}")
                    self.current_model_name = model_config["name"]

                logger.debug(f"Generated text: {response_text[:100]}...")
                return response_text

            except Exception as e:
                last_error = e
                logger.warning(f"Model {i+1} failed: {e}")
                continue

        # All models failed
        raise LLMServiceException(f"All models failed. Last error: {str(last_error)}")

    async def generate_with_langchain(self, prompt: str, **kwargs) -> str:
        """Generate text using current LangChain model with fallback"""

        if not self._initialized or not self.langchain_llm:
            raise LLMServiceException("LangChain LLM not initialized")

        try:
            # Try current langchain model
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.langchain_llm.invoke(prompt, **kwargs)
            )

            # Extract content from response
            if hasattr(response, 'content'):
                return response.content
            else:
                return str(response)

        except Exception as e:
            logger.warning(f"LangChain model failed, trying fallback: {e}")

            # Fallback to generate_text method
            return await self.generate_text(prompt, **kwargs)

    async def batch_generate(
        self,
        prompts: List[str],
        **kwargs
    ) -> List[str]:
        """Generate text for multiple prompts with fallback"""

        if not self._initialized:
            raise LLMServiceException("LLM service not initialized")

        try:
            tasks = []
            for prompt in prompts:
                task = self.generate_text(prompt, **kwargs)
                tasks.append(task)

            responses = await asyncio.gather(*tasks, return_exceptions=True)

            # Handle exceptions in results
            results = []
            for i, response in enumerate(responses):
                if isinstance(response, Exception):
                    logger.error(f"Batch generation failed for prompt {i}: {response}")
                    results.append(f"Error: {str(response)}")
                else:
                    results.append(response)

            return results

        except Exception as e:
            logger.error(f"Batch generation failed: {e}")
            raise LLMServiceException(f"Batch generation failed: {str(e)}")

    async def health_check(self) -> bool:
        """Check service health with fallback testing"""

        if not self._initialized:
            return False

        try:
            # Quick health check with primary model
            test_response = await self.generate_text(
                "Health check: Say 'OK'",
                max_tokens=5,
                temperature=0.0
            )

            self._health_status = bool(test_response)
            return self._health_status

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            self._health_status = False
            return False

    async def get_model_info(self) -> Dict[str, Any]:
        """Get current model information"""

        if not self._initialized:
            raise LLMServiceException("LLM service not initialized")

        return {
            "current_model": self.current_model_name,
            "primary_model": self.model_configs[0]["name"],
            "available_fallbacks": len(self.fallback_llms),
            "total_models": len([m for m in [self.primary_llm] + self.fallback_llms if m is not None]),
            "initialized": self._initialized,
            "health_status": self._health_status,
            "cot_enabled": self.enable_cot,
            "last_health_check": datetime.utcnow().isoformat()
        }

    async def switch_to_fallback(self, fallback_index: int = 0) -> bool:
        """Manually switch to a specific fallback model"""

        if not self._initialized:
            raise LLMServiceException("LLM service not initialized")

        if fallback_index >= len(self.fallback_llms):
            raise LLMServiceException(f"Fallback index {fallback_index} out of range")

        try:
            # Switch primary model
            old_model = self.current_model_name
            self.primary_llm = self.fallback_llms[fallback_index]
            self.langchain_llm = self.primary_llm
            self.current_model_name = self.model_configs[fallback_index + 1]["name"]

            # Test new primary model
            await self._test_connection()

            logger.info(f"🔄 Switched from {old_model} to {self.current_model_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to switch to fallback model: {e}")
            return False

    async def get_fallback_status(self) -> Dict[str, Any]:
        """Get status of all available models"""

        status = {
            "primary": {
                "name": self.current_model_name,
                "available": self.primary_llm is not None,
                "config": next((c for c in self.model_configs if c["name"] == self.current_model_name), {})
            },
            "fallbacks": []
        }

        for i, model in enumerate(self.fallback_llms):
            config = self.model_configs[i + 1] if i + 1 < len(self.model_configs) else {}
            status["fallbacks"].append({
                "index": i,
                "name": config.get("name", f"Fallback-{i}"),
                "available": model is not None,
                "config": config
            })

        return status

    async def cleanup(self) -> None:
        """Cleanup resources"""

        logger.info("🧹 Cleaning up LLM service...")

        self.primary_llm = None
        self.fallback_llms = []
        self.langchain_llm = None
        self.current_model_name = "unknown"
        self._initialized = False
        self._health_status = False

        logger.info("✅ LLM service cleanup completed")

    def _enhance_prompt_with_cot(self, prompt: str) -> str:
        """
        일반 프롬프트를 CoT 구조로 개선

        DRT 도메인에 특화된 CoT 가이드라인:
        1. 문제 이해 단계
        2. 관련 정보 분석 단계
        3. 논리적 추론 단계
        4. 결론 도출 단계
        """
        cot_prefix = """DRT 교통 전문가로서 다음과 같이 간결하고 명료하게 분석해주세요:

🔍 **핵심 분석**: 질문의 핵심 요소 파악 및 DRT 관련성 식별

📊 **데이터 검토**: 제공된 데이터의 주요 패턴과 의미 분석

🧠 **논리적 추론**: 핵심 인사이트 도출 및 실용적 시사점

✅ **결론**: 주요 발견사항과 구체적 제안사항

**중요**: 각 단계는 2-3문장으로 간결하게 작성하고, 전체 답변은 1000자 이내로 제한해주세요.

질문: """
        return cot_prefix + prompt

    def _extract_reasoning_steps(self, response: str) -> None:
        """응답에서 추론 단계를 추출하여 저장"""
        self.reasoning_steps = []
        if "1단계:" in response:
            steps = response.split("단계:")
            for i, step in enumerate(steps[1:], 1):
                clean_step = step.split("🔍📊🧠✅")[0].strip()
                if clean_step:
                    self.reasoning_steps.append(f"단계{i}: {clean_step[:100]}...")

    def get_reasoning_steps(self) -> List[str]:
        """추론 단계 반환"""
        return self.reasoning_steps.copy()

    def set_cot_mode(self, enable: bool) -> None:
        """CoT 모드 설정"""
        self.enable_cot = enable
        logger.info(f"CoT mode set to: {enable}")

        # Update model temperatures for CoT mode
        if self._initialized:
            try:
                # Update primary model
                if hasattr(self.primary_llm, 'temperature'):
                    self.primary_llm.temperature = 0.05 if enable else 0.1

                # Update fallback models
                for model in self.fallback_llms:
                    if hasattr(model, 'temperature'):
                        model.temperature = 0.05 if enable else 0.1

                logger.info(f"Model temperatures updated for CoT mode: {enable}")

            except Exception as e:
                logger.warning(f"Could not update model temperatures: {e}")