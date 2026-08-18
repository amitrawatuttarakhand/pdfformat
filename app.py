import streamlit as st
from pypdf import PdfReader
from weasyprint import HTML
import json

st.set_page_config(page_title="PDF Template Agent", layout="wide")

# 1. Helper Functions
def extract_text_from_pdf(uploaded_file):
    reader = PdfReader(uploaded_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    return text

def generate_pdf_from_html(html_content):
    return HTML(string=html_content).write_pdf()

# 2. Session State Initialization
if "messages" not in st.session_state:
    st.session_state.messages = []
if "template_html" not in st.session_state:
    st.session_state.template_html = """
    <html>
    <head>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; color: #333; }
            h1 { color: #1E3A8A; border-bottom: 2px solid #1E3A8A; }
            .header-info { margin-bottom: 20px; }
            .content { line-height: 1.6; }
            .footer { margin-top: 50px; font-size: 0.8em; color: #777; }
        </style>
    </head>
    <body>
        <h1>{{title}}</h1>
        <div class="header-info">
            <p><strong>Prepared for:</strong> {{client_name}}</p>
            <p><strong>Date:</strong> {{date}}</p>
        </div>
        <div class="content">
            <p>{{body}}</p>
        </div>
        <div class="footer">
            <p>Generated via PDF Agent</p>
        </div>
    </body>
    </html>
    """
if "doc_data" not in st.session_state:
    st.session_state.doc_data = {
        "title": "Document Title",
        "client_name": "Acme Corp",
        "date": "2026-08-18",
        "body": "This is a placeholder body matching your uploaded structure."
    }

# 3. Sidebar: PDF Upload & Processing
with st.sidebar:
    st.header("1. Upload & Analyze")
    uploaded_pdf = st.file_uploader("Upload reference PDF template", type=["pdf"])
    
    if uploaded_pdf:
        if st.button("Analyze Template & Summarize"):
            raw_text = extract_text_from_pdf(uploaded_pdf)
            st.session_state.extracted_text = raw_text
            st.success("PDF analyzed successfully!")
            
            # Display Quick Summary
            st.subheader("Summary")
            st.write(raw_text[:400] + "..." if len(raw_text) > 400 else raw_text)

# 4. Main App: Chat Interface & Live Preview
col1, col2 = st.columns([1, 1])

with col1:
    st.header("Chat with PDF Agent")
    st.caption("Instruct the bot to update fields, rewrite sections, or summarize.")

    # Render Chat History
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    # Handle User Input
    if user_prompt := st.chat_input("E.g., Update client name to Beta Ltd, change date to today"):
        st.session_state.messages.append({"role": "user", "content": user_prompt})
        with st.chat_message("user"):
            st.write(user_prompt)

        # Logic for handling updates (Replace this with LLM tool-calling in production)
        response_text = ""
        prompt_lower = user_prompt.lower()
        
        if "client name to" in prompt_lower:
            new_name = user_prompt.split("to")[-1].strip()
            st.session_state.doc_data["client_name"] = new_name
            response_text = f"Updated client name to **{new_name}**."
        elif "summarize" in prompt_lower:
            response_text = f"**Document Summary:** The document is structured as an official report. Key sections include Header, Client Details, and Body."
        else:
            # Fallback mock LLM field update
            st.session_state.doc_data["body"] = user_prompt
            response_text = "Updated the main body text to reflect your prompt."

        st.session_state.messages.append({"role": "assistant", "content": response_text})
        with st.chat_message("assistant"):
            st.write(response_text)

with col2:
    st.header("Live Template & PDF Export")
    
    # Render dynamic HTML by injecting session state variables
    populated_html = st.session_state.template_html
    for key, val in st.session_state.doc_data.items():
        populated_html = populated_html.replace(f"{{{{{key}}}}}", str(val))
    
    # Live preview container
    st.components.v1.html(populated_html, height=350, scrolling=True)
    
    # PDF Compilation Button
    pdf_bytes = generate_pdf_from_html(populated_html)
    st.download_button(
        label="Download Generated PDF",
        data=pdf_bytes,
        file_name="generated_document.pdf",
        mime="application/pdf",
        type="primary"
    )
