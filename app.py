import os
import streamlit as st
from pypdf import PdfReader
from weasyprint import HTML
from groq import Groq
from google import genai
from google.genai import types
from openai import OpenAI

st.set_page_config(page_title="AI PDF Cloner & Generator", layout="wide")

# 1. Multi-Provider Client Setup
groq_key = st.secrets.get("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))
gemini_key = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
openai_key = st.secrets.get("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", ""))

groq_client = Groq(api_key=groq_key) if groq_key else None
gemini_client = genai.Client(api_key=gemini_key) if gemini_key else None
openai_client = OpenAI(api_key=openai_key) if openai_key else None

# Universal LLM caller across active free models
def generate_llm_response(messages, system_prompt="", temperature=0.2):
    last_error = None

    # Priority 1: Groq with active Llama 3.3 & Llama 3.1 production models
    if groq_client:
        groq_active_models = [
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "gemma2-9b-it"
        ]
        groq_msgs = []
        if system_prompt:
            groq_msgs.append({"role": "system", "content": system_prompt})
        groq_msgs.extend(messages)

        for model in groq_active_models:
            try:
                response = groq_client.chat.completions.create(
                    messages=groq_msgs,
                    model=model,
                    temperature=temperature
                )
                return response.choices[0].message.content
            except Exception as e:
                last_error = e
                continue

    # Priority 2: Google Gemini Flash (Generous free tier)
    if gemini_client:
        try:
            full_prompt = f"{system_prompt}\n\n" if system_prompt else ""
            for m in messages:
                full_prompt += f"{m['role'].upper()}: {m['content']}\n"
            
            resp = gemini_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=full_prompt
            )
            return resp.text
        except Exception as e:
            last_error = e

    # Priority 3: OpenAI / OpenRouter Fallback
    if openai_client:
        try:
            oai_msgs = []
            if system_prompt:
                oai_msgs.append({"role": "system", "content": system_prompt})
            oai_msgs.extend(messages)
            
            resp = openai_client.chat.completions.create(
                messages=oai_msgs,
                model="gpt-4o-mini",
                temperature=temperature
            )
            return resp.choices[0].message.content
        except Exception as e:
            last_error = e

    raise RuntimeError(f"No LLM provider succeeded. Please verify your API keys. Last error: {last_error}")

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
            <p>Upload any template PDF on the left, then ask in chat: <em>"Make a PDF of Python in this same format"</em>.</p>
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

# 4. Sidebar: Upload & Extract
with st.sidebar:
    st.header("📄 Upload Template PDF")
    uploaded_pdf = st.file_uploader("Upload reference PDF format", type=["pdf"])

    if uploaded_pdf and st.button("Extract Layout & Format", use_container_width=True):
        if not (groq_client or gemini_client or openai_client):
            st.error("No API keys found. Set GROQ_API_KEY or GEMINI_API_KEY in secrets.")
        else:
            with st.spinner("Analyzing PDF format & layout..."):
                try:
                    raw_text = extract_pdf_content(uploaded_pdf)
                    st.session_state.reference_text = raw_text

                    extract_prompt = f"""
                    Analyze the following text extracted from a reference PDF document. 
                    Identify its visual sections, typography hierarchy, tables, headers, footers, and layout structure.
                    Create a complete, single-file HTML document (with internal CSS inside <style>) that visually recreates 
                    the exact same structure and design format. 
                    Return ONLY raw valid HTML code without markdown fences.

                    Reference Document Content:
                    {raw_text[:4000]}
                    """

                    response_html = generate_llm_response(
                        messages=[{"role": "user", "content": extract_prompt}],
                        temperature=0.2
                    )

                    clean_html = response_html.replace("```html", "").replace("```", "").strip()
                    st.session_state.current_html = clean_html
                    st.success("Template format extracted successfully!")
                except Exception as e:
                    st.error(f"Extraction error: {e}")

# 5. Main App: Chat & Live Preview
col1, col2 = st.columns([1.1, 0.9])

with col1:
    st.header("💬 Chat & Document Generator")
    st.caption("Ask to generate new topics (e.g. *'Make a PDF of Python in this format'*), summarize, or modify sections.")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if user_prompt := st.chat_input("E.g., Make a PDF of Python core concepts in this format..."):
        if not (groq_client or gemini_client or openai_client):
            st.error("Missing API Key. Add GROQ_API_KEY or GEMINI_API_KEY to your Streamlit secrets.")
        else:
            st.session_state.messages.append({"role": "user", "content": user_prompt})
            with st.chat_message("user"):
                st.markdown(user_prompt)

            with st.chat_message("assistant"):
                with st.spinner("Generating document..."):
                    try:
                        system_prompt = f"""
                        You are an expert document design and PDF generator assistant.
                        
                        Current Reference PDF Extracted Content:
                        {st.session_state.reference_text[:3000] if st.session_state.reference_text else "Standard clean technical report format."}

                        Current HTML/CSS Template:
                        {st.session_state.current_html}

                        Instructions:
                        1. If the user asks for a summary, provide a clear, concise bulleted summary of the reference PDF.
                        2. If the user asks to create a new PDF on a new topic (e.g., 'Make a PDF of Python' or 'Make a resume for a Data Scientist') in the same format:
                           - Generate high-quality, comprehensive content for the requested topic.
                           - Map this new content into the exact HTML/CSS layout structure of the current template (same font styles, headers, colors, cards, tables, margins).
                           - Return your output in the following format:
                             [RESPONSE]
                             A brief explanation of what was updated.
                             [/RESPONSE]
                             [HTML]
                             The complete updated HTML code (with internal CSS, printable on standard A4, ready for WeasyPrint).
                             [/HTML]
                        """

                        reply = generate_llm_response(
                            messages=[{"role": "user", "content": user_prompt}],
                            system_prompt=system_prompt,
                            temperature=0.3
                        )

                        if "[HTML]" in reply and "[/HTML]" in reply:
                            chat_msg = reply.split("[HTML]")[0].replace("[RESPONSE]", "").replace("[/RESPONSE]", "").strip()
                            new_html = reply.split("[HTML]")[1].split("[/HTML]")[0].replace("```html", "").replace("```", "").strip()
                            st.session_state.current_html = new_html
                        else:
                            chat_msg = reply

                        st.markdown(chat_msg)
                        st.session_state.messages.append({"role": "assistant", "content": chat_msg})
                    except Exception as err:
                        error_msg = f"Generation failed: {err}"
                        st.error(error_msg)
                        st.session_state.messages.append({"role": "assistant", "content": error_msg})

with col2:
    st.header("📄 Live PDF Preview & Export")

    # Live Render Preview
    st.components.v1.html(st.session_state.current_html, height=520, scrolling=True)

    # PDF Download Button
    try:
        pdf_data = generate_pdf(st.session_state.current_html)
        st.download_button(
            label="📥 Download Generated PDF",
            data=pdf_data,
            file_name="generated_document.pdf",
            mime="application/pdf",
            type="primary",
            use_container_width=True
        )
    except Exception as e:
        st.error(f"Error compiling PDF: {e}")
