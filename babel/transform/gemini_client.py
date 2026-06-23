"""Gemini client for LLM-based text transformation."""

import os
import json
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types


class RateLimitError(Exception):
    """Raised when rate limit is exceeded after retries."""
    pass


class GeminiClient:
    """Client for Gemini API."""

    def __init__(self, api_key: str = None, model_name: str = None):
        """Initialize Gemini client."""
        load_dotenv()
        
        # Get API key
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set")
        
        # Initialize client
        self.client = genai.Client(api_key=self.api_key)
        self.model_name = model_name or "gemini-2.5-flash"
    
    def generate_content(self, prompt: str, max_retries: int = 5) -> str:
        """Generate content with rate limit retry logic."""
        config = types.GenerateContentConfig(
            response_mime_type="application/json"
        )
        
        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=config
                )
                
                if not response.text:
                    raise ValueError("Empty response from Gemini API")
                
                return response.text
                
            except Exception as e:
                error_msg = str(e).lower()
                
                # Check if it's a rate limit error
                is_rate_limit = (
                    "429" in error_msg or
                    "rate limit" in error_msg or
                    "quota" in error_msg
                )
                
                if is_rate_limit and attempt < max_retries - 1:
                    # Exponential backoff: 1s, 2s, 4s, 8s, capped at 10s
                    wait_time = min(2 ** attempt, 10)
                    print(f"    ⚠️  Rate limit hit, waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                
                # If not rate limit or last attempt, raise
                if is_rate_limit:
                    raise RateLimitError(f"Rate limit exceeded after {max_retries} attempts: {e}")
                else:
                    raise
        
        raise RateLimitError(f"Failed after {max_retries} attempts")
    
    def transform_text(self, text: str, system_prompt: str, max_retries: int = 3) -> dict:
        """Transform text using Gemini API."""
        # Combine system prompt and user text
        full_prompt = f"{system_prompt}\n\nInput text:\n{text}"
        
        for attempt in range(max_retries):
            try:
                response_text = self.generate_content(full_prompt)
                result = json.loads(response_text)
                return result
                
            except json.JSONDecodeError as e:
                print(f"    ⚠️  JSON decode error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                else:
                    raise
            
            except Exception as e:
                error_msg = str(e)
                print(f"    ⚠️  Error (attempt {attempt + 1}/{max_retries}): {error_msg[:100]}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                else:
                    raise
        
        raise Exception(f"Failed to transform text after {max_retries} attempts")