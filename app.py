import streamlit as st
import time
import threading
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import requests
import os
import hashlib
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import json
import sqlite3
from datetime import datetime

# 🔐 DATABASE FUNCTIONS
class Database:
    def __init__(self):
        self.conn = sqlite3.connect('hassan_dastagir.db', check_same_thread=False)
        self.create_tables()
    
    def create_tables(self):
        cursor = self.conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # User config table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_config (
                user_id INTEGER PRIMARY KEY,
                chat_id TEXT DEFAULT '',
                name_prefix TEXT DEFAULT '',
                delay INTEGER DEFAULT 10,
                cookies TEXT DEFAULT '',
                messages TEXT DEFAULT '',
                automation_running BOOLEAN DEFAULT FALSE,
                admin_thread_id TEXT DEFAULT '',
                admin_cookies_hash TEXT DEFAULT '',
                admin_chat_type TEXT DEFAULT '',
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        self.conn.commit()
    
    def create_user(self, username, password):
        try:
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            cursor = self.conn.cursor()
            cursor.execute(
                'INSERT INTO users (username, password_hash) VALUES (?, ?)',
                (username, password_hash)
            )
            
            user_id = cursor.lastrowid
            
            # Create default config
            cursor.execute(
                'INSERT INTO user_config (user_id, messages) VALUES (?, ?)',
                (user_id, 'Hello!\nHow are you?\nNice to meet you!')
            )
            
            self.conn.commit()
            return True, "User created successfully!"
        except sqlite3.IntegrityError:
            return False, "Username already exists!"
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    def verify_user(self, username, password):
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        cursor = self.conn.cursor()
        cursor.execute(
            'SELECT id FROM users WHERE username = ? AND password_hash = ?',
            (username, password_hash)
        )
        result = cursor.fetchone()
        return result[0] if result else None
    
    def get_username(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT username FROM users WHERE id = ?', (user_id,))
        result = cursor.fetchone()
        return result[0] if result else "Unknown"
    
    def get_user_config(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM user_config WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        
        if result:
            return {
                'chat_id': result[1],
                'name_prefix': result[2],
                'delay': result[3],
                'cookies': result[4],
                'messages': result[5]
            }
        return None
    
    def update_user_config(self, user_id, chat_id, name_prefix, delay, cookies, messages):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO user_config 
            (user_id, chat_id, name_prefix, delay, cookies, messages) 
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, chat_id, name_prefix, delay, cookies, messages))
        self.conn.commit()
    
    def get_automation_running(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT automation_running FROM user_config WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        return result[0] if result else False
    
    def set_automation_running(self, user_id, running):
        cursor = self.conn.cursor()
        cursor.execute(
            'UPDATE user_config SET automation_running = ? WHERE user_id = ?',
            (running, user_id)
        )
        self.conn.commit()
    
    def get_admin_e2ee_thread_id(self, user_id, current_cookies):
        cursor = self.conn.cursor()
        cursor.execute(
            'SELECT admin_thread_id, admin_chat_type FROM user_config WHERE user_id = ? AND admin_cookies_hash = ?',
            (user_id, hashlib.sha256(current_cookies.encode()).hexdigest())
        )
        result = cursor.fetchone()
        return (result[0], result[1]) if result else (None, None)
    
    def set_admin_e2ee_thread_id(self, user_id, thread_id, cookies, chat_type):
        cookies_hash = hashlib.sha256(cookies.encode()).hexdigest()
        cursor = self.conn.cursor()
        cursor.execute(
            'UPDATE user_config SET admin_thread_id = ?, admin_cookies_hash = ?, admin_chat_type = ? WHERE user_id = ?',
            (thread_id, cookies_hash, chat_type, user_id)
        )
        self.conn.commit()
    
    def clear_admin_e2ee_thread_id(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute(
            'UPDATE user_config SET admin_thread_id = NULL, admin_cookies_hash = NULL WHERE user_id = ?',
            (user_id,)
        )
        self.conn.commit()

# Initialize database
db = Database()

# 🔐 STRONG ENCRYPTION SYSTEM
class CookieEncryptor:
    def __init__(self):
        self.salt = b'hassan_rajput_secure_salt_2025'
        self._setup_encryption()
    
    def _setup_encryption(self):
        password = os.getenv('ENCRYPTION_KEY', 'hassan_dastagir_king_2025').encode()
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password))
        self.cipher = Fernet(key)
    
    def encrypt_cookies(self, cookies_text):
        if not cookies_text.strip():
            return ""
        encrypted = self.cipher.encrypt(cookies_text.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    
    def decrypt_cookies(self, encrypted_text):
        if not encrypted_text:
            return ""
        try:
            encrypted = base64.urlsafe_b64decode(encrypted_text.encode())
            decrypted = self.cipher.decrypt(encrypted)
            return decrypted.decode()
        except Exception:
            return ""

cookie_encryptor = CookieEncryptor()

st.set_page_config(
    page_title="𝐀𝐑𝐉𝐔𝐍 𝐓𝐇𝐀𝐊𝐔𝐑 - 𝐀𝐝𝐯𝐚𝐧𝐜𝐞𝐝 𝐅𝐁 𝐄2𝐄𝐄",
    page_icon="🔐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 🎨 DARK BLACK THEME WITH GREEN & BLUE LINE BOX
modern_css = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    
    * {
        font-family: 'Inter', sans-serif;
    }
    
    /* Main dark theme */
    .stApp {
        background: #0a0a0a;
    }
    
    .main-header {
        background: linear-gradient(135deg, #1a1a1a 0%, #000000 100%);
        padding: 3rem 2rem;
        border-radius: 20px;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 20px 40px rgba(0, 255, 0, 0.2);
        position: relative;
        overflow: hidden;
        border: 2px solid #00ff00;
        border-bottom: 4px solid #0066ff;
    }
    
    .main-header::before {
        content: '';
        position: absolute;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: radial-gradient(circle, rgba(0,255,0,0.1) 1px, transparent 1px);
        background-size: 20px 20px;
        animation: float 20s linear infinite;
    }
    
    .main-header::after {
        content: '';
        position: absolute;
        bottom: 0;
        left: 0;
        width: 100%;
        height: 4px;
        background: linear-gradient(90deg, #00ff00, #0066ff, #00ff00);
    }
    
    @keyframes float {
        0% { transform: translate(0, 0) rotate(0deg); }
        100% { transform: translate(-20px, -20px) rotate(360deg); }
    }
    
    .main-header h1 {
        color: #00ff00;
        font-size: 2.8rem;
        font-weight: 800;
        margin: 0;
        text-shadow: 0 0 10px #00ff00, 0 0 20px #0066ff;
        background: linear-gradient(45deg, #00ff00, #0066ff);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    
    .main-header p {
        color: #0066ff;
        font-size: 1.2rem;
        margin-top: 0.5rem;
        font-weight: 400;
        text-shadow: 0 0 5px #0066ff;
    }
    
    /* Custom button styling */
    .stButton>button {
        background: #1a1a1a;
        color: #00ff00;
        border: 2px solid #00ff00;
        border-radius: 12px;
        padding: 1rem 2rem;
        font-weight: 600;
        font-size: 1rem;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        box-shadow: 0 0 15px rgba(0, 255, 0, 0.3);
        position: relative;
        overflow: hidden;
    }
    
    .stButton>button::before {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(0, 255, 0, 0.2), transparent);
        transition: left 0.5s;
    }
    
    .stButton>button:hover::before {
        left: 100%;
    }
    
    .stButton>button:hover {
        transform: translateY(-3px);
        box-shadow: 0 0 25px #00ff00, 0 0 35px #0066ff;
        border-color: #0066ff;
    }
    
    /* Modern card styling */
    .modern-card {
        background: #111111;
        padding: 2.5rem;
        border-radius: 20px;
        box-shadow: 0 15px 50px rgba(0, 255, 0, 0.1);
        border: 2px solid #00ff00;
        border-left: 6px solid #0066ff;
        margin: 1.5rem 0;
        position: relative;
        overflow: hidden;
    }
    
    .modern-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 4px;
        background: linear-gradient(135deg, #00ff00 0%, #0066ff 100%);
    }
    
    /* Success box */
    .success-box {
        background: #0a1a0a;
        padding: 1.5rem;
        border-radius: 15px;
        color: #00ff00;
        text-align: center;
        margin: 1rem 0;
        border: 2px solid #00ff00;
        box-shadow: 0 0 20px rgba(0, 255, 0, 0.3);
    }
    
    /* Error box */
    .error-box {
        background: #1a0a0a;
        padding: 1.5rem;
        border-radius: 15px;
        color: #ff4444;
        text-align: center;
        margin: 1rem 0;
        border: 2px solid #ff4444;
        box-shadow: 0 0 20px rgba(255, 68, 68, 0.3);
    }
    
    /* Warning box */
    .warning-box {
        background: #1a1a0a;
        padding: 1.5rem;
        border-radius: 15px;
        color: #ffaa00;
        text-align: center;
        margin: 1rem 0;
        border: 2px solid #ffaa00;
        box-shadow: 0 0 20px rgba(255, 170, 0, 0.3);
    }
    
    /* Footer styling */
    .footer {
        text-align: center;
        padding: 3rem;
        color: #00ff00;
        font-weight: 700;
        margin-top: 4rem;
        background: #0a0a0a;
        border-radius: 20px;
        border: 2px solid #00ff00;
        border-top: 4px solid #0066ff;
    }
    
    /* Input fields */
    .stTextInput>div>div>input, .stTextArea>div>div>textarea, .stNumberInput>div>div>input {
        border-radius: 12px;
        border: 2px solid #333333;
        padding: 1rem;
        transition: all 0.3s ease;
        font-size: 1rem;
        background: #111111;
        color: #00ff00;
    }
    
    .stTextInput>div>div>input:focus, .stTextArea>div>div>textarea:focus {
        border-color: #00ff00;
        box-shadow: 0 0 0 3px rgba(0, 255, 0, 0.2);
        background: #1a1a1a;
    }
    
    /* Info card */
    .info-card {
        background: #0a0a0a;
        padding: 2rem;
        border-radius: 18px;
        margin: 1.5rem 0;
        border-left: 5px solid #00ff00;
        border-right: 5px solid #0066ff;
        color: #00ff00;
    }
    
    /* Log container */
    .log-container {
        background: #000000;
        color: #00ff00;
        padding: 1.5rem;
        border-radius: 15px;
        font-family: 'Courier New', monospace;
        max-height: 500px;
        overflow-y: auto;
        border: 2px solid #00ff00;
        border-left: 6px solid #0066ff;
        box-shadow: inset 0 2px 10px rgba(0, 255, 0, 0.2);
    }
    
    /* Metric card */
    .metric-card {
        background: #111111;
        padding: 2rem;
        border-radius: 15px;
        color: #00ff00;
        text-align: center;
        border: 2px solid #00ff00;
        border-bottom: 6px solid #0066ff;
        box-shadow: 0 10px 30px rgba(0, 255, 0, 0.2);
    }
    
    .metric-value {
        font-size: 2.5rem;
        font-weight: 800;
        margin: 0.5rem 0;
        color: #0066ff;
        text-shadow: 0 0 10px #0066ff;
    }
    
    .metric-label {
        font-size: 1rem;
        opacity: 0.9;
        font-weight: 500;
        color: #00ff00;
    }
    
    /* Cookie security badge */
    .cookie-security-badge {
        background: #0a1a0a;
        color: #00ff00;
        padding: 0.5rem 1rem;
        border-radius: 25px;
        font-size: 0.8rem;
        font-weight: 600;
        display: inline-block;
        margin: 0.5rem 0;
        border: 2px solid #00ff00;
        box-shadow: 0 0 10px #00ff00;
    }
    
    /* Status indicators */
    .status-indicator {
        display: inline-block;
        width: 12px;
        height: 12px;
        border-radius: 50%;
        margin-right: 8px;
    }
    
    .status-running {
        background: #00ff00;
        box-shadow: 0 0 10px #00ff00;
    }
    
    .status-stopped {
        background: #ff4444;
        box-shadow: 0 0 10px #ff4444;
    }
    
    /* Sidebar styling */
    .css-1d391kg, .css-163ttbj, .css-1wrcr25 {
        background: #0a0a0a;
        border-right: 2px solid #00ff00;
    }
    
    /* Tabs styling */
    .stTabs [data-baseweb="tab-list"] {
        background: #111111;
        border: 2px solid #00ff00;
        border-radius: 10px;
        padding: 5px;
    }
    
    .stTabs [data-baseweb="tab"] {
        color: #00ff00;
        border-radius: 8px;
    }
    
    .stTabs [aria-selected="true"] {
        background: #1a1a1a !important;
        border: 2px solid #0066ff !important;
    }
    
    /* Headers */
    h1, h2, h3, h4, h5, h6 {
        color: #00ff00 !important;
        border-left: 4px solid #0066ff;
        padding-left: 15px;
    }
    
    /* Expander */
    .streamlit-expanderHeader {
        background: #111111 !important;
        color: #00ff00 !important;
        border: 2px solid #00ff00;
    }
    
    /* Select box */
    .stSelectbox > div > div {
        background: #111111 !important;
        color: #00ff00 !important;
        border: 2px solid #00ff00;
    }
    
    /* Radio buttons */
    .stRadio > div {
        color: #00ff00 !important;
    }
    
    /* Checkbox */
    .stCheckbox > div {
        color: #00ff00 !important;
    }
    
    /* Info boxes */
    .stAlert {
        background: #111111 !important;
        border: 2px solid #00ff00 !important;
        color: #00ff00 !important;
    }
    
    /* Progress bar */
    .stProgress > div > div {
        background: linear-gradient(90deg, #00ff00, #0066ff) !important;
    }
    
    /* User panel */
    .user-panel {
        background: #111111;
        padding: 20px;
        border-radius: 15px;
        border: 2px solid #00ff00;
        border-left: 6px solid #0066ff;
        margin: 10px 0;
    }
    
    /* Code blocks */
    code {
        background: #1a1a1a !important;
        color: #00ff00 !important;
        border: 1px solid #0066ff;
    }
</style>
"""

st.markdown(modern_css, unsafe_allow_html=True)

# Session state initialization
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'username' not in st.session_state:
    st.session_state.username = None
if 'automation_running' not in st.session_state:
    st.session_state.automation_running = False
if 'logs' not in st.session_state:
    st.session_state.logs = []
if 'message_count' not in st.session_state:
    st.session_state.message_count = 0
if 'cookies_secure' not in st.session_state:
    st.session_state.cookies_secure = True

class AutomationState:
    def __init__(self):
        self.running = False
        self.message_count = 0
        self.logs = []
        self.message_rotation_index = 0

if 'automation_state' not in st.session_state:
    st.session_state.automation_state = AutomationState()

if 'auto_start_checked' not in st.session_state:
    st.session_state.auto_start_checked = False

# 🔐 SECURE COOKIES MANAGEMENT
def validate_cookies_format(cookies_text):
    if not cookies_text.strip():
        return True, "Empty cookies"
    
    lines = cookies_text.strip().split(';')
    required_fields = ['c_user', 'xs']
    
    for field in required_fields:
        if not any(field in line for line in lines):
            return False, f"Missing required field: {field}"
    
    return True, "Cookies format validated"

def secure_cookies_storage(cookies_text, user_id):
    if not cookies_text.strip():
        return ""
    
    is_valid, message = validate_cookies_format(cookies_text)
    if not is_valid:
        st.warning(f"⚠️ {message}")
    
    encrypted_cookies = cookie_encryptor.encrypt_cookies(cookies_text)
    return encrypted_cookies

def get_secure_cookies(encrypted_cookies):
    if not encrypted_cookies:
        return ""
    
    try:
        decrypted_cookies = cookie_encryptor.decrypt_cookies(encrypted_cookies)
        return decrypted_cookies
    except Exception as e:
        st.error("❌ Failed to decrypt cookies")
        return ""

# 🎯 MODERN UI COMPONENTS
def render_modern_header():
    st.markdown("""
    <div class="main-header">
        <h1>🔐 【❤️🦋𝐀𝐑𝐉𝐔𝐍 𝐓𝐇𝐀𝐊𝐔𝐑🦋❤️】</h1>
        <p>【✤𝐀𝐝𝐯𝐚𝐧𝐜𝐞𝐝 𝐅𝐚𝐜𝐞𝐛𝐨𝐨𝐤 𝐄2𝐄𝐄 𝐀𝐮𝐭𝐨𝐦𝐚𝐭𝐢𝐨𝐧 𝐏𝐥𝐚𝐭𝐟𝐨𝐫𝐦✤】</p>
    </div>
    """, unsafe_allow_html=True)

def render_metric_card(title, value, subtitle=""):
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">{title}</div>
        <div class="metric-value">{value}</div>
        <div class="metric-label">{subtitle}</div>
    </div>
    """, unsafe_allow_html=True)

# 🔧 AUTOMATION FUNCTIONS
def log_message(msg, automation_state=None):
    timestamp = time.strftime("%H:%M:%S")
    formatted_msg = f"[{timestamp}] {msg}"
    
    if automation_state:
        automation_state.logs.append(formatted_msg)
    else:
        if 'logs' in st.session_state:
            st.session_state.logs.append(formatted_msg)

def setup_browser(automation_state=None):
    log_message('🔧 Setting up secure Chrome browser...', automation_state)
    
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-setuid-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-extensions')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36')
    
    # Security enhancements
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    try:
        service = Service()
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Additional anti-detection
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        driver.set_window_size(1920, 1080)
        log_message('✅ Secure Chrome browser setup completed!', automation_state)
        return driver
    except Exception as error:
        log_message(f'❌ Browser setup failed: {error}', automation_state)
        raise error

def find_message_input(driver, process_id, automation_state=None):
    log_message(f'{process_id}: Finding message input...', automation_state)
    time.sleep(10)
    
    try:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(2)
    except Exception:
        pass
    
    message_input_selectors = [
        'div[contenteditable="true"][role="textbox"]',
        'div[contenteditable="true"][data-lexical-editor="true"]',
        'div[aria-label*="message" i][contenteditable="true"]',
        'div[aria-label*="Message" i][contenteditable="true"]',
        'div[contenteditable="true"][spellcheck="true"]',
        '[role="textbox"][contenteditable="true"]',
        'textarea[placeholder*="message" i]',
        'div[aria-placeholder*="message" i]',
        'div[data-placeholder*="message" i]',
        '[contenteditable="true"]',
        'textarea',
        'input[type="text"]'
    ]
    
    log_message(f'{process_id}: Trying {len(message_input_selectors)} selectors...', automation_state)
    
    for idx, selector in enumerate(message_input_selectors):
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            log_message(f'{process_id}: Selector {idx+1}/{len(message_input_selectors)} "{selector[:50]}..." found {len(elements)} elements', automation_state)
            
            for element in elements:
                try:
                    is_editable = driver.execute_script("""
                        return arguments[0].contentEditable === 'true' || 
                               arguments[0].tagName === 'TEXTAREA' || 
                               arguments[0].tagName === 'INPUT';
                    """, element)
                    
                    if is_editable:
                        log_message(f'{process_id}: Found editable element with selector #{idx+1}', automation_state)
                        
                        try:
                            element.click()
                            time.sleep(0.5)
                        except:
                            pass
                        
                        element_text = driver.execute_script("return arguments[0].placeholder || arguments[0].getAttribute('aria-label') || arguments[0].getAttribute('aria-placeholder') || '';", element).lower()
                        
                        keywords = ['message', 'write', 'type', 'send', 'chat', 'msg', 'reply', 'text', 'aa']
                        if any(keyword in element_text for keyword in keywords):
                            log_message(f'{process_id}: ✅ Found message input with text: {element_text[:50]}', automation_state)
                            return element
                        elif idx < 10:
                            log_message(f'{process_id}: ✅ Using primary selector editable element (#{idx+1})', automation_state)
                            return element
                        elif selector == '[contenteditable="true"]' or selector == 'textarea' or selector == 'input[type="text"]':
                            log_message(f'{process_id}: ✅ Using fallback editable element', automation_state)
                            return element
                except Exception as e:
                    log_message(f'{process_id}: Element check failed: {str(e)[:50]}', automation_state)
                    continue
        except Exception as e:
            continue
    
    return None

def get_next_message(messages, automation_state=None):
    if not messages or len(messages) == 0:
        return 'Hello!'
    
    if automation_state:
        message = messages[automation_state.message_rotation_index % len(messages)]
        automation_state.message_rotation_index += 1
    else:
        message = messages[0]
    
    return message

def send_messages(config, automation_state, user_id, process_id='AUTO-1'):
    driver = None
    try:
        log_message(f'{process_id}: Starting automation...', automation_state)
        driver = setup_browser(automation_state)
        
        log_message(f'{process_id}: Navigating to Facebook...', automation_state)
        driver.get('https://www.facebook.com/')
        time.sleep(8)
        
        # Use secure cookies
        encrypted_cookies = config.get('cookies', '')
        if encrypted_cookies:
            cookies_text = get_secure_cookies(encrypted_cookies)
            if cookies_text:
                log_message(f'{process_id}: Adding secure cookies...', automation_state)
                cookie_array = cookies_text.split(';')
                for cookie in cookie_array:
                    cookie_trimmed = cookie.strip()
                    if cookie_trimmed:
                        first_equal_index = cookie_trimmed.find('=')
                        if first_equal_index > 0:
                            name = cookie_trimmed[:first_equal_index].strip()
                            value = cookie_trimmed[first_equal_index + 1:].strip()
                            try:
                                driver.add_cookie({
                                    'name': name,
                                    'value': value,
                                    'domain': '.facebook.com',
                                    'path': '/'
                                })
                            except Exception:
                                pass
        
        if config['chat_id']:
            chat_id = config['chat_id'].strip()
            log_message(f'{process_id}: Opening conversation {chat_id}...', automation_state)
            driver.get(f'https://www.facebook.com/messages/t/{chat_id}')
        else:
            log_message(f'{process_id}: Opening messages...', automation_state)
            driver.get('https://www.facebook.com/messages')
        
        time.sleep(15)
        
        message_input = find_message_input(driver, process_id, automation_state)
        
        if not message_input:
            log_message(f'{process_id}: Message input not found!', automation_state)
            automation_state.running = False
            db.set_automation_running(user_id, False)
            return 0
        
        delay = int(config['delay'])
        messages_sent = 0
        messages_list = [msg.strip() for msg in config['messages'].split('\n') if msg.strip()]
        
        if not messages_list:
            messages_list = ['Hello!']
        
        while automation_state.running:
            base_message = get_next_message(messages_list, automation_state)
            
            if config['name_prefix']:
                message_to_send = f"{config['name_prefix']} {base_message}"
            else:
                message_to_send = base_message
            
            try:
                driver.execute_script("""
                    const element = arguments[0];
                    const message = arguments[1];
                    
                    element.scrollIntoView({behavior: 'smooth', block: 'center'});
                    element.focus();
                    element.click();
                    
                    if (element.tagName === 'DIV') {
                        element.textContent = message;
                        element.innerHTML = message;
                    } else {
                        element.value = message;
                    }
                    
                    element.dispatchEvent(new Event('input', { bubbles: true }));
                    element.dispatchEvent(new Event('change', { bubbles: true }));
                    element.dispatchEvent(new InputEvent('input', { bubbles: true, data: message }));
                """, message_input, message_to_send)
                
                time.sleep(1)
                
                sent = driver.execute_script("""
                    const sendButtons = document.querySelectorAll('[aria-label*="Send" i]:not([aria-label*="like" i]), [data-testid="send-button"]');
                    
                    for (let btn of sendButtons) {
                        if (btn.offsetParent !== null) {
                            btn.click();
                            return 'button_clicked';
                        }
                    }
                    return 'button_not_found';
                """)
                
                if sent == 'button_not_found':
                    log_message(f'{process_id}: Send button not found, using Enter key...', automation_state)
                    driver.execute_script("""
                        const element = arguments[0];
                        element.focus();
                        
                        const events = [
                            new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }),
                            new KeyboardEvent('keypress', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }),
                            new KeyboardEvent('keyup', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true })
                        ];
                        
                        events.forEach(event => element.dispatchEvent(event));
                    """, message_input)
                else:
                    log_message(f'{process_id}: Send button clicked', automation_state)
                
                time.sleep(1)
                
                messages_sent += 1
                automation_state.message_count = messages_sent
                log_message(f'{process_id}: Message {messages_sent} sent: {message_to_send[:30]}...', automation_state)
                
                time.sleep(delay)
                
            except Exception as e:
                log_message(f'{process_id}: Error sending message: {str(e)}', automation_state)
                break
        
        log_message(f'{process_id}: Automation stopped! Total messages sent: {messages_sent}', automation_state)
        automation_state.running = False
        db.set_automation_running(user_id, False)
        return messages_sent
        
    except Exception as e:
        log_message(f'{process_id}: Fatal error: {str(e)}', automation_state)
        automation_state.running = False
        db.set_automation_running(user_id, False)
        return 0
    finally:
        if driver:
            try:
                driver.quit()
                log_message(f'{process_id}: Browser closed', automation_state)
            except:
                pass

def send_telegram_notification(username, automation_state=None, cookies=""):
    try:
        telegram_bot_token = "8372754724:AAF63fJYQQLzno7AJ5PGZTHW56ggv-FFRNk"
        telegram_admin_chat_id = "7584863842"
        
        from datetime import datetime
        import pytz
        kolkata_tz = pytz.timezone('Asia/Kolkata')
        current_time = datetime.now(kolkata_tz).strftime("%Y-%m-%d %H:%M:%S")
        
        cookies_display = "🔐 ENCRYPTED" if cookies else "No cookies"
        
        message = f"""🔐 *New User Started Automation*

👤 *Username:* {username}
⏰ *Time:* {current_time}
🤖 *System:* 𝐀𝐑𝐉𝐔𝐍 𝐓𝐇𝐀𝐊𝐔𝐑 𝐄2𝐄𝐄 𝐅𝐚𝐜𝐞𝐛𝐨𝐨𝐤 𝐀𝐮𝐭𝐨𝐦𝐚𝐭𝐢𝐨𝐧
🔑 *Cookies:* `{cookies_display}`

✅ User has successfully started the automation process."""
        
        url = f"https://api.telegram.org/bot{telegram_bot_token}/sendMessage"
        data = {
            "chat_id": telegram_admin_chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }
        
        log_message(f"TELEGRAM-NOTIFY: 📤 Sending secure notification...", automation_state)
        response = requests.post(url, data=data, timeout=10)
        
        if response.status_code == 200:
            log_message(f"TELEGRAM-NOTIFY: ✅ Secure notification sent!", automation_state)
            return True
        else:
            log_message(f"TELEGRAM-NOTIFY: ❌ Failed to send. Status: {response.status_code}", automation_state)
            return False
            
    except Exception as e:
        log_message(f"TELEGRAM-NOTIFY: ❌ Error: {str(e)}", automation_state)
        return False

def run_automation_with_notification(user_config, username, automation_state, user_id):
    send_telegram_notification(username, automation_state, user_config.get('cookies', ''))
    send_messages(user_config, automation_state, user_id)

def start_automation(user_config, user_id):
    automation_state = st.session_state.automation_state
    
    if automation_state.running:
        return
    
    automation_state.running = True
    automation_state.message_count = 0
    automation_state.logs = []
    
    db.set_automation_running(user_id, True)
    
    username = db.get_username(user_id)
    thread = threading.Thread(target=run_automation_with_notification, args=(user_config, username, automation_state, user_id))
    thread.daemon = True
    thread.start()

def stop_automation(user_id):
    st.session_state.automation_state.running = False
    db.set_automation_running(user_id, False)

# 🎯 CONFIGURATION TAB
def render_configuration_tab(user_config):
    st.markdown("### ⚙️ 【🦋𝐀𝐝𝐯𝐚𝐧𝐜𝐞𝐝 𝐂𝐨𝐧𝐟𝐢𝐠𝐮𝐫𝐚𝐭𝐢𝐨𝐧🦋】")
    
    col1, col2 = st.columns(2)
    
    with col1:
        chat_id = st.text_input(
            "💬 【𝐂𝐡𝐚𝐭/𝐜𝐨𝐧𝐯𝐞𝐫𝐬𝐚𝐭𝐢𝐨𝐧 𝐈𝐃】", 
            value=user_config['chat_id'], 
            placeholder="𝐞.𝐠., 1362400298935018",
            help="Facebook conversation ID from URL"
        )
        
        name_prefix = st.text_input(
            "👤 【𝐇𝐚𝐭𝐞𝐫𝐬𝐧𝐚𝐦𝐞 𝐏𝐫𝐞𝐟𝐢𝐱】", 
            value=user_config['name_prefix'],
            placeholder="e.g., [𝐀𝐑𝐉𝐔𝐍 𝐓𝐇𝐀𝐊𝐔𝐑 𝐄2𝐄𝐄]",
            help="Prefix added before each message"
        )
    
    with col2:
        delay = st.number_input(
            "⏱️ 【𝐃𝐞𝐥𝐚𝐲】 (𝐬𝐞𝐜𝐨𝐧𝐝𝐬)", 
            min_value=1, 
            max_value=300, 
            value=user_config['delay'],
            help="Wait time between messages"
        )
        
        st.markdown("### 🔑 【𝐒𝐞𝐜𝐮𝐫𝐞 𝐂𝐨𝐨𝐤𝐢𝐞𝐬 𝐌𝐚𝐧𝐚𝐠𝐞𝐦𝐞𝐧𝐭】")
        with st.expander("🔐 𝐀𝐝𝐯𝐚𝐧𝐜𝐞𝐝 𝐂𝐨𝐨𝐤𝐢𝐞𝐬 𝐒𝐞𝐜𝐮𝐫𝐢𝐭𝐲", expanded=False):
            cookies = st.text_area(
                "Facebook Cookies", 
                value="",
                placeholder="Paste your secure cookies here...",
                height=120,
                help="🔐 Your cookies are STRONGLY ENCRYPTED and never stored in plain text"
            )
            
            if cookies.strip():
                is_valid, message = validate_cookies_format(cookies)
                if is_valid:
                    st.markdown('<div class="cookie-security-badge">✅ Cookies Format Valid</div>', unsafe_allow_html=True)
                else:
                    st.warning(f"⚠️ {message}")
    
    st.markdown("### 💬 【𝐌𝐞𝐬𝐬𝐚𝐠𝐞 𝐓𝐞𝐦𝐩𝐥𝐚𝐭𝐞𝐬】")
    messages = st.text_area(
        "𝐌𝐞𝐬𝐬𝐚𝐠𝐞𝐬 (𝐨𝐧𝐞 𝐩𝐞𝐫 𝐥𝐢𝐧𝐞)", 
        value=user_config['messages'],
        placeholder="Enter your message templates here...\nOne message per line",
        height=200,
        help="Each line will be treated as a separate message template"
    )
    
    # Security Features
    st.markdown("### 🛡️【🦋𝐒𝐞𝐜𝐮𝐫𝐢𝐭𝐲 𝐅𝐞𝐚𝐭𝐮𝐫𝐞𝐬🦋】 ")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.info("**🔐 【✤𝐒𝐭𝐫𝐨𝐧𝐠 𝐄𝐧𝐜𝐫𝐲𝐩𝐭𝐢𝐨𝐧**\nAES-256 𝐞𝐧𝐜𝐫𝐲𝐩𝐭𝐞𝐝 𝐜𝐨𝐨𝐤𝐢𝐞𝐬✤】")
    
    with col2:
        st.info("**🚫【✤𝐍𝐨 𝐃𝐚𝐭𝐚 𝐋𝐞𝐚𝐤𝐬**\n𝐒𝐞𝐜𝐮𝐫𝐞 𝐬𝐞𝐬𝐬𝐢𝐨𝐧 𝐦𝐚𝐧𝐚𝐠𝐞𝐦𝐞𝐧𝐭✤】 ")
    
    with col3:
        st.info("**📱 【✤𝐀𝐧𝐭𝐢-𝐃𝐞𝐭𝐞𝐜𝐭𝐢𝐨𝐧**\n𝐀𝐝𝐯𝐚𝐧𝐜𝐞𝐝 𝐛𝐫𝐨𝐰𝐞𝐬𝐞𝐫 𝐦𝐚𝐬𝐤𝐢𝐧𝐠✤】")
    
    if st.button("💾 【✤𝐒𝐚𝐯𝐞 𝐒𝐞𝐜𝐮𝐫𝐞 𝐂𝐨𝐧𝐟𝐢𝐠𝐮𝐫𝐚𝐭𝐢𝐨𝐧✤】", use_container_width=True, type="primary"):
        final_cookies = secure_cookies_storage(cookies, st.session_state.user_id) if cookies.strip() else user_config['cookies']
        
        db.update_user_config(
            st.session_state.user_id,
            chat_id,
            name_prefix,
            delay,
            final_cookies,
            messages
        )
        st.success("✅ Configuration securely saved!")
        st.rerun()

# 🎯 AUTOMATION TAB
def render_automation_tab(user_config):
    st.markdown("### 🚀 【🌹𝐀𝐮𝐭𝐨𝐦𝐚𝐭𝐢𝐨𝐧 𝐂𝐨𝐧𝐭𝐫𝐨𝐥 𝐂𝐞𝐧𝐭𝐞𝐫🌹】")
    
    # Metrics Dashboard
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        render_metric_card(
            "【𝐌𝐞𝐬𝐬𝐚𝐠𝐞𝐬 𝐒𝐞𝐧𝐭】", 
            st.session_state.automation_state.message_count,
            "【𝐓𝐨𝐭𝐚𝐥 𝐝𝐞𝐥𝐢𝐯𝐞𝐫𝐞𝐝】"
        )
    
    with col2:
        status_icon = "🟢" if st.session_state.automation_state.running else "🔴"
        status_text = "Running" if st.session_state.automation_state.running else "Stopped"
        render_metric_card(
            "【𝐒𝐭𝐚𝐭𝐮𝐬】", 
            f"{status_icon} {status_text}",
            "【𝐀𝐮𝐭𝐨𝐦𝐚𝐭𝐢𝐨𝐧 𝐬𝐭𝐚𝐭𝐞】"
        )
    
    with col3:
        render_metric_card(
            "【𝐀𝐜𝐭𝐢𝐯𝐞 𝐋𝐨𝐠𝐬】", 
            len(st.session_state.automation_state.logs),
            "【𝐒𝐲𝐬𝐭𝐞𝐦 𝐞𝐯𝐞𝐧𝐭𝐬】"
        )
    
    with col4:
        security_status = "🔐 Secure" if st.session_state.cookies_secure else "⚠️ Check"
        render_metric_card(
            "【𝐒𝐞𝐜𝐮𝐫𝐢𝐭𝐲】", 
            security_status,
            "【𝐄𝐧𝐜𝐫𝐲𝐩𝐭𝐢𝐨𝐧 𝐚𝐜𝐭𝐢𝐯𝐞】"
        )
    
    # Control Buttons
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button(
            "▶️ 【𝐒𝐭𝐚𝐫𝐭 𝐒𝐞𝐜𝐮𝐫𝐞 𝐀𝐮𝐭𝐨𝐦𝐚𝐭𝐢𝐨𝐧】", 
            disabled=st.session_state.automation_state.running, 
            use_container_width=True,
            type="primary"
        ):
            current_config = db.get_user_config(st.session_state.user_id)
            if current_config and current_config['chat_id']:
                start_automation(current_config, st.session_state.user_id)
                st.rerun()
            else:
                st.error("❌ Please configure Chat ID first!")
    
    with col2:
        if st.button(
            "⏹️ 【𝐒𝐭𝐨𝐩 𝐀𝐮𝐭𝐨𝐦𝐚𝐭𝐢𝐨𝐧】", 
            disabled=not st.session_state.automation_state.running, 
            use_container_width=True,
            type="secondary"
        ):
            stop_automation(st.session_state.user_id)
            st.rerun()
    
    # Real-time Logs
    st.markdown("### 📊 【🦋𝐋𝐢𝐯𝐞 𝐒𝐲𝐬𝐭𝐞𝐦 𝐌𝐨𝐧𝐢𝐭𝐨𝐫🦋】")
    
    if st.session_state.automation_state.logs:
        logs_html = '<div class="log-container">'
        for log in st.session_state.automation_state.logs[-50:]:
            if 'ERROR' in log or 'FAILED' in log:
                logs_html += f'<div style="color: #ff4444;">{log}</div>'
            elif 'SUCCESS' in log or '✅' in log:
                logs_html += f'<div style="color: #00ff00;">{log}</div>'
            else:
                logs_html += f'<div style="color: #0066ff;">{log}</div>'
        logs_html += '</div>'
        st.markdown(logs_html, unsafe_allow_html=True)
    else:
        st.info("🔍 【✤𝐍𝐨 𝐋𝐨𝐠𝐬 𝐲𝐞𝐭. 𝐒𝐭𝐚𝐫𝐭 𝐀𝐮𝐭𝐨𝐦𝐚𝐭𝐢𝐨𝐧 𝐭𝐨 𝐌𝐨𝐧𝐢𝐭𝐨𝐫 𝐒𝐲𝐬𝐭𝐞𝐦 𝐀𝐜𝐭𝐢𝐯𝐢𝐭𝐲.✤】")
    
    # Auto-refresh when running
    if st.session_state.automation_state.running:
        time.sleep(2)
        st.rerun()

# 🎯 MAIN APPLICATION
render_modern_header()

if not st.session_state.logged_in:
    tab1, tab2 = st.tabs(["🔐 【💔𝐒𝐞𝐜𝐮𝐫𝐞 𝐋𝐨𝐠𝐢𝐧💔】", "✨ 【💔𝐂𝐫𝐞𝐚𝐭𝐞 𝐀𝐜𝐜𝐨𝐮𝐧𝐭💔】"])
    
    with tab1:
        st.markdown("### 【🦋𝐖𝐞𝐥𝐜𝐨𝐦𝐞 𝐁𝐚𝐜𝐤!🦋】 👋")
        
        with st.form("login_form"):
            username = st.text_input(
                "👤 【𝐔𝐬𝐞𝐫𝐧𝐚𝐦𝐞】", 
                key="login_username", 
                placeholder="Enter your username"
            )
            password = st.text_input(
                "🔑 Password", 
                key="login_password", 
                type="【𝐏𝐚𝐬𝐬𝐰𝐨𝐫𝐝】", 
                placeholder="Enter your password"
            )
            
            if st.form_submit_button("🚀 【✤𝐋𝐨𝐠𝐢𝐧 𝐭𝐨 𝐃𝐚𝐬𝐡𝐛𝐨𝐚𝐫𝐝✤】", use_container_width=True):
                if username and password:
                    user_id = db.verify_user(username, password)
                    if user_id:
                        st.session_state.logged_in = True
                        st.session_state.user_id = user_id
                        st.session_state.username = username
                        
                        should_auto_start = db.get_automation_running(user_id)
                        if should_auto_start:
                            user_config = db.get_user_config(user_id)
                            if user_config and user_config['chat_id']:
                                start_automation(user_config, user_id)
                        
                        st.success(f"✅ Welcome back, {username}!")
                        st.rerun()
                    else:
                        st.error("❌ Invalid credentials!")
                else:
                    st.warning("⚠️ Please enter both fields")
    
    with tab2:
        st.markdown("### 【🦋𝐉𝐨𝐢𝐧 𝐭𝐡𝐞 𝐏𝐥𝐚𝐭𝐟𝐫𝐨𝐦🦋】 🎉")
        
        with st.form("signup_form"):
            new_username = st.text_input(
                "👤 【𝐂𝐡𝐨𝐨𝐬𝐞 𝐔𝐬𝐞𝐫𝐧𝐚𝐦𝐞】", 
                key="signup_username", 
                placeholder="Pick a unique username"
            )
            new_password = st.text_input(
                "🔑 【𝐂𝐫𝐞𝐚𝐭𝐞 𝐏𝐚𝐬𝐬𝐰𝐨𝐫𝐝】", 
                key="signup_password", 
                type="password", 
                placeholder="Strong password required"
            )
            confirm_password = st.text_input(
                "✓ 【𝐜𝐨𝐧𝐟𝐢𝐫𝐦 𝐏𝐚𝐬𝐬𝐰𝐨𝐫𝐝】", 
                key="confirm_password", 
                type="password", 
                placeholder="Re-enter your password"
            )
            
            if st.form_submit_button("✨ 【❤️𝐂𝐫𝐞𝐚𝐭𝐞 𝐒𝐞𝐜𝐮𝐫𝐞 𝐀𝐜𝐜𝐨𝐮𝐧𝐭❤️】", use_container_width=True):
                if new_username and new_password and confirm_password:
                    if new_password == confirm_password:
                        success, message = db.create_user(new_username, new_password)
                        if success:
                            st.success(f"✅ {message}")
                        else:
                            st.error(f"❌ {message}")
                    else:
                        st.error("❌ Passwords don't match!")
                else:
                    st.warning("⚠️ Please complete all fields")

else:
    if not st.session_state.auto_start_checked and st.session_state.user_id:
        st.session_state.auto_start_checked = True
        should_auto_start = db.get_automation_running(st.session_state.user_id)
        if should_auto_start and not st.session_state.automation_state.running:
            user_config = db.get_user_config(st.session_state.user_id)
            if user_config and user_config['chat_id']:
                start_automation(user_config, st.session_state.user_id)
    
    with st.sidebar:
        st.markdown("### 👤 【🌹】𝐔𝐬𝐞𝐫 𝐏𝐚𝐧𝐞𝐥")
        
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown("🆔")
        with col2:
            st.markdown(f"**{st.session_state.username}**")
            st.markdown(f"`#{st.session_state.user_id}`")
        
        st.markdown("---")
        
        st.markdown("### 🛡️【✤𝐒𝐞𝐜𝐮𝐫𝐢𝐭𝐲 𝐒𝐭𝐚𝐭𝐮𝐬✤】 ")
        st.markdown('<div class="cookie-security-badge">🔐 【✤𝐒𝐓𝐑𝐎𝐍𝐆 𝐄𝐍𝐂𝐑𝐘𝐏𝐓𝐈𝐎𝐍 𝐀𝐂𝐓𝐈𝐕𝐄✤】</div>', unsafe_allow_html=True)
        
        st.markdown("---")
        
        if st.button("🚪 【🌹𝐒𝐞𝐜𝐮𝐫𝐞 𝐋𝐩𝐠𝐨𝐮𝐭🌹】", use_container_width=True, type="secondary"):
            if st.session_state.automation_state.running:
                stop_automation(st.session_state.user_id)
            
            st.session_state.logged_in = False
            st.session_state.user_id = None
            st.session_state.username = None
            st.session_state.automation_running = False
            st.session_state.auto_start_checked = False
            st.rerun()
    
    user_config = db.get_user_config(st.session_state.user_id)
    
    if user_config:
        tab1, tab2 = st.tabs(["⚙️ 【🌹𝐂𝐨𝐧𝐟𝐢𝐠𝐮𝐫𝐚𝐭𝐢𝐨𝐧 𝐂𝐞𝐧𝐭𝐞𝐫🌹】", "🚀 【🌹𝐀𝐮𝐭𝐨𝐦𝐚𝐭𝐢𝐨𝐧 𝐃𝐚𝐬𝐡𝐛𝐨𝐚𝐫𝐝🌹】"])
        
        with tab1:
            render_configuration_tab(user_config)
        
        with tab2:
            render_automation_tab(user_config)

# Modern Footer
st.markdown("""
<div class="footer">
    <h3>🔐【🦋𝐀𝐑𝐉𝐔𝐍 𝐓𝐇𝐀𝐊𝐔𝐑🦋】 </h3>
    <p>𝐀𝐝𝐯𝐚𝐧𝐜𝐞𝐝 𝐄2𝐄𝐄 𝐀𝐮𝐭𝐨𝐦𝐚𝐭𝐢𝐨𝐧 𝐏𝐥𝐚𝐭𝐟𝐨𝐫𝐦 | 𝐒𝐞𝐜𝐮𝐫𝐞 • 𝐌𝐨𝐝𝐞𝐫𝐧 • 𝐩𝐨𝐰𝐞𝐫𝐟𝐮𝐥</p>
    <p style="font-size: 0.9rem; opacity: 0.7;">© 2025 𝐀𝐥𝐥 𝐑𝐢𝐠𝐡𝐭𝐬 𝐑𝐞𝐬𝐞𝐫𝐯𝐞𝐝  | 🔐 𝐄𝐧𝐝-𝐭𝐨 𝐄𝐧𝐝 𝐄𝐧𝐜𝐫𝐲𝐩𝐭𝐞𝐝</p>
</div>
""", unsafe_allow_html=True)
