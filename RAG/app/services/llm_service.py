"""
Large Language Model service
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime

from langchain_community.llms import WatsonxLLM
from ibm_watsonx_ai import Credentials, APIClient
from ibm_watsonx_ai.foundation_models import Model

from app.core.config import settings
from app.core.exceptions import LLMServiceException, ConfigurationException


logger = logging.getLogger(__name__)


class LLMService:
    """Service for LLM operations using IBM Watson AI"""
    
    def __init__(self):
        self.client: Optional[APIClient] = None
        self.model: Optional[Model] = None
        self.langchain_llm: Optional[WatsonxLLM] = None
        self._initialized = False
        self._health_status = False
    
    async def initialize(self) -> None:
        """Initialize Watson AI client and model"""
        
        if self._initialized:
            return
        
        logger.info("🚀 Initializing Watson AI LLM service...")
        
        try:
            # Validate configuration
            if not all([
                settings.WATSON_API_KEY,
                settings.WATSON_URL,
                settings.WATSON_PROJECT_ID
            ]):
                raise ConfigurationException(
                    "Watson AI configuration incomplete. Please set WATSON_API_KEY, WATSON_URL, and WATSON_PROJECT_ID"
                )
            
            # Setup credentials
            credentials = Credentials(
                url=settings.WATSON_URL,
                api_key=settings.WATSON_API_KEY
            )
            
            # Initialize API client
            self.client = APIClient(credentials)
            self.client.set.default_project(settings.WATSON_PROJECT_ID)
            
            # Initialize model
            self.model = Model(
                model_id=settings.WATSON_MODEL_ID,
                params={
                    "decoding_method": "greedy",
                    "max_new_tokens": 1000,
                    "temperature": 0.1,
                    "top_p": 1.0,
                    "top_k": 50,
                    "repetition_penalty": 1.0,
                    "stop_sequences": ["<|endoftext|>"]
                },
                credentials=credentials,
                project_id=settings.WATSON_PROJECT_ID
            )
            
            # Initialize LangChain wrapper
            self.langchain_llm = WatsonxLLM(
                model_id=settings.WATSON_MODEL_ID,
                url=settings.WATSON_URL,
                apikey=settings.WATSON_API_KEY,
                project_id=settings.WATSON_PROJECT_ID,
                params={
                    "decoding_method": "greedy",
                    "max_new_tokens": 1000,
                    "temperature": 0.1
                }
            )
            
            # Test connection
            await self._test_connection()
            
            self._initialized = True
            self._health_status = True
            
            logger.info("✅ Watson AI LLM service initialized successfully")
            
        except Exception as e:
            self._health_status = False
            logger.error(f"❌ Failed to initialize Watson AI LLM service: {e}")
            raise LLMServiceException(f"LLM service initialization failed: {str(e)}")
    
    async def _test_connection(self) -> None:
        """Test Watson AI connection"""
        
        try:
            # Simple test generation
            test_prompt = "Test connection: What is 1+1?"
            response = self.model.generate_text(prompt=test_prompt, guardrails=False)
            
            if not response:
                raise Exception("Empty response from Watson AI")
            
            logger.info("✅ Watson AI connection test successful")
            
        except Exception as e:
            logger.error(f"❌ Watson AI connection test failed: {e}")
            raise
    
    async def generate_text(
        self, 
        prompt: str, 
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> str:
        """Generate text using Watson AI"""
        
        if not self._initialized:
            raise LLMServiceException("LLM service not initialized")
        
        try:
            # 단순하게 기본 파라미터로만 호출 (동적 파라미터는 일단 무시)
            logger.debug(f"Generating text for prompt: {prompt[:100]}...")
            response = self.model.generate_text(prompt=prompt)
            
            if not response:
                raise LLMServiceException("Empty response from Watson AI")
            
            logger.debug(f"Generated text: {response[:100]}...")
            return response
            
        except Exception as e:
            logger.error(f"Text generation failed: {e}")
            raise LLMServiceException(f"Text generation failed: {str(e)}")
    
    async def generate_with_langchain(self, prompt: str, **kwargs) -> str:
        """Generate text using LangChain wrapper"""
        
        if not self._initialized or not self.langchain_llm:
            raise LLMServiceException("LangChain LLM not initialized")
        
        try:
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, 
                lambda: self.langchain_llm.invoke(prompt, **kwargs)
            )
            
            return response
            
        except Exception as e:
            logger.error(f"LangChain text generation failed: {e}")
            raise LLMServiceException(f"LangChain generation failed: {str(e)}")
    
    async def batch_generate(
        self, 
        prompts: List[str], 
        **kwargs
    ) -> List[str]:
        """Generate text for multiple prompts"""
        
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
        """Check service health"""
        
        if not self._initialized:
            return False
        
        try:
            # Quick health check with simple prompt
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
        """Get model information"""
        
        if not self._initialized:
            raise LLMServiceException("LLM service not initialized")
        
        return {
            "model_id": settings.WATSON_MODEL_ID,
            "watson_url": settings.WATSON_URL,
            "project_id": settings.WATSON_PROJECT_ID,
            "initialized": self._initialized,
            "health_status": self._health_status,
            "last_health_check": datetime.utcnow().isoformat()
        }
    
    async def cleanup(self) -> None:
        """Cleanup resources"""
        
        logger.info("🧹 Cleaning up LLM service...")
        
        self.client = None
        self.model = None
        self.langchain_llm = None
        self._initialized = False
        self._health_status = False
        
        logger.info("✅ LLM service cleanup completed")