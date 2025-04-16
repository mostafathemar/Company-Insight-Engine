import os
import re
import streamlit as st
from modify_data_sheet import CompanyIntelSystem, CONFIG
from crewai import Agent, Task, Crew, Process
from crewai_tools import BaseTool  
from typing_extensions import Self
# Disable CrewAI telemetry
os.environ["CREWAI_TELEMETRY"] = "false"

# Set page config
st.set_page_config(
    page_title="Company Intelligence System",
    page_icon="🔍",
    layout="wide"
)

# Initialize session state
if 'stage' not in st.session_state:
    st.session_state.stage = 'input_company'
if 'intel_system' not in st.session_state:
    st.session_state.intel_system = None

# Sidebar for API key
with st.sidebar:
    st.header("Configuration")
    groq_api_key = st.text_input("Groq API Key", type="password")
    st.markdown("[Get Groq API Key](https://console.groq.com/keys)")

# Main app
st.title("Company Intelligence System")
st.markdown("Automated company data collection and analysis")

class IntelTools(BaseTool):
    name: str = "Company Intelligence Tools"
    description: str = "Collection of tools for company data processing"
    
    def _run(self, company_name: str, website: str) -> dict:
        try:
            intel_system = CompanyIntelSystem()
            intel_system.website = website
            processed_data = intel_system.process_company(company_name)
            return dict(zip(CONFIG['GOOGLE']['COLUMNS'], processed_data))
        except Exception as e:
            return {"error": str(e)}

def create_agents():
    intel_tool = IntelTools()
    
    researcher = Agent(
        role="Company Researcher",
        goal="Gather comprehensive company information",
        tools=[intel_tool],
        verbose=True,
        allow_delegation=False
    )

    validator = Agent(
        role="Data Validator",
        goal="Verify and format company data",
        verbose=True,
        allow_delegation=False
    )

    return researcher, validator

def generate_website_variants(company_name):
    base_name = re.sub(r'[^\w]', '', company_name).lower()
    tlds = ['com', 'org', 'net', 'io', 'ai', 'co', 'tech']
    return [f"https://www.{base_name}.{tld}" for tld in tlds] + \
           [f"https://{base_name}.{tld}" for tld in tlds]

def check_domain(url):
    try:
        response = st.session_state.intel_system.session.head(
            url, timeout=5, verify=False, allow_redirects=True
        )
        return response.status_code < 400
    except:
        return False

def main_workflow():
    if st.session_state.stage == 'input_company':
        handle_input_stage()
    elif st.session_state.stage == 'verify_website':
        handle_verification_stage()
    elif st.session_state.stage == 'manual_website':
        handle_manual_stage()
    elif st.session_state.stage == 'process_data':
        handle_processing_stage()
    elif st.session_state.stage == 'review_data':
        handle_review_stage()

def handle_input_stage():
    if not groq_api_key:
        st.error("Please enter your Groq API key in the sidebar")
        return

    CONFIG['GROQ']['API_KEY'] = groq_api_key
    st.session_state.intel_system = CompanyIntelSystem()
    
    company_name = st.text_input("Enter Company Name", key='company_input')
    if st.button("Start Processing"):
        if company_name:
            st.session_state.company_name = company_name
            st.session_state.website_variants = generate_website_variants(company_name)
            st.session_state.stage = 'verify_website'
        else:
            st.warning("Please enter a company name")

def handle_verification_stage():
    st.subheader("Website Verification")
    
    if 'suggested_url' not in st.session_state:
        suggested_url = None
        for url in st.session_state.website_variants:
            if check_domain(url):
                suggested_url = url
                break
        st.session_state.suggested_url = suggested_url
    
    if st.session_state.suggested_url:
        st.write(f"🌐 Suggested website: {st.session_state.suggested_url}")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Yes, this is correct"):
                st.session_state.website = st.session_state.suggested_url
                st.session_state.stage = 'process_data'
        with col2:
            if st.button("No, enter manually"):
                st.session_state.stage = 'manual_website'
    else:
        st.session_state.stage = 'manual_website'

def handle_manual_stage():
    st.subheader("Manual Website Entry")
    website = st.text_input("Enter full website URL (https://...)")
    if st.button("Submit Website"):
        if website:
            if not website.startswith(('http://', 'https://')):
                website = f'https://{website}'
            if check_domain(website):
                st.session_state.website = website
                st.session_state.stage = 'process_data'
            else:
                st.error("Invalid or unreachable URL")
        else:
            st.warning("Please enter a website URL")

def handle_processing_stage():
    st.subheader("Processing Company Data")
    
    with st.spinner("Collecting and analyzing data..."):
        try:
            researcher, validator = create_employees()
            
            research_task = Task(
                description=f"Gather data for {st.session_state.company_name}",
                agent=researcher,
                expected_output="Structured company data in JSON format",
                context={
                    "company_name": st.session_state.company_name,
                    "website": st.session_state.website
                }
            )
            
            validation_task = Task(
                description="Validate and format the collected data",
                agent=validator,
                expected_output="Properly formatted JSON output",
                context=[research_task]
            )
            
            crew = Crew(
                agents=[researcher, validator],
                tasks=[research_task, validation_task],
                verbose=True,
                process=Process.sequential
            )
            
            result = crew.kickoff()
            
            if result and not result.get('error'):
                st.session_state.json_data = result
                st.session_state.stage = 'review_data'
            else:
                st.error(f"Processing failed: {result.get('error', 'Unknown error')}")
                st.session_state.stage = 'input_company'
                
        except Exception as e:
            st.error(f"Processing failed: {str(e)}")
            st.session_state.stage = 'input_company'

def handle_review_stage():
    st.subheader("Processed Data Review")
    st.json(st.session_state.json_data)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 Save to Google Sheets"):
            success = st.session_state.intel_system.save_results(
                list(st.session_state.json_data.values())
            )
            if success:
                st.success("Data saved successfully!")
            else:
                st.error("Failed to save data")
            st.session_state.stage = 'input_company'
    with col2:
        if st.button("🚫 Discard Data"):
            st.warning("Data not saved")
            st.session_state.stage = 'input_company'

if __name__ == "__main__":
    main_workflow()