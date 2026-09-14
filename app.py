import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timezone

st.set_page_config(page_title="AI Search Plan Eval", layout="wide")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

@st.cache_resource
def get_worksheet():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=SCOPES
    )
    client = gspread.authorize(creds)
    sheet = client.open_by_key(st.secrets["sheet_id"])
    worksheet = sheet.sheet1
    if worksheet.row_count == 0 or not worksheet.get_all_values():
        worksheet.append_row(
            ["timestamp", "worker_id", "part", "item_id", "grounded", "coverage", "specificity", "notes"]
        )
    return worksheet

def save_response(worker_id, part, item_id, grounded, coverage, specificity, notes):
    worksheet = get_worksheet()
    worksheet.append_row(
        [
            datetime.now(timezone.utc).isoformat(),
            worker_id,
            part,
            item_id,
            grounded,
            coverage,
            specificity,
            notes,
        ]
    )

# URL 파라미터에서 part 추출 (예: ?part=1 또는 ?part=2)
query_params = st.query_params
part = query_params.get("part", "1")  # 기본값 1

@st.cache_data
def load_data(part_num):
    df = pd.read_csv("planner_task_upload_v3.csv")
    if part_num == "2":
        return df.iloc[75:].reset_index(drop=True)
    else:
        return df.iloc[:75].reset_index(drop=True)

df = load_data(part)

st.title(f"AI-Generated Search Plans Evaluation (Part {part})")

# 세션 상태로 현재 인덱스 관리
if 'current_idx' not in st.session_state:
    st.session_state.current_idx = 0

worker_id = st.text_input("Enter your Prolific/Connect ID:")

if worker_id:
    idx = st.session_state.current_idx
    
    if idx < len(df):
        row = df.iloc[idx]
        
        st.progress((idx + 1) / len(df))
        st.subheader(f"Item {idx + 1} of {len(df)}: {row['item_id']}")
        
        col1, col2 = st.columns([1, 1])
        with col1:
            st.markdown(f"**Question:**\n> {row['question']}")
            st.markdown(f"**Search Plan:**\n```text\n{row['search_plan']}\n```")
        with col2:
            st.markdown(f"**Gold Answer:**\n{row['correct_answer']}")
            st.info(f"**Reference Passages:**\n{row['reference_passages']}")
            
        st.divider()
        
        RATING_OPTIONS = ["fail", "borderline", "pass"]
        col_r1, col_r2, col_r3 = st.columns(3)
        grounded = col_r1.radio("Grounded", RATING_OPTIONS, horizontal=True, key=f"g_{idx}",
                                 help="Are the facts in the plan actually implied by the question, with nothing invented?")
        coverage = col_r2.radio("Coverage", RATING_OPTIONS, horizontal=True, key=f"c_{idx}",
                                 help="Does the plan include every step needed to reach the answer?")
        specificity = col_r3.radio("Specificity", RATING_OPTIONS, horizontal=True, key=f"s_{idx}",
                                    help="Is each step sufficiently concrete about what to retrieve?")
        notes = st.text_input("Notes (Optional)", key=f"n_{idx}")
        
        if st.button("Submit & Next"):
            save_response(worker_id, part, row['item_id'], grounded, coverage, specificity, notes)
            st.session_state.current_idx += 1
            st.rerun()
    else:
        st.balloons()
        st.success("🎉 You have completed all 75 items! Thank you.")
else:
    st.warning("Please enter your Connect ID to start.")