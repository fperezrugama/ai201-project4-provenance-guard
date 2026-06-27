import os
from groq import Groq
import json
import re

def groq_signal(text):
    """
    Use Groq LLM to assess if text is human or AI-generated.
    
    Returns:
        dict: {
            'score': float (0-1, 0=human, 1=AI),
            'confidence': float (0-1),
            'reasoning': str
        }
    """
    # Get API key from environment
    api_key = os.getenv('GROQ_API_KEY')
    if not api_key:
        return {
            'score': 0.5,
            'confidence': 0.0,
            'reasoning': 'GROQ_API_KEY not found in environment variables'
        }
    
    try:
        client = Groq(api_key=api_key)
        
        prompt = f"""Analyze the following text and determine if it was written by a human or AI.

Return ONLY a JSON object with these exact fields:
- score: a number between 0 and 1 where 0 = definitely human-written and 1 = definitely AI-generated
- confidence: a number between 0 and 1 indicating your certainty
- reasoning: a brief explanation (1-2 sentences)

Text to analyze:
"{text}"

JSON:"""

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=150
        )
        
        # Extract response content
        content = response.choices[0].message.content.strip()
        
        # Try to parse JSON from the response
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
        else:
            result = json.loads(content)
        
        # Ensure required fields exist
        result['score'] = max(0, min(1, float(result.get('score', 0.5))))
        result['confidence'] = max(0, min(1, float(result.get('confidence', 0.5))))
        result['reasoning'] = result.get('reasoning', 'Analysis completed')
        
        return result
        
    except Exception as e:
        return {
            'score': 0.5,
            'confidence': 0.3,
            'reasoning': f"Error during analysis: {str(e)[:100]}"
        }