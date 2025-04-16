# Company Insight Engine 🕵️♂️

Automated intelligence system that scrapes company data, analyzes it with AI (Llama3-70B), and exports structured insights to Google Sheets.

## 🚀 Key Features
- Web scraping with anti-blocking techniques
- AI-powered data structuring (Groq/Llama3)
- Multi-agent validation workflow (CrewAI)
- Google Sheets integration with OAuth2
- Streamlit dashboard for pipeline control
- Memory/performance optimization (tracemalloc)

## 🛠 Tech Stack
**Core**  
`Python 3.10` `Streamlit` `CrewAI` `Groq API`  
**Web**  
`BeautifulSoup4` `Requests` `tldextract`  
**Data**  
`Google Sheets API` `JSON5` `lxml`  
**DevOps**  
`LRU Caching` `Connection Pooling` `Retry Logic`

## License:
Please see the LICENSE file for details.

## Contact:
If you have any questions, please feel free to contact us at mostafathemar@email.com.

## ⚙️ Architecture
```mermaid
graph TD
    A[Streamlit UI] --> B[Domain Verification]
    B --> C[Web Scraping Agent]
    C --> D[LLM Data Structuring]
    D --> E[AI Validation Agent]
    E --> F[Google Sheets Export]
