import os
import streamlit as st
from pypdf import PdfReader
from weasyprint import HTML
from google import genai
from google.genai import types

st.set_page_config(page_title="AI PDF Cloner & Generator", layout="wide")

# 1. API Client Setup (Loaded silently in background)
api_key = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
client = genai.Client(api_key=api_key) if api_key else None

# 2. Session State Initialization
if "messages" not in st.session_state:
    st.session_state.messages = []
if "reference_text" not in st.session_state:
    st.session_state.reference_text = ""
if "current_html" not in st.session_state:
    st.session_state.current_html = """
    <html>
    <head>
        <style>
            body { font-family: 'Helvetica Neue', Arial, sans-serif; margin: 35px; color: #1e293b; background: #ffffff; }
            .header { border-bottom: 3px solid #3b82f6; padding-bottom: 12px; margin-bottom: 25px; }
            h1 { color: #0f172a; margin: 0; font-size: 26px; }
            .subtitle { color: #64748b; font-size: 14px; margin-top: 5px; }
            .section { margin-bottom: 20px; }
            h2 { color: #1e40af; font-size: 18px; border-bottom: 1px solid #e2e8f0; padding-bottom: 6px; }
            p, li { font-size: 13px; line-height: 1.6; color: #334155; }
            .card { background: #f8fafc; border-left: 4px solid #3b82f6; padding: 12px; margin: 10px 0; }
            code { background: #e2e8f0; padding: 2px 6px; border-radius: 4px; font-family: monospace; font-size: 12px; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Document Preview</h1>
            <div class="subtitle">Upload a reference PDF to clone its layout structure.</div>
        </div>
        <div class="section">
            <h2>Getting Started</h2>
            <p>Upload any template PDF, then prompt: <em>"Make a PDF of Python in this same format"</em>.</p>
        </div>
    </body>
    </html>
    """

# 3. Helper Functions
def extract_pdf_content(file):
    reader = PdfReader(file)
    extracted = ""
    for idx, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        extracted += f"--- Page {idx+1} ---\n" + text + "\n"
    return extracted

def generate_pdf(html_string):
    return HTML(string=html_string).write_pdf()

# 4. Clean Sidebar (Only Upload and Extract)
with st.sidebar:
    st.header("📄 Upload Template PDF")
    uploaded_pdf = st.file_uploader("Upload reference PDF format", type=["pdf"])

    if uploaded_pdf and st.button("Extract Layout & Format", use_container_width=True):
        if not client:
            st.error("API Key not found in environment or secrets.")
        else:
            with st.spinner("Analyzing PDF format & layout..."):
                raw_text = extract_pdf_content(uploaded_pdf)
                st.session_state.reference_text = raw_text

                extract_prompt = f"""
                Analyze the following text extracted from a reference PDF document. 
                Identify its visual sections, typography hierarchy, tables, headers, footers, and layout structure.
                Create a complete, single-file HTML document (with internal CSS in <style>) that visually recreates 
                the exact same structure and design format. 
                Return ONLY raw valid HTML code without markdown fences.

                Reference Document Content:
                {raw_text[:4000]}
                """
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=extract_prompt
                )
                clean_html = response.text.replace("```html", "").replace("```", "").strip()
                st.session_state.current_html = clean_html
                st.success("Template cloned successfully!")

# 5. Main App: Chat & Live Preview
col1, col2 = st.columns([1.1, 0.9])

with col1:
    st.header("💬 Chat & Document Generator")
    st.caption("Instruct the AI to generate new topics (e.g. *'Make a PDF of Python in this format'*), summarize, or edit fields.")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if user_prompt := st.chat_input("E.g., Make a PDF of Python core concepts in the uploaded format..."):
        if not client:
            st.error("API Key is missing. Add GEMINI_API_KEY to your Streamlit secrets.")
        else:
            st.session_state.messages.append({"role": "user", "content": user_prompt})
            with st.chat_message("user"):
                st.markdown(user_prompt)

            with st.chat_message("assistant"):
                with st.spinner("Updating document..."):
                    system_prompt = f"""
                    You are an expert document design and PDF generator assistant.
                    
                    Current Reference PDF Extracted Content:
                    {st.session_state.reference_text[:3000] if st.session_state.reference_text else "Standard clean technical report format."}

                    Current HTML/CSS Template:
                    {st.session_state.current_html}

                    Instructions:
                    1. If the user asks for a summary, provide a clear, concise bulleted summary of the reference PDF.
                    2. If the user asks to create a new PDF on a new topic (e.g., 'Make a PDF of Python' or 'Make a resume for a Data Scientist') in the same format:
                       - Generate high quality, comprehensive content for the requested topic.
                       - Map this new content into the exact HTML/CSS layout structure of the current template (same font styles, headers, colors, cards, tables, margins).
                       - Return your output in the following format:
                         [RESPONSE]
                         A friendly message explaining what you generated/updated.
                         [/RESPONSE]
                         [HTML]
                         The complete updated HTML code (with internal CSS, printable on standard A4, ready for WeasyPrint).
                         [/HTML]
                    """

                    response = client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=[
                            types.Content(role="user", parts=[types.Part.from_text(text=f"{system_prompt}\n\nUser Request: {user_prompt}")])
                        ]
                    )
                    
                    reply = response.text

                    if "[HTML]" in reply and "[/HTML]" in reply:
                        chat_msg = reply.split("[HTML]")[0].replace("[RESPONSE]", "").replace("[/RESPONSE]", "").strip()
                        new_html = reply.split("[HTML]")[1].split("[/HTML]")[0].replace("```html", "").replace("```", "").strip()
                        st.session_state.current_html = new_html
                    else:
                        chat_msg = reply

                    st.markdown(chat_msg)
                    st.session_state.messages.append({"role": "assistant", "content": chat_msg})

with col2:
    st.header("📄 Live PDF Preview & Export")

    # Render Preview
    st.components.v1.html(st.session_state.current_html, height=520, scrolling=True)

    # Download Button
    try:
        pdf_data = generate_pdf(st.session_state.current_html)
        st.download_button(
            label="📥 Download Generated PDF",
            data=pdf_data,
            file_name="custom_document.pdf",
            mime="application/pdf",
            type="primary",
            use_container_width=True
        )
    except Exception as e:
        st.error(f"Error compiling PDF: {e}")
