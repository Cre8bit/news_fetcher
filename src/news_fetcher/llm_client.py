"""LLM client for article ranking and summarization."""

import json
import requests
from typing import Any, Dict, List, Optional
from datetime import datetime

from news_fetcher.config import Config, LLMConfig


class LLMClient:
    """Client for LLM-based article ranking and summarization."""
    
    def __init__(self, config: Config):
        self.config = config
        self.llm_config = config.get_llm_config()
    
    def is_available(self) -> bool:
        """Check if LLM is available and configured."""
        return bool(self.llm_config.api_key and self.llm_config.provider)
    
    def rank_articles(self, articles: List[Dict[str, Any]], topic: str) -> Optional[List[Dict[str, Any]]]:
        """Rank articles using LLM."""
        if not self.is_available():
            return None
        
        try:
            # Prepare article summaries for LLM
            article_summaries = []
            for i, article in enumerate(articles):
                summary = {
                    'index': i,
                    'title': article.get('title', ''),
                    'summary': article.get('summary', ''),
                    'source': article.get('source', ''),
                    'published': article.get('published', ''),
                    'domain': article.get('domain', '')
                }
                article_summaries.append(summary)
            
            prompt = self._create_ranking_prompt(article_summaries, topic)
            response = self._call_llm(prompt)
            
            if response:
                # Parse LLM response to get ranking
                ranked_indices = self._parse_ranking_response(response)
                if ranked_indices:
                    return [articles[i] for i in ranked_indices if i < len(articles)]
            
            return None
            
        except Exception as e:
            print(f"Error in LLM ranking: {e}")
            return None
    
    def summarize_articles(self, articles: List[Dict[str, Any]]) -> Optional[str]:
        """Summarize articles using LLM."""
        if not self.is_available():
            return None
        
        try:
            prompt = self._create_summarization_prompt(articles)
            response = self._call_llm(prompt)
            
            if response:
                # Clean up the response
                summary = response.strip()
                if summary.startswith('"') and summary.endswith('"'):
                    summary = summary[1:-1]
                return summary
            
            return None
            
        except Exception as e:
            print(f"Error in LLM summarization: {e}")
            return None
    
    def _create_ranking_prompt(self, articles: List[Dict[str, Any]], topic: str) -> str:
        """Create prompt for article ranking."""
        articles_text = ""
        for article in articles:
            articles_text += f"Index {article['index']}: {article['title']}\n"
            articles_text += f"Source: {article['source']}\n"
            articles_text += f"Summary: {article['summary'][:200]}...\n"
            articles_text += f"Published: {article['published']}\n\n"
        
        prompt = f"""You are a news curator tasked with ranking articles by relevance to the topic "{topic}".

Articles to rank:
{articles_text}

Please rank these articles by relevance to "{topic}" and return ONLY the top 5 article indices in order of relevance (most relevant first). 

Ranking criteria:
1. Direct relevance to the topic
2. Recency and newsworthiness
3. Source credibility
4. Depth of coverage

Respond with ONLY a JSON array of indices, like: [3, 1, 7, 2, 9]
"""
        return prompt
    
    def _create_summarization_prompt(self, articles: List[Dict[str, Any]]) -> str:
        """Create prompt for article summarization."""
        articles_text = ""
        for i, article in enumerate(articles[:10]):  # Limit to avoid token limits
            articles_text += f"{i+1}. {article.get('title', 'No title')}\n"
            articles_text += f"   Source: {article.get('source', 'Unknown')}\n"
            
            summary_text = article.get('summary', article.get('text', ''))
            if summary_text:
                articles_text += f"   Summary: {summary_text[:300]}...\n"
            
            if article.get('published'):
                articles_text += f"   Published: {article['published']}\n"
            
            articles_text += "\n"
        
        prompt = f"""You are a news editor creating a daily news summary. Based on the following {len(articles)} articles, create a concise front-page style summary.

Articles:
{articles_text}

Create a summary that includes:
1. A brief overview paragraph
2. 3-5 key bullet points highlighting the most important stories
3. Any significant numbers, dates, or developments mentioned
4. Keep it under 300 words total

Focus on the most newsworthy and impactful stories. Write in a professional news style.
"""
        return prompt
    
    def _call_llm(self, prompt: str) -> Optional[str]:
        """Make API call to LLM provider."""
        try:
            if self.llm_config.provider.lower() == "openai":
                return self._call_openai(prompt)
            elif self.llm_config.provider.lower() == "anthropic":
                return self._call_anthropic(prompt)
            elif self.llm_config.provider.lower() == "local":
                return self._call_local_llm(prompt)
            else:
                print(f"Unsupported LLM provider: {self.llm_config.provider}")
                return None
        except Exception as e:
            print(f"Error calling LLM: {e}")
            return None
    
    def _call_openai(self, prompt: str) -> Optional[str]:
        """Call OpenAI API."""
        url = self.llm_config.base_url
        
        headers = {
            "Authorization": f"Bearer {self.llm_config.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.llm_config.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": self.llm_config.max_tokens,
            "temperature": self.llm_config.temperature
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        return result["choices"][0]["message"]["content"]
    
    def _call_anthropic(self, prompt: str) -> Optional[str]:
        """Call Anthropic API."""
        url = self.llm_config.base_url
        
        headers = {
            "x-api-key": self.llm_config.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2024-06-01"
        }
        
        data = {
            "model": self.llm_config.model,
            "max_tokens": self.llm_config.max_tokens,
            "temperature": self.llm_config.temperature,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        return result["content"][0]["text"]
    
    def _call_local_llm(self, prompt: str) -> Optional[str]:
        """Call local LLM API (e.g., Ollama, LocalAI)."""
        if not self.llm_config.base_url:
            print("Base URL required for local LLM")
            return None
        
        url = f"{self.llm_config.base_url}/api/generate"
        
        data = {
            "model": self.llm_config.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.llm_config.temperature,
                "num_predict": self.llm_config.max_tokens
            }
        }
        
        response = requests.post(url, json=data, timeout=60)
        response.raise_for_status()
        
        result = response.json()
        return result.get("response", "")
    
    def _parse_ranking_response(self, response: str) -> Optional[List[int]]:
        """Parse LLM ranking response to extract indices."""
        try:
            # Try to find JSON array in the response
            import re
            
            # Look for JSON array pattern
            json_match = re.search(r'\[[\d,\s]+\]', response)
            if json_match:
                json_str = json_match.group()
                indices = json.loads(json_str)
                
                # Validate indices
                valid_indices = []
                for idx in indices:
                    if isinstance(idx, int) and idx >= 0:
                        valid_indices.append(idx)
                
                return valid_indices[:5]  # Return top 5
            
            # Fallback: try to extract numbers
            numbers = re.findall(r'\b\d+\b', response)
            if numbers:
                indices = [int(n) for n in numbers[:5]]
                return indices
            
            return None
            
        except Exception as e:
            print(f"Error parsing ranking response: {e}")
            return None