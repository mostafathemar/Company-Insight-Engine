import requests
from groq import Groq
import json
from bs4 import BeautifulSoup

class WebSearchAgent:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Language': 'en-US,en;q=0.9'
        }
    
    def search(self, url):
        """Fetch HTML content from a website"""
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.text
        except Exception as e:
            return f"Error fetching content: {str(e)}"

class LLMProcessorAgent:
    def __init__(self, api_key):
        self.client = Groq(api_key=api_key)
    
    def process_to_json(self, html_content):
        """Process HTML content to structured JSON using LLM"""
        try:
            # Extract clean text first
            soup = BeautifulSoup(html_content, 'html.parser')
            text_content = soup.get_text(separator='\n', strip=True)[:3000]  # Truncate for token limits
            
            response = self.client.chat.completions.create(
                messages=[{
                    "role": "user",
                    "content": f"""Convert this website content into structured JSON format:
                    {text_content}
                    
                    Output format:
                    {{
                        "metadata": {{
                            "source": "website URL",
                            "title": "page title",
                            "description": "page description"
                        }},
                        "content": {{
                            "sections": [
                                {{
                                    "heading": "section heading",
                                    "paragraphs": ["paragraph text"]
                                }}
                            ]
                        }}
                    }}"""
                }],
                model="llama3-70b-8192",
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            return {"error": str(e)}

# Example usage
if __name__ == "__main__":
    # Initialize agents
    web_agent = WebSearchAgent()
    llm_agent = LLMProcessorAgent(api_key='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')
    
    # Execute workflow
    target_url = "https://example.com"
    html_content = web_agent.search(target_url)
    
    if not html_content.startswith("Error"):
        processed_data = llm_agent.process_to_json(html_content)
        print(json.dumps(processed_data, indent=2))
    else:
        print(html_content)