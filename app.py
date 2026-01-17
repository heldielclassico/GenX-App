import os
import subprocess
import signal
import time
from openai import OpenAI
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# --- KONFIGURASI OPENROUTER ---
OPENROUTER_API_KEY = "ISI_API_KEY_OPENROUTER_ANDA"

client = OpenAI(
  base_url="https://openrouter.ai/api/v1",
  api_key=OPENROUTER_API_KEY,
)

streamlit_process = None

def setup_streamlit_env():
    """Mencipta folder .streamlit dan fail secrets.toml secara automatik"""
    if not os.path.exists(".streamlit"):
        os.makedirs(".streamlit")
    
    with open(".streamlit/secrets.toml", "w") as f:
        f.write(f'OPENROUTER_API_KEY = "{OPENROUTER_API_KEY}"\n')
        f.write('SYSTEM_PROMPT = "Anda adalah asisten virtual yang membantu."\n')

def kill_current_streamlit():
    global streamlit_process
    if streamlit_process:
        try:
            if os.name == 'nt': 
                subprocess.call(['taskkill', '/F', '/T', '/PID', str(streamlit_process.pid)])
            else:
                os.killpg(os.getpgid(streamlit_process.pid), signal.SIGTERM)
        except: pass
        streamlit_process = None

@app.route('/', methods=['GET', 'POST'])
def index():
    global streamlit_process
    success = False
    
    if request.method == 'POST':
        user_prompt = request.form.get('prompt')
        
        # System Prompt supaya AI menulis kod gaya "Sivita" (Langchain + st.secrets)
        system_instruction = """
        Generate a Python Streamlit script. 
        Requirements:
        1. Use langchain_openai.ChatOpenAI with api_key=st.secrets['OPENROUTER_API_KEY'].
        2. Include a CSS loader animation for 5 seconds using time.sleep and st.session_state.
        3. Use st.form for input and st.chat_message for output.
        4. Style it with custom CSS (rounded corners, professional colors).
        5. DO NOT include markdown backticks (```python). Output ONLY raw code.
        """

        try:
            completion = client.chat.completions.create(
                model="google/gemini-2.0-flash-001",
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": f"Alur Web: {user_prompt}"}
                ]
            )
            
            clean_code = completion.choices[0].message.content.strip()
            # Safety check jika AI masih bagi backticks
            clean_code = clean_code.replace("```python", "").replace("```", "")

            with open("generated_web.py", "w", encoding="utf-8") as f:
                f.write(clean_code)

            kill_current_streamlit()
            setup_streamlit_env() # Pastikan secrets sentiasa sedia
            
            cmd = ["streamlit", "run", "generated_web.py", "--server.port", "8501", "--server.headless", "true"]
            streamlit_process = subprocess.Popen(cmd, preexec_fn=None if os.name == 'nt' else os.setpgrp)
            
            time.sleep(6) # Jeda untuk loader Streamlit
            success = True

        except Exception as e:
            return f"Error: {str(e)}"

    return render_template('index.html', success=success)

@app.route('/stop', methods=['POST'])
def stop_web():
    kill_current_streamlit()
    return jsonify({"status": "stopped"})

if __name__ == '__main__':
    setup_streamlit_env()
    app.run(debug=True, port=5000)
