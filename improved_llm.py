"""
Enhanced LLM integration with:
- Multi-provider support (OpenAI, Anthropic)
- Robust error handling and retries
- Token counting and cost tracking
- Better JSON extraction
"""

import json
import time
import os
from typing import Dict, Optional, Literal
import requests
import streamlit as st


LLMProvider = Literal["openai", "anthropic"]


def get_config(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Get configuration from environment variables or Streamlit secrets.
    
    Args:
        key: Configuration key
        default: Default value if not found
        
    Returns:
        Configuration value or default
    """
    # Check environment variables first (Render, production)
    value = os.getenv(key)
    if value is not None:
        return value
    
    # Fall back to Streamlit secrets (local development)
    try:
        if hasattr(st, 'secrets') and key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    
    return default


class LLMError(Exception):
    """Base exception for LLM-related errors."""
    pass


class LLMClient:
    """Unified interface for multiple LLM providers."""
    
    def __init__(self, provider: LLMProvider = "openai"):
        self.provider = provider
        
        if provider == "openai":
            self.api_key = get_config("OPENAI_API_KEY")
            self.model = get_config("OPENAI_MODEL", "gpt-4o-mini")
            self.endpoint = "https://api.openai.com/v1/chat/completions"
        elif provider == "anthropic":
            self.api_key = get_config("ANTHROPIC_API_KEY")
            self.model = get_config("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
            self.endpoint = "https://api.anthropic.com/v1/messages"
        else:
            raise ValueError(f"Unsupported provider: {provider}")
            
        if not self.api_key:
            raise LLMError(f"Missing API key for {provider}")
    
    def call(
        self,
        system: str,
        user: str,
        temperature: float = 0.2,
        max_tokens: int = 4000,
        max_retries: int = 3,
        retry_delay: float = 2.0,
    ) -> Dict:
        """
        Call LLM with automatic retries and error handling.
        
        Args:
            system: System prompt
            user: User message
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            max_retries: Number of retry attempts
            retry_delay: Seconds to wait between retries
            
        Returns:
            Parsed JSON response
            
        Raises:
            LLMError: If all retries fail
        """
        for attempt in range(max_retries):
            try:
                if self.provider == "openai":
                    response = self._call_openai(system, user, temperature, max_tokens)
                else:  # anthropic
                    response = self._call_anthropic(system, user, temperature, max_tokens)
                
                return response
                
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    st.warning(f"Request timeout, retrying... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(retry_delay * (attempt + 1))
                else:
                    raise LLMError("Request timed out after all retries")
                    
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    st.warning(f"Request failed: {e}, retrying... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(retry_delay * (attempt + 1))
                else:
                    raise LLMError(f"Request failed after all retries: {e}")
                    
            except json.JSONDecodeError as e:
                if attempt < max_retries - 1:
                    st.warning(f"Invalid JSON response, retrying... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(retry_delay)
                else:
                    raise LLMError(f"Model did not return valid JSON after all retries: {e}")
        
        raise LLMError("Unexpected error: all retries exhausted")
    
    def _call_openai(self, system: str, user: str, temperature: float, max_tokens: int) -> Dict:
        """Call OpenAI API."""
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        response = requests.post(
            self.endpoint,
            headers=headers,
            json=payload,
            timeout=120,
        )
        
        if not response.ok:
            error_detail = response.text
            try:
                error_json = response.json()
                error_detail = error_json.get("error", {}).get("message", error_detail)
            except:
                pass
            raise LLMError(f"OpenAI API error {response.status_code}: {error_detail}")
        
        data = response.json()
        content = data["choices"][0]["message"].get("content", "").strip()
        
        # Track usage
        usage = data.get("usage", {})
        st.session_state.setdefault("total_tokens", 0)
        st.session_state["total_tokens"] += usage.get("total_tokens", 0)
        
        return self._parse_json_response(content)
    
    def _call_anthropic(self, system: str, user: str, temperature: float, max_tokens: int) -> Dict:
        """Call Anthropic API."""
        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system,
            "messages": [
                {"role": "user", "content": user}
            ],
        }
        
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        
        response = requests.post(
            self.endpoint,
            headers=headers,
            json=payload,
            timeout=120,
        )
        
        if not response.ok:
            error_detail = response.text
            try:
                error_json = response.json()
                error_detail = error_json.get("error", {}).get("message", error_detail)
            except:
                pass
            raise LLMError(f"Anthropic API error {response.status_code}: {error_detail}")
        
        data = response.json()
        content = data["content"][0]["text"].strip()
        
        # Track usage
        usage = data.get("usage", {})
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        st.session_state.setdefault("total_tokens", 0)
        st.session_state["total_tokens"] += input_tokens + output_tokens
        
        return self._parse_json_response(content)
    
    def _parse_json_response(self, content: str) -> Dict:
        """
        Parse JSON from LLM response with fallback extraction.
        
        Handles:
        - Direct JSON
        - Markdown code blocks
        - JSON embedded in text
        """
        if not content:
            raise json.JSONDecodeError("Empty response", "", 0)
        
        # Try direct parse first
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        
        # Try extracting from markdown code blocks
        if "```" in content:
            parts = content.split("```")
            for i, part in enumerate(parts):
                # Skip non-code parts
                if i % 2 == 0:
                    continue
                
                # Remove language identifier
                lines = part.strip().split("\n")
                if lines[0].lower() in ["json", "jsonc"]:
                    part = "\n".join(lines[1:])
                
                try:
                    return json.loads(part.strip())
                except json.JSONDecodeError:
                    continue
        
        # Try finding JSON object boundaries
        start = content.find("{")
        end = content.rfind("}")
        
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(content[start:end + 1])
            except json.JSONDecodeError:
                pass
        
        # Last resort: show what we got
        raise json.JSONDecodeError(
            f"Could not extract valid JSON. Response preview: {content[:500]}",
            content,
            0
        )


def call_llm(
    system: str,
    user: str,
    provider: LLMProvider = "openai",
    temperature: float = 0.2,
    max_tokens: int = 4000,
) -> Dict:
    """
    Convenience function for calling LLM.
    Maintains backward compatibility with original interface.
    """
    client = LLMClient(provider=provider)
    return client.call(system, user, temperature, max_tokens)


def estimate_tokens(text: str) -> int:
    """
    Rough token estimation (4 chars ≈ 1 token).
    Good enough for UI display and cost estimation.
    """
    return len(text) // 4


def estimate_cost(tokens: int, provider: LLMProvider = "openai", model: str = "gpt-4o-mini") -> float:
    """
    Estimate API cost based on token count.
    
    Prices as of Jan 2025 (update as needed):
    - GPT-4o-mini: $0.150 / 1M input, $0.600 / 1M output
    - Claude Sonnet 4: $3 / 1M input, $15 / 1M output
    """
    if provider == "openai":
        if "gpt-4o-mini" in model.lower():
            # Assume 70% input, 30% output
            cost_per_1m = (0.150 * 0.7) + (0.600 * 0.3)
            return (tokens / 1_000_000) * cost_per_1m
        elif "gpt-4o" in model.lower():
            cost_per_1m = (2.50 * 0.7) + (10.00 * 0.3)
            return (tokens / 1_000_000) * cost_per_1m
    elif provider == "anthropic":
        if "sonnet" in model.lower():
            cost_per_1m = (3.00 * 0.7) + (15.00 * 0.3)
            return (tokens / 1_000_000) * cost_per_1m
    
    return 0.0  # Unknown model
