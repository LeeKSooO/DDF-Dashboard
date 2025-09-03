"""
Logging middleware for API requests
"""

import time
import logging
import uuid
from typing import Callable
from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings


logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Custom logging middleware"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and log details"""
        
        # Generate request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Start timing
        start_time = time.time()
        
        # Log request
        logger.info(
            f"Request started - ID: {request_id}, "
            f"Method: {request.method}, "
            f"URL: {request.url}, "
            f"Client: {request.client.host if request.client else 'unknown'}"
        )
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate processing time
            process_time = time.time() - start_time
            
            # Log response
            logger.info(
                f"Request completed - ID: {request_id}, "
                f"Status: {response.status_code}, "
                f"Time: {process_time:.3f}s"
            )
            
            # Add headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{process_time:.3f}"
            
            return response
            
        except Exception as e:
            # Calculate processing time
            process_time = time.time() - start_time
            
            # Log error
            logger.error(
                f"Request failed - ID: {request_id}, "
                f"Error: {str(e)}, "
                f"Time: {process_time:.3f}s"
            )
            
            raise


def setup_logging_middleware(app: FastAPI) -> None:
    """Setup logging middleware"""
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper()),
        format=settings.LOG_FORMAT,
    )
    
    # Add custom logging middleware
    app.add_middleware(LoggingMiddleware)