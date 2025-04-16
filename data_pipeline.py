import re
import requests
import json
import sys
import random
import time
import tracemalloc
from groq import Groq
from bs4 import BeautifulSoup
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import urllib3
from urllib.parse import urlparse
from functools import lru_cache
import json5
import tldextract

# Configuration Constants
CONFIG = {
    'GOOGLE': {
        'SCOPES': ['https://www.googleapis.com/auth/spreadsheets'],
        'SPREADSHEET_ID': '1098MT3Wgfzia7dKjxAyr7jxgH5PpdAt3AOaoII2J9xw',
        'CREDENTIALS_FILE': 'credentials.json',
        'SHEET_NAME': 'Company Details',
        'COLUMNS': [
            'Company Name', 'Website', 'Industry', 'Headquarters',
            'Founding Year', 'No.Employees', 'Funding Raised', 'Revenue',
            'Valuation', 'Company Description', 'Founders & LinkedIn URLs',
            'Key Contacts', 'Social Media Links', 'AI Model Used',
            'Primary AI Use Case', 'AI Frameworks Used',
            'AI Products/Services Offered', 'Patent Details',
            'AI Research Papers Published', 'Partnerships', 'Technology Stack',
            'Customer Base', 'Case Studies', 'Awards and Recognition',
            'Compliance and Regulatory Adherence', 'Market Presence',
            'Community Engagement', 'AI Ethics Policies', 'Competitor Analysis',
            'Media Mentions'
        ]
    },
    'GROQ': {
        'API_KEY': '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',
        'MODEL': 'llama3-70b-8192'
    },
    'NETWORK': {
        'REQUEST_TIMEOUT': (15, 45),
        'MAX_RETRIES': 7,
        'BACKOFF_FACTOR': 2.0,
        'POOL_SIZE': 20,
        'USER_AGENTS': [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1'
        ]
    },
    'ANALYSIS': {
        'INDUSTRY_KEYWORDS': {
            'Technology': ['software', 'technology', 'cloud', 'saas'],
            'AI': ['artificial intelligence', 'machine learning', 'deep learning'],
            'FinTech': ['financial technology', 'banking', 'payments'],
            'HealthTech': ['healthcare', 'medical', 'biotech']
        },
        'TECH_KEYWORDS': {
            'Frontend': ['react', 'angular', 'vue', 'javascript'],
            'Backend': ['node.js', 'django', 'spring', 'flask'],
            'Database': ['mysql', 'postgresql', 'mongodb'],
            'Cloud': ['aws', 'azure', 'gcp']
        }
    }
}

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class CompanyIntelSystem:
    def __init__(self):
        self.session = self._create_session()
        
        if not CONFIG['GROQ']['API_KEY'] or CONFIG['GROQ']['API_KEY'].startswith('YOUR_'):
            print("🔴 Error: Invalid Groq API key configuration")
            sys.exit(1)
            
        self.groq = Groq(api_key=CONFIG['GROQ']['API_KEY'])
        self.sheets = self._init_google_sheets()
        self.website = ''
        self.trusted_domains = {
            'careers': ['lever.co', 'greenhouse.io'],
            'patents': ['uspto.gov', 'google.com/patents']
        }
        tracemalloc.start()

    def _create_session(self):
        session = requests.Session()
        retry = Retry(
            total=CONFIG['NETWORK']['MAX_RETRIES'],
            backoff_factor=CONFIG['NETWORK']['BACKOFF_FACTOR'],
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=['HEAD', 'GET', 'POST'],
            respect_retry_after_header=True
        )
        adapter = HTTPAdapter(
            max_retries=retry,
            pool_connections=CONFIG['NETWORK']['POOL_SIZE'],
            pool_maxsize=CONFIG['NETWORK']['POOL_SIZE']
        )
        session.mount('https://', adapter)
        session.headers.update({
            'User-Agent': random.choice(CONFIG['NETWORK']['USER_AGENTS']),
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://www.google.com/',
            'DNT': str(random.randint(0, 1))})
        return session

    def _init_google_sheets(self):
        try:
            creds = Credentials.from_service_account_file(
                CONFIG['GOOGLE']['CREDENTIALS_FILE'],
                scopes=CONFIG['GOOGLE']['SCOPES'])
            return build('sheets', 'v4', credentials=creds)
        except Exception as e:
            print(f"🔴 Google Sheets connection failed: {str(e)}")
            sys.exit(1)

    @lru_cache(maxsize=100)
    def _get_verified_website(self, company_name):
        base_name = re.sub(r'[^\w]', '', company_name).lower()
        tlds = ['com', 'org', 'net', 'io', 'ai', 'co', 'tech']
        variants = [f"https://www.{base_name}.{tld}" for tld in tlds] + \
                   [f"https://{base_name}.{tld}" for tld in tlds]
        for url in variants:
            if self._check_domain(url):
                print(f"\n🌐 Suggested website: {url}")
                if input("Is this correct? (y/n): ").lower().strip() == 'y':
                    return url
                return self._manual_website_entry()
        return self._manual_website_entry()

    def _check_domain(self, url):
        try:
            response = self.session.head(url, timeout=5, verify=False, allow_redirects=True)
            return response.status_code < 400
        except requests.RequestException:
            return False

    def _manual_website_entry(self):
        while True:
            url = input("\n🔧 Enter full website URL (https://...): ").strip()
            if not url.startswith(('http://', 'https://')):
                url = f'https://{url}'
            if self._check_domain(url):
                return url
            print("❌ Invalid or unreachable URL")

    def _get_page_content(self, url):
        try:
            response = self.session.get(url, timeout=CONFIG['NETWORK']['REQUEST_TIMEOUT'], verify=False)
            response.raise_for_status()
            return response.text
        except requests.HTTPError as e:
            if e.response.status_code == 403:
                return self._bypass_protection(url)
            return None
        except Exception as e:
            print(f"⚠️ Network Error: {str(e)}")
            return None

    def _bypass_protection(self, url):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': 'https://www.google.com/'
            }
            time.sleep(random.uniform(1, 3))
            response = self.session.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"🔴 Bypass failed: {str(e)}")
            return None

    def _clean_text(self, text):
        return re.sub(r'\s+', ' ', text).strip()[:5000] if text else 'N/A'

    def _extract_meaningful_content(self, soup):
        for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'form', 'button']):
            element.decompose()
        main_content = soup.find(['main', 'article', 'div.content']) or soup.body
        return self._clean_text(main_content.get_text(separator='\n')) if main_content else 'N/A'

    def _extract_description(self, soup):
        try:
            for meta in ['og:description', 'description']:
                tag = soup.find('meta', property=meta) or soup.find('meta', attrs={'name': meta})
                if tag and tag.get('content'):
                    return self._clean_text(tag['content'])
            about = soup.find('section', id='about') or soup.find(class_=re.compile('about', re.I))
            if about:
                first_para = about.find('p')
                if first_para:
                    return self._clean_text(first_para.text)
            return self._clean_text(self._extract_meaningful_content(soup))[:200]
        except:
            return 'N/A'

    def _detect_industry(self, content):
        content_lower = content.lower()
        for industry, keywords in CONFIG['ANALYSIS']['INDUSTRY_KEYWORDS'].items():
            if any(kw in content_lower for kw in keywords):
                return industry
        return 'Technology'

    def _extract_pattern(self, text, pattern):
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(1) if match else 'N/A'

    def _find_patents(self, soup):
        patents = []
        for elem in soup.find_all(string=re.compile(r'patent', re.I)):
            if 'US' in elem and re.search(r'\d', elem):
                patents.append(self._clean_text(elem))
        return patents[:3] or ['N/A']

    def _find_case_studies(self, soup):
        studies = []
        for a in soup.select('a[href*="case-study"]')[:3]:
            studies.append(f"{self._clean_text(a.text)} | {a['href']}")
        return studies or ['N/A']

    def _find_awards(self, soup):
        awards = []
        for h in soup.find_all(['h2', 'h3']):
            if 'award' in h.text.lower():
                awards.append(self._clean_text(h.text))
        return awards[:3] or ['N/A']

    def _find_partnerships(self, soup):
        """Extract partnership information"""
        partners = []
        # Look for partnership sections
        for section in soup.find_all(['section', 'div'], class_=re.compile(r'partners?|collab', re.I)):
            partners.extend([self._clean_text(img['alt']) for img in section.find_all('img', alt=True)])
            partners.extend([self._clean_text(a.text) for a in section.find_all('a', href=True)])
        return list(set(partners))[:5] or ['N/A']
    
    def _find_customer_base(self, soup):
        """Identify customer base information"""
        customers = []
        # Look for client/customer sections
        for section in soup.find_all(['section', 'div'], class_=re.compile(r'clients?|customers?', re.I)):
            customers.extend([self._clean_text(img['alt']) for img in section.find_all('img', alt=True)])
            customers.extend([self._clean_text(li.text) for li in section.find_all('li')])
        return list(set(customers))[:5] or ['N/A']

    def _find_competitors(self, soup):
        competitors = []
        content = self._extract_meaningful_content(soup).lower()
        patterns = [
            r'compared to (\w+)',
            r'vs\. (\w+)',
            r'unlike (\w+)',
            r'competitors? (?:include|are) ([\w\s,]+)'
        ]
        for pattern in patterns:
            matches = re.findall(pattern, content)
            if matches:
                competitors.extend([m.strip() for m in matches[-1].split(',')])
        return list(set(competitors))[:3] or ['N/A']

    def _find_media_mentions(self, soup):
        media = []
        press_section = soup.find(['section', 'div'], class_=re.compile(r'press|media', re.I))
        if press_section:
            media.extend([f"{a.text} | {a['href']}" for a in press_section.find_all('a', href=True)])
        return media[:5] or ['N/A']

    def _find_ethics_policies(self, soup):
        ethics = []
        for link in soup.find_all('a', href=re.compile(r'ethics|responsible-ai', re.I)):
            ethics.append(f"{self._clean_text(link.text)} | {link['href']}")
        return ethics[:3] or ['N/A']

    def _find_compliance_info(self, soup):
        compliance = []
        patterns = {
            'ISO': r'\bISO\/IEC \d{5}',
            'SOC': r'\bSOC 2\b',
            'GDPR': r'\bGDPR\b',
            'HIPAA': r'\bHIPAA\b'
        }
        content = self._extract_meaningful_content(soup)
        for name, pattern in patterns.items():
            if re.search(pattern, content, re.I):
                compliance.append(name)
        return compliance or ['N/A']

    def _extract_core_data(self, soup):
        try:
            content = self._extract_meaningful_content(soup)
            return {
                'name': self._extract_company_name(soup),
                'description': self._extract_description(soup),
                'financials': self._extract_financials(soup),
                'technology': self._detect_technology(soup),
                'social': self._find_social_links(soup),
                'content': content,
                'leadership': self._find_leadership(soup),
                'founders': self._find_founders(soup),
                'ai_info': self._extract_ai_info(soup),
                'industry': self._detect_industry(content),
                'patents': self._find_patents(soup),
                'case_studies': self._find_case_studies(soup),
                'awards': self._find_awards(soup),
                'partnerships': self._find_partnerships(soup),
                'customers': self._find_customer_base(soup),
                'competitors': self._find_competitors(soup),
                'media': self._find_media_mentions(soup),
                'ethics': self._find_ethics_policies(soup),
                'compliance': self._find_compliance_info(soup)
            }
        except Exception as e:
            print(f"⚠️ Core extraction error: {str(e)}")
            return self._create_empty_core_data()

    def _create_empty_core_data(self):
        return {key: 'N/A' for key in [
            'name', 'description', 'financials', 'technology', 'social',
            'content', 'leadership', 'founders', 'ai_info', 'industry',
            'patents', 'case_studies', 'awards', 'partnerships', 'customers',
            'competitors', 'media', 'ethics', 'compliance'
        ]}

    def _extract_company_name(self, soup):
        try:
            sources = [
                soup.find('meta', property='og:site_name'),
                soup.title,
                soup.find('h1'),
                soup.find('div', class_=re.compile('header|heading', re.I))
            ]
            for source in sources:
                if source:
                    name = source.get('content') if source.name == 'meta' else source.text
                    clean_name = self._clean_text(name.split('|')[0].split('-')[0].strip())
                    if clean_name and len(clean_name) > 2:
                        return clean_name
            return tldextract.extract(self.website).domain.title()
        except:
            return tldextract.extract(self.website).domain.title()

    def _extract_financials(self, soup):
        content = self._extract_meaningful_content(soup)
        return {
            'employees': self._extract_pattern(content, r'(\d{1,3}(?:,\d{3})*)\s+employees'),
            'founded': self._extract_pattern(content, r'founded in (\d{4})'),
            'revenue': self._extract_pattern(content, r'revenue of (\$?\d+(?:\.\d+)?[BM]?)'),
            'valuation': self._extract_pattern(content, r'valued at (\$?\d+(?:\.\d+)?[BM]?)')
        }

    def _detect_technology(self, soup):
        content = self._extract_meaningful_content(soup).lower()
        return [tech for tech, keywords in CONFIG['ANALYSIS']['TECH_KEYWORDS'].items()
                if any(kw in content for kw in keywords)] or ['N/A']

    def _find_social_links(self, soup):
        social = {p: [] for p in ['twitter', 'linkedin', 'github', 'youtube']}
        for link in soup.find_all('a', href=True):
            for platform, pattern in [
                ('twitter', r'https?://(?:www\.)?(?:twitter|x)\.com/[\w-]+'),
                ('linkedin', r'https?://(?:www\.)?linkedin\.com/(?:company|in)/[\w-]+'),
                ('github', r'https?://(?:www\.)?github\.com/[\w-]+'),
                ('youtube', r'https?://(?:www\.)?youtube\.com/(?:user|channel)/[\w-]+')
            ]:
                if re.fullmatch(pattern, link['href'], re.I):
                    social[platform].append(link['href'])
        return {k: list(set(v)) for k, v in social.items()}

    def _find_leadership(self, soup):
        leadership = []
        for container in soup.find_all(['section', 'div'], class_=re.compile(r'leadership|team', re.I)):
            for member in container.find_all(['div', 'li'], class_=re.compile(r'member|profile')):
                name = member.find(['h2', 'h3'], class_=re.compile(r'name|title'))
                role = member.find('p', class_=re.compile(r'role|position'))
                if name and role:
                    # Changed separator from '-' to ':'
                    leadership.append(f"{self._clean_text(name.text)}: {self._clean_text(role.text)}")
        return leadership[:5] or ['N/A']

    def _find_founders(self, soup):
        founders = []
        for container in soup.find_all(['section', 'div'], class_=re.compile(r'founders?|history', re.I)):
            for elem in container.find_all(['div', 'li'], class_=re.compile(r'founder')):
                name = elem.find(['h3', 'h4'], class_=re.compile(r'name|title'))
                role = elem.find('p', class_=re.compile(r'role|position'))
                link = elem.find('a', href=re.compile(r'linkedin\.com/in/'))
                if name and role and 'founder' in role.text.lower():
                    entry = self._clean_text(name.text)
                    if link:
                        entry += f" | {link['href']}"
                    founders.append(entry)
        return founders[:3] or ['N/A']

    def _extract_ai_info(self, soup):
        content = self._extract_meaningful_content(soup)
        return {
            'models': re.findall(r'\b(transformer|bert|gpt-\d|llama)\b', content, re.I) or ['N/A'],
            'frameworks': re.findall(r'\b(tensorflow|pytorch|keras)\b', content, re.I) or ['N/A'],
            'products': re.findall(r'\b(ai[- ]powered|ai[- ]driven|copilot)\b', content, re.I) or ['N/A']
        }

    def _enhance_with_ai(self, raw_data, website):
        system_prompt = f"""Generate COMPLETE JSON data for all requested fields:
{{
  "Company Name": "string",
  "Website": "string",
  "Industry": "string",
  "Headquarters": "string",
  "Founding Year": "YYYY",
  "No.Employees": "number",
  "Funding Raised": "$X.XM/B",
  "Revenue": "$X.XB",
  "Valuation": "$X.XB",
  "Company Description": "2-3 paragraph summary",
  "Founders & LinkedIn URLs": ["Name | URL"],
  "Key Contacts": ["Name: Position"],
  "Social Media Links": {{"platform": ["urls"]}},
  "AI Model Used": ["list"],
  "Primary AI Use Case": "string",
  "AI Frameworks Used": ["list"],
  "AI Products/Services Offered": ["list"],
  "Patent Details": ["patent numbers/names"],
  "AI Research Papers Published": ["titles"],
  "Partnerships": ["partner names"],
  "Technology Stack": ["list"],
  "Customer Base": ["customer types/names"],
  "Case Studies": ["study titles/urls"],
  "Awards and Recognition": ["award names"],
  "Compliance and Regulatory Adherence": ["standards"],
  "Market Presence": "string",
  "Community Engagement": ["initiatives"],
  "AI Ethics Policies": ["policy names/urls"],
  "Competitor Analysis": ["competitor names"],
  "Media Mentions": ["article titles/urls"]
}}

Rules:
1. Use N/A for missing fields
2. Include ALL fields from the template
3. Validate URLs
4. Use real data from: {raw_data.get('content','')[:3000]}
5. Enhance with industry knowledge where appropriate
6. Format financial numbers with $ and suffixes (e.g., $1.5M, $2.4B)
7. Never hallucinate data - use 'N/A' for unknown
8. For any key-value pairs, format as "Key: Value" strings
9. For lists, use comma-separated values
10. Never use JSON brackets or quotation marks
11. Example format:
{{
  "Founders & LinkedIn URLs": "Larry Page: https://linkedin.com/in/larrypage, Sergey Brin: https://linkedin.com/in/sergeybrin",
  "Social Media Links": "Twitter: https://twitter.com/company, LinkedIn: https://linkedin.com/company"
}}
12. For key-value pairs in contacts, format as "Name: Position"
13. Example:
{{
  ...
  "Key Contacts": "Sundar Pichai: CEO, Ruth Porat: CFO",
  ...
}}"""
        try:
            response = self.groq.chat.completions.create(
                messages=[{"role": "system", "content": system_prompt}],
                model=CONFIG['GROQ']['MODEL'],
                temperature=0.3,
                max_tokens=3000,
                response_format={"type": "json_object"}
            )
            return self._clean_ai_response(response.choices[0].message.content)
        except Exception as e:
            print(f"🔴 AI Error: {str(e)}")
            return {}
            
    def _format_value(self, value, field_name):
        """Convert complex types to properly formatted strings"""
        formatted = ""
        if isinstance(value, dict):
            formatted = ", ".join([f"{k}: {v}" for k, v in value.items()])
        elif isinstance(value, list):
            formatted = ", ".join(str(item) for item in value)
        else:
            formatted = str(value)
        
        # Special handling for Key Contacts field
        if field_name == "Key Contacts":
            # Replace any incorrect separators
            formatted = formatted.replace(" - ", ": ")
            # Remove any trailing commas
            formatted = re.sub(r',\s*$', '', formatted)
            
        return formatted
        
    def _clean_ai_response(self, raw_json):
        try:
            raw_json = re.sub(r'^```json|```$', '', raw_json)
            raw_json = re.sub(r',\s*}', '}', raw_json)
            return json5.loads(raw_json)
        except Exception as e:
            print(f"⚠️ JSON Error: {str(e)[:100]}")
            return {}

    def _merge_data_sources(self, core, ai, website):
        merged = {}
        for col in CONFIG['GOOGLE']['COLUMNS']:
            try:
                ai_value = ai.get(col, 'N/A')
                web_value = self._get_web_data(col, core)
                default_value = self._get_default_value(col, website)
    
                # Pass field name to format_value
                final_value = next(
                    (self._format_value(v, col) for v in [ai_value, web_value, default_value] 
                    if v not in ['', 'N/A', None]),
                    'N/A'
                )
                
                merged[col] = final_value
                
            except Exception as e:
                merged[col] = 'N/A'
                
        return [merged.get(col, 'N/A') for col in CONFIG['GOOGLE']['COLUMNS']]

    def _get_web_data(self, col, core):
        mapping = {
            'Patent Details': core.get('patents', 'N/A'),
            'Partnerships': core.get('partnerships', 'N/A'),
            'Customer Base': core.get('customers', 'N/A'),
            'Competitor Analysis': core.get('competitors', 'N/A'),
            'Media Mentions': core.get('media', 'N/A'),
            'AI Ethics Policies': core.get('ethics', 'N/A'),
            'Compliance and Regulatory Adherence': core.get('compliance', 'N/A'),
            'Case Studies': core.get('case_studies', 'N/A'),
            'Awards and Recognition': core.get('awards', 'N/A')
        }
        return mapping.get(col, 'N/A')

    def _get_default_value(self, field, website):
        tld = tldextract.extract(website).suffix
        return {
            'Market Presence': 'Global',
            'Compliance and Regulatory Adherence': 'GDPR, CCPA'
        }.get(field, 'N/A')

    def process_company(self, company_name):
        try:
            self.website = self._get_verified_website(company_name)
            content = self._get_page_content(self.website)
            if not content:
                raise ValueError("Failed to retrieve website content")
            soup = BeautifulSoup(content, 'lxml')
            if not soup.find():
                raise ValueError("Invalid HTML structure")
            core_data = self._extract_core_data(soup)
            ai_data = self._enhance_with_ai(core_data, self.website)
            return self._merge_data_sources(core_data, ai_data, self.website)
        except Exception as e:
            print(f"⚠️ Critical Processing Error: {str(e)}")
            return ['N/A'] * len(CONFIG['GOOGLE']['COLUMNS'])

    def save_results(self, data):
        try:
            print("\n💾 Save to Google Sheets? (y/n): ", end="")
            if input().strip().lower() != 'y':
                print("\n🚫 Save cancelled")
                return False
    
            body = {'values': [data]}
            service = self.sheets.spreadsheets().values().append(
                spreadsheetId=CONFIG['GOOGLE']['SPREADSHEET_ID'],
                range=f"'{CONFIG['GOOGLE']['SHEET_NAME']}'!A:AD",
                valueInputOption="USER_ENTERED",
                body=body
            )
            result = service.execute()
            
            # Verify update
            if 'updates' in result and result['updates'].get('updatedRows') == 1:
                return True
            raise RuntimeError("Partial update failure: " + str(result))
            
        except Exception as e:
            print("\n🔴 CRITICAL SAVE ERROR:")
            print(f"Type: {type(e).__name__}")
            print(f"Details: {str(e)}")
            if hasattr(e, 'resp') and hasattr(e, 'uri'):
                print(f"HTTP Status: {e.resp.status}")
                print(f"API Response: {e.resp.reason}")
                print(f"Request URL: {e.uri}")
            return False

    def run(self):
        print("\n" + "="*60)
        print("=== Universal Company Intelligence System ===".center(60))
        print("="*60)
        
        company_name = input("\n🏢 Enter company name: ").strip()
        start_time = time.time()
        processed_data = self.process_company(company_name)
        
        print("\n🔍 Final Data Preview:")
        for idx, col in enumerate(CONFIG['GOOGLE']['COLUMNS']):
            value = str(processed_data[idx])[:100] if idx < len(processed_data) else ''
            print(f"   - {col[:25]:<25}: {value}...")

        if self.save_results(processed_data):
            print("\n🎉 Data saved successfully!")
        else:
            print("\n🚫 Data not saved")
        
        current, peak = tracemalloc.get_traced_memory()
        print(f"\n📊 Performance Metrics:")
        print(f"   - Memory Usage: {current/1e6:.1f}MB (Peak: {peak/1e6:.1f}MB)")
        print(f"   - Processing Time: {time.time()-start_time:.2f}s")
        tracemalloc.stop()

if __name__ == "__main__":
    intel_system = CompanyIntelSystem()
    intel_system.run()