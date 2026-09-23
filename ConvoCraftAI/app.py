import streamlit as st
import sqlite3
import pandas as pd
import json
import tempfile
import os
import hashlib
from datetime import datetime, timedelta
import ai_services  # Your Groq AI service module
import extra_streamlit_components as stx

# ==========================================
# 1. PAGE CONFIGURATION (Must be first)
# ==========================================
st.set_page_config(
    page_title="ConvoCraft AI – AI Meeting Assistant",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# 2. DATABASE & HELPER FUNCTIONS
# ==========================================
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def init_db():
    conn = sqlite3.connect("convocraft.db")
    cursor = conn.cursor()
    
    # Users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT DEFAULT 'CSE AIML Student',
        default_language TEXT DEFAULT 'English',
        default_summary_format TEXT DEFAULT 'Detailed',
        default_tone TEXT DEFAULT 'Technical'
    )
    """)
    
    # Meetings table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS meetings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        date TEXT NOT NULL,
        language TEXT NOT NULL,
        summary TEXT NOT NULL,
        decisions TEXT NOT NULL,
        agenda TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    """)
    
    # Action Items table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS action_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        meeting_id INTEGER,
        task TEXT NOT NULL,
        assignee TEXT NOT NULL,
        deadline TEXT NOT NULL,
        priority TEXT NOT NULL,
        status TEXT DEFAULT 'Pending',
        FOREIGN KEY (user_id) REFERENCES users (id),
        FOREIGN KEY (meeting_id) REFERENCES meetings (id)
    )
    """)
    
    conn.commit()
    conn.close()

init_db()

def create_user(name, email, password):
    conn = sqlite3.connect("convocraft.db")
    cursor = conn.cursor()
    try:
        hashed_pwd = hash_password(password)
        cursor.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, hashed_pwd)
        )
        conn.commit()
        return True, "Account created successfully! Please log in below."
    except sqlite3.IntegrityError:
        return False, "An account with this email already exists."
    finally:
        conn.close()

def authenticate_user(email, password):
    conn = sqlite3.connect("convocraft.db")
    cursor = conn.cursor()
    hashed_pwd = hash_password(password)
    cursor.execute(
        "SELECT id, name, email, role, default_language, default_summary_format, default_tone FROM users WHERE email = ? AND password_hash = ?",
        (email, hashed_pwd)
    )
    user = cursor.fetchone()
    conn.close()
    if user:
        return {
            "id": user[0],
            "name": user[1],
            "email": user[2],
            "role": user[3],
            "default_language": user[4],
            "default_summary_format": user[5],
            "default_tone": user[6]
        }
    return None

def update_user_profile(user_id, name, email, role, lang, summary_fmt, tone):
    conn = sqlite3.connect("convocraft.db")
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE users 
    SET name=?, email=?, role=?, default_language=?, default_summary_format=?, default_tone=?
    WHERE id = ?
    """, (name, email, role, lang, summary_fmt, tone, user_id))
    conn.commit()
    conn.close()

def save_meeting_data(user_id, title, language, summary, decisions_list, action_items_list, agenda_list):
    conn = sqlite3.connect("convocraft.db")
    cursor = conn.cursor()
    today_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    summary_str = json.dumps(summary) if isinstance(summary, (dict, list)) else str(summary)
    decisions_str = json.dumps(decisions_list) if isinstance(decisions_list, list) else str(decisions_list)
    agenda_str = json.dumps(agenda_list) if isinstance(agenda_list, list) else str(agenda_list)
    
    cursor.execute("""
    INSERT INTO meetings (user_id, title, date, language, summary, decisions, agenda)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_id, title, today_str, language, summary_str, decisions_str, agenda_str))
    
    meeting_id = cursor.lastrowid
    
    if isinstance(action_items_list, list):
        for item in action_items_list:
            if isinstance(item, dict):
                cursor.execute("""
                INSERT INTO action_items (user_id, meeting_id, task, assignee, deadline, priority, status)
                VALUES (?, ?, ?, ?, ?, ?, 'Pending')
                """, (
                    user_id,
                    meeting_id, 
                    str(item.get('task', 'N/A')), 
                    str(item.get('assignee', 'Unassigned')), 
                    str(item.get('deadline', 'Not specified')), 
                    str(item.get('priority', 'Medium'))
                ))
        
    conn.commit()
    conn.close()
    return meeting_id

def delete_user_meeting(user_id, meeting_id):
    conn = sqlite3.connect("convocraft.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM action_items WHERE user_id = ? AND meeting_id = ?", (user_id, meeting_id))
    cursor.execute("DELETE FROM meetings WHERE user_id = ? AND id = ?", (user_id, meeting_id))
    conn.commit()
    conn.close()

def clear_all_user_history(user_id):
    conn = sqlite3.connect("convocraft.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM action_items WHERE user_id = ?", (user_id,))
    cursor.execute("DELETE FROM meetings WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def toggle_task_status(task_id, current_status):
    new_status = 'Completed' if current_status == 'Pending' else 'Pending'
    conn = sqlite3.connect("convocraft.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE action_items SET status = ? WHERE id = ?", (new_status, task_id))
    conn.commit()
    conn.close()

# Initialize Cookie Manager
cookie_manager = stx.CookieManager()

# Get existing session cookie
session_user_email = cookie_manager.get(cookie="convocraft_user")

# Restore Session from Cookie if state is empty
if st.session_state.get("user") is None and session_user_email:
    conn = sqlite3.connect("convocraft.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, email, role, default_language, default_summary_format, default_tone FROM users WHERE email = ?",
        (session_user_email,)
    )
    user = cursor.fetchone()
    conn.close()
    if user:
        st.session_state["user"] = {
            "id": user[0],
            "name": user[1],
            "email": user[2],
            "role": user[3],
            "default_language": user[4],
            "default_summary_format": user[5],
            "default_tone": user[6]
        }
        st.rerun()

# ==========================================
# 3. SIDEBAR THEME TOGGLE (Rendered for everyone)
# ==========================================
st.sidebar.title("🎙️ ConvoCraft AI")
st.sidebar.caption("AI-Powered Meeting Assistant")

theme_mode = st.sidebar.radio("🎨 UI Theme Mode", ["Light (Ivory & Lavender)", "Dark (Obsidian & Blue)"], index=0)
is_dark = "Dark" in theme_mode

if not is_dark:
    css_vars = """
    :root {
        --bg-main: #FFFDF9;
        --bg-card: #F3F0FF;
        --bg-sidebar: #E0E7FF;
        --border-color: #C7D2FE;
        --text-primary: #1E1B4B;
        --text-secondary: #4338CA;
        --accent-gradient: linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%);
        --metric-val: #2563EB;
        --shadow: 0 4px 15px rgba(99, 102, 241, 0.12);
    }
    """
else:
    css_vars = """
    :root {
        --bg-main: #0F172A;
        --bg-card: #1E1B4B;
        --bg-sidebar: #1E293B;
        --border-color: #3730A3;
        --text-primary: #F8FAFC;
        --text-secondary: #C7D2FE;
        --accent-gradient: linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%);
        --metric-val: #818CF8;
        --shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
    }
    """

theme_css = f"""
<style>
    {css_vars}

    .stApp {{
        background-color: var(--bg-main) !important;
        color: var(--text-primary) !important;
        font-family: 'Inter', sans-serif;
    }}

    section[data-testid="stSidebar"] {{
        background-color: var(--bg-sidebar) !important;
        border-right: 1px solid var(--border-color);
    }}

    h1, h2, h3, h4, label, .stMarkdown {{
        color: var(--text-primary) !important;
    }}

    div[data-testid="stMetric"] {{
        background-color: var(--bg-card) !important;
        border: 1.5px solid var(--border-color) !important;
        border-radius: 14px !important;
        padding: 18px !important;
        box-shadow: var(--shadow) !important;
        transition: transform 0.2s ease;
    }}
    div[data-testid="stMetric"]:hover {{
        transform: translateY(-3px);
    }}
    div[data-testid="stMetricValue"] {{
        color: var(--metric-val) !important;
        font-weight: 800 !important;
    }}
    div[data-testid="stMetricLabel"] {{
        color: var(--text-secondary) !important;
        font-weight: 600 !important;
    }}

    div.stButton > button[kind="primary"] {{
        background: var(--accent-gradient) !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        padding: 0.65rem 1.4rem !important;
        box-shadow: 0 4px 14px rgba(79, 70, 229, 0.35) !important;
        transition: all 0.3s ease !important;
    }}
    div.stButton > button[kind="primary"]:hover {{
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(124, 58, 237, 0.5) !important;
    }}

    div[data-testid="stExpander"] {{
        background-color: var(--bg-card) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 12px !important;
    }}
</style>
"""
st.markdown(theme_css, unsafe_allow_html=True)

# ==========================================
# 4. AUTHENTICATION SCREEN (UNAUTHENTICATED)
# ==========================================
if st.session_state.get("user") is None:
    st.title("🎙️ Welcome to ConvoCraft AI")
    st.caption("AI-Powered Meeting Assistant & Workspace Management")
    st.markdown("---")
    auth_tab1, auth_tab2 = st.tabs(["🔐 Log In", "📝 Sign Up"])
    
    with auth_tab1:
        st.subheader("Sign in to your account")
        login_email = st.text_input("Email Address", key="login_email")
        login_password = st.text_input("Password", type="password", key="login_pwd")
        
        if st.button("Log In", type="primary", use_container_width=True):
            if login_email and login_password:
                user_data = authenticate_user(login_email, login_password)
                if user_data:
                    st.session_state["user"] = user_data
                    expiry_date = datetime.now() + timedelta(days=30)
                    cookie_manager.set("convocraft_user", user_data["email"], key="set_user_cookie", expires_at=expiry_date)
                    st.success(f"Welcome back, {user_data['name']}!")
                    st.rerun()
                else:
                    st.error("Invalid email or password.")
            else:
                st.warning("Please enter your email and password.")
                
    with auth_tab2:
        st.subheader("Create a free account")
        signup_name = st.text_input("Full Name", key="signup_name")
        signup_email = st.text_input("Email Address", key="signup_email")
        signup_password = st.text_input("Password", type="password", key="signup_pwd")
        
        if st.button("Sign Up", type="primary", use_container_width=True):
            if signup_name and signup_email and signup_password:
                success, msg = create_user(signup_name, signup_email, signup_password)
                if success:
                    st.success(msg)
                else:
                    st.error(msg)
            else:
                st.warning("Please fill in all fields to register.")

    # Halt execution here until user logs in
    st.stop()

# ==========================================
# 5. LOGGED-IN NAVIGATION & SIDEBAR
# ==========================================
current_user = st.session_state["user"]

st.sidebar.markdown("---")
st.sidebar.write("**Logged-in Account:**")
st.sidebar.info(f"👤 **{current_user['name']}**\n\n✉️ *{current_user['email']}*\n\n🎓 *{current_user['role']}*")

if st.sidebar.button("🚪 Log Out", use_container_width=True):
    cookie_manager.delete("convocraft_user")
    st.session_state["user"] = None
    st.rerun()

nav_choice = st.sidebar.radio(
    "Navigation", 
    ["📊 Dashboard", "🎤 Upload & Process", "📋 Task Tracker", "👤 Profile & Preferences"]
)

# ==========================================
# TAB 1: DASHBOARD
# ==========================================
if nav_choice == "📊 Dashboard":
    st.title("📊 Meeting Analytics & Workspace Dashboard")
    st.write("Overview of all past meeting insights, task metrics, and search.")

    conn = sqlite3.connect("convocraft.db")
    meetings_df = pd.read_sql_query("SELECT * FROM meetings WHERE user_id = ? ORDER BY id DESC", conn, params=(current_user['id'],))
    tasks_df = pd.read_sql_query("SELECT * FROM action_items WHERE user_id = ?", conn, params=(current_user['id'],))
    conn.close()

    total_meetings = len(meetings_df)
    pending_tasks = len(tasks_df[tasks_df['status'] == 'Pending']) if not tasks_df.empty else 0
    completed_tasks = len(tasks_df[tasks_df['status'] == 'Completed']) if not tasks_df.empty else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Meetings", total_meetings)
    col2.metric("Pending Tasks", pending_tasks)
    col3.metric("Completed Tasks", completed_tasks)
    col4.metric("Completion Rate", f"{int((completed_tasks / len(tasks_df)) * 100)}%" if not tasks_df.empty and len(tasks_df) > 0 else "0%")

    st.markdown("---")

    search_query = st.text_input("🔍 Search past meetings (Keywords, Titles, or Tasks)", "")
    if not meetings_df.empty:
        col_hist_head, col_hist_clear = st.columns([3, 1])
        with col_hist_head:
            st.subheader("📚 Meeting History")
        with col_hist_clear:
            if st.button("🗑️ Clear All History", type="secondary", use_container_width=True):
                clear_all_user_history(current_user['id'])
                st.success("All meeting history cleared!")
                st.rerun()

        if search_query:
            filtered_meetings = meetings_df[meetings_df['title'].str.contains(search_query, case=False, na=False) | 
                                            meetings_df['summary'].str.contains(search_query, case=False, na=False)]
        else:
            filtered_meetings = meetings_df

        for idx, row in filtered_meetings.iterrows():
            with st.expander(f"📌 {row['title']} — {row['date']} ({row['language']})"):
                st.write("**Summary:**")
                st.write(row['summary'])
                
                col_a, col_b = st.columns(2)
                with col_a:
                    st.write("**Key Decisions:**")
                    try:
                        decisions = json.loads(row['decisions'])
                        for d in decisions:
                            st.write(f"- {d}")
                    except Exception:
                        st.write(row['decisions'])
                with col_b:
                    st.write("**Suggested Next Agenda:**")
                    try:
                        agenda = json.loads(row['agenda'])
                        for a in agenda:
                            st.write(f"- {a}")
                    except Exception:
                        st.write(row['agenda'])

                # Ask AI Chatbot
                st.markdown("---")
                st.subheader("💬 Ask AI About This Meeting")
                chat_key = f"chat_input_{row['id']}"
                user_query = st.text_input(f"Ask anything about '{row['title']}'...", key=chat_key, placeholder="e.g., What deadline was assigned?")
                
                if user_query:
                    with st.spinner("ConvoCraft AI is thinking..."):
                        meeting_context = f"Title: {row['title']}\nSummary: {row['summary']}\nDecisions: {row['decisions']}"
                        ai_answer = ai_services.chat_with_meeting(meeting_context, user_query)
                        st.markdown("**🤖 AI Response:**")
                        st.info(ai_answer)

                st.markdown("---")
                if st.button(f"🗑️ Delete Meeting #{row['id']}", key=f"del_m_{row['id']}"):
                    delete_user_meeting(current_user['id'], row['id'])
                    st.success("Meeting deleted!")
                    st.rerun()
    else:
        st.info("No meetings uploaded yet. Head over to the **Upload & Process** tab to upload your first recording!")

# ==========================================
# TAB 2: UPLOAD & PROCESS
# ==========================================
elif nav_choice == "🎤 Upload & Process":
    st.title("🎤 Meeting Audio Upload & AI Analysis")
    st.write("Upload raw meeting audio and generate structured summaries, action items, and agendas using Groq AI.")

    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.subheader("1. Audio File")
        uploaded_file = st.file_uploader("Upload recorded meeting audio", type=["mp3", "wav"])
        meeting_title = st.text_input("Meeting Title", value="Project Sync & Architecture Discussion")

    with col_right:
        st.subheader("2. AI Customization Preferences")
        selected_lang = st.selectbox("Target Output Language", ["English", "Telugu", "Hindi"], 
                                     index=["English", "Telugu", "Hindi"].index(current_user.get('default_language', 'English')))
        summary_format = st.selectbox("Summary Format", ["Brief", "Detailed", "Bullet Points"], 
                                      index=["Brief", "Detailed", "Bullet Points"].index(current_user.get('default_summary_format', 'Detailed')))
        selected_tone = st.selectbox("Persona / Tone", ["Executive", "Technical", "Casual"], 
                                     index=["Executive", "Technical", "Casual"].index(current_user.get('default_tone', 'Technical')))
        custom_hint = st.text_area("Custom Guidance / Focus Area (Optional)", placeholder="e.g., Focus heavily on database decisions and API deadlines.")

    if st.button("🚀 Process Audio with AI", type="primary", use_container_width=True):
        if uploaded_file is None:
            st.error("Please upload an MP3 or WAV file before processing.")
        else:
            with st.spinner("Processing audio with Groq Whisper & GPT-OSS 20B AI..."):
                file_extension = uploaded_file.name.split('.')[-1]
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_extension}") as tmp_file:
                    tmp_file.write(uploaded_file.getvalue())
                    tmp_audio_path = tmp_file.name

                try:
                    ai_output = ai_services.process_meeting_audio(
                        audio_file_path=tmp_audio_path,
                        language=selected_lang,
                        summary_format=summary_format,
                        tone=selected_tone,
                        custom_hint=custom_hint
                    )

                    # Check whether AI processing actually succeeded
                    if ai_output.get("success") is False:
                        st.error(
                            "AI processing failed. The meeting was NOT saved.\n\n"
                            f"Error: {ai_output.get('error', 'Unknown Groq error')}"
                        )
                        st.stop()

                    proc_summary = ai_output.get("summary", "")
                    proc_decisions = ai_output.get("key_decisions", [])
                    proc_action_items = ai_output.get("action_items", [])
                    proc_agenda = ai_output.get("next_agenda", [])

                    save_meeting_data(
                        current_user['id'],
                        meeting_title, 
                        selected_lang, 
                        proc_summary, 
                        proc_decisions, 
                        proc_action_items, 
                        proc_agenda
                    )                    
                    st.success("Meeting processed and saved successfully!")

                    st.markdown("---")
                    st.subheader("📝 Processed AI Output")
                    st.info(f"**Summary ({selected_lang}):**\n\n{proc_summary}")
                    
                    res_col1, res_col2 = st.columns(2)
                    with res_col1:
                        st.write("### 📌 Key Decisions")
                        for d in proc_decisions:
                            st.write(f"- {d}")
                    with res_col2:
                        st.write("### 📅 Next Meeting Agenda")
                        for a in proc_agenda:
                            st.write(f"- {a}")
                            
                    st.write("### ✅ Extracted Action Items")
                    if proc_action_items:
                        st.dataframe(pd.DataFrame(proc_action_items), use_container_width=True)

                    export_text = f"""# {meeting_title}
Date: {datetime.now().strftime("%Y-%m-%d")}
Language: {selected_lang}

## Summary
{proc_summary}

## Key Decisions
""" + "\n".join([f"- {d}" for d in proc_decisions]) + """

## Action Items
""" + "\n".join([f"- [{item.get('priority')}] {item.get('task')} (Assignee: {item.get('assignee')}, Deadline: {item.get('deadline')})" for item in proc_action_items]) + """

## Next Agenda
""" + "\n".join([f"- {a}" for a in proc_agenda])

                    st.download_button(
                        label="📥 Download Meeting Minutes (Markdown)",
                        data=export_text,
                        file_name=f"{meeting_title.replace(' ', '_')}_notes.md",
                        mime="text/markdown",
                        use_container_width=True
                    )

                finally:
                    if os.path.exists(tmp_audio_path):
                        os.remove(tmp_audio_path)

# ==========================================
# TAB 3: TASK TRACKER
# ==========================================
elif nav_choice == "📋 Task Tracker":
    st.title("📋 Action Item & Pending Task Tracker")
    st.write("Centralized task management across all historical meetings.")
    conn = sqlite3.connect("convocraft.db")
    tasks_df = pd.read_sql_query("SELECT * FROM action_items WHERE user_id = ?", conn, params=(current_user['id'],))
    conn.close()

    if not tasks_df.empty:
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            assignee_filter = st.selectbox("Filter by Assignee", ["All", "My Tasks Only"] + list(tasks_df['assignee'].unique()))
        with col_f2:
            status_filter = st.selectbox("Filter by Status", ["All", "Pending", "Completed"])

        filtered_df = tasks_df.copy()
        if assignee_filter == "My Tasks Only":
            filtered_df = filtered_df[filtered_df['assignee'].str.contains(current_user.get('name', ''), case=False, na=False)]
        elif assignee_filter != "All":
            filtered_df = filtered_df[filtered_df['assignee'] == assignee_filter]

        if status_filter != "All":
            filtered_df = filtered_df[filtered_df['status'] == status_filter]

        st.markdown("---")

        for idx, row in filtered_df.iterrows():
            c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 1, 1])
            
            status_icon = "✅" if row['status'] == "Completed" else "⏳"
            c1.write(f"{status_icon} **{row['task']}**")
            c2.write(f"👤 {row['assignee']}")
            c3.write(f"📅 Deadline: {row['deadline']}")
            
            p_color = "🔴" if row['priority'] == "High" else ("🟡" if row['priority'] == "Medium" else "🟢")
            c4.write(f"{p_color} {row['priority']}")
            
            btn_label = "Mark Pending" if row['status'] == "Completed" else "Mark Done"
            if c5.button(btn_label, key=f"task_{row['id']}"):
                toggle_task_status(row['id'], row['status'])
                st.rerun()
    else:
        st.info("No action items stored yet. Process a meeting recording to extract tasks automatically!")

# ==========================================
# TAB 4: PROFILE & PREFERENCES
# ==========================================
elif nav_choice == "👤 Profile & Preferences":
    st.title("👤 Profile & Default AI Preferences")
    st.write("Manage your personal workspace profile and default automation settings.")

    with st.form("profile_form"):
        st.subheader("Personal Details")
        prof_name = st.text_input("Full Name", value=current_user.get('name', ''))
        prof_email = st.text_input("Email Address", value=current_user.get('email', ''))
        prof_role = st.text_input("Job Role / Specialty", value=current_user.get('role', 'CSE AIML Student'))

        st.subheader("Default AI Processing Settings")
        def_lang = st.selectbox("Default Language Output", ["English", "Telugu", "Hindi"], 
                                index=["English", "Telugu", "Hindi"].index(current_user.get('default_language', 'English')))
        def_summary = st.selectbox("Default Summary Format", ["Brief", "Detailed", "Bullet Points"], 
                                   index=["Brief", "Detailed", "Bullet Points"].index(current_user.get('default_summary_format', 'Detailed')))
        def_tone = st.selectbox("Default Summary Tone", ["Executive", "Technical", "Casual"], 
                                index=["Executive", "Technical", "Casual"].index(current_user.get('default_tone', 'Technical')))

        save_btn = st.form_submit_button("Save Profile Settings", type="primary")

        if save_btn:
            update_user_profile(current_user['id'], prof_name, prof_email, prof_role, def_lang, def_summary, def_tone)
            # Update active session dict
            st.session_state["user"]["name"] = prof_name
            st.session_state["user"]["email"] = prof_email
            st.session_state["user"]["role"] = prof_role
            st.session_state["user"]["default_language"] = def_lang
            st.session_state["user"]["default_summary_format"] = def_summary
            st.session_state["user"]["default_tone"] = def_tone
            st.success("Profile updated successfully!")
            st.rerun()
