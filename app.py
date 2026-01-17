import os
import subprocess
import signal
import time
from openai import OpenAI
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# --- KONFIGURASI ---
OPENROUTER_API_KEY = "YOUR_OPENROUTER_API_KEY"
# Deteksi apakah berjalan di Cloud (Streamlit Share)
IS_CLOUD = os.getenv("STREAMLIT_SERVER_PORT") is not None 

client = OpenAI(
  base_url="https://openrouter.ai/api/v1",
  api_key=OPENROUTER_API_KEY,
)

streamlit_process = None

def setup_streamlit_env():
    """Menyiapkan folder secrets hanya jika di lokal untuk menghindari Permission Error di Cloud"""
    if IS_CLOUD:
        print("Running on Cloud: Skipping manual secrets creation.")
        return

    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        st_dir = os.path.join(base_dir, ".streamlit")
        os.makedirs(st_dir, exist_ok=True)
        
        with open(os.path.join(st_dir, "secrets.toml"), "w", encoding="utf-8") as f:
            f.write(f'OPENROUTER_API_KEY = "{OPENROUTER_API_KEY}"\n')
            f.write('SYSTEM_PROMPT = "Anda adalah asisten virtual ahli."\n')
        print("Local Environment: .streamlit/secrets.toml updated.")
    except Exception as e:
        print(f"Error setting up local env: {e}")

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
        
        system_instruction = (
            "You are a Streamlit expert. Generate a complete Python Streamlit script. "
            "Use 'langchain_openai' with api_key=st.secrets['OPENROUTER_API_KEY']. "
            "Include a professional CSS loader for 5 seconds using st.session_state. "
            "Output ONLY raw Python code. No conversational text, no markdown backticks."
        )

        try:
            completion = client.chat.completions.create(
                model="google/gemini-2.0-flash-001",
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": f"Create web with flow: {user_prompt}"}
                ]
            )
            
            clean_code = completion.choices[0].message.content.strip()
            clean_code = clean_code.replace("```python", "").replace("```", "")

            with open("generated_web.py", "w", encoding="utf-8") as f:
                f.write(clean_code)

            kill_current_streamlit()
            
            # Jalankan Streamlit
            cmd = ["streamlit", "run", "generated_web.py", "--server.port", "8501", "--server.headless", "true"]
            streamlit_process = subprocess.Popen(cmd, preexec_fn=None if os.name == 'nt' else os.setpgrp)
            
            time.sleep(6) 
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
    # Inisialisasi file agar tidak error saat start
    if not os.path.exists("generated_web.py"):
        with open("generated_web.py", "w") as f:
            f.write("import streamlit as st\nst.title('AI Web Builder Ready')")
            
    app.run(debug=True, port=5000)
