import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timezone

st.set_page_config(page_title="AI Search Plan Eval", layout="wide")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

CSV_BY_TASK = {"plan": "plan_task_v3.csv", "sufficiency": "sufficiency_task.csv"}
RATING_OPTIONS = ["fail", "borderline", "pass"]
SUFFICIENCY_OPTIONS = ["insufficient", "borderline", "sufficient"]


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
            ["timestamp", "worker_id", "task", "part", "item_id",
             "rating_1", "rating_2", "rating_3", "notes"]
        )
    return worksheet


def save_response(worker_id, task, part, item_id, r1, r2, r3, notes):
    worksheet = get_worksheet()
    worksheet.append_row(
        [datetime.now(timezone.utc).isoformat(), worker_id, task, part,
         item_id, r1, r2, r3, notes]
    )


query_params = st.query_params
task = query_params.get("task", "plan")
part = query_params.get("part", "1")

# 2026-09-14: plain disjoint split (no shared/overlap items) -- matches
# the HARIS paper's (arXiv:2506.07528) own human-validation design: two
# annotators each independently rate their own disjoint half (75/75 for
# 150 items there, same pattern here), and the reliability number reported
# (Cohen's kappa, agreement %) is HUMAN-vs-LLM-JUDGE agreement per item,
# not human-vs-human -- which needs no overlap at all, since every item
# already has both a human rating (from whichever annotator got it) and
# an LLM-judge verdict to compare against.
@st.cache_data
def load_data(task, part_num):
    df = pd.read_csv(CSV_BY_TASK[task])
    half = len(df) // 2
    return (df.iloc[half:] if part_num == "2" else df.iloc[:half]).reset_index(drop=True)


df = load_data(task, part)

st.title(f"AI Search Eval -- {task} task (Part {part})")

if 'current_idx' not in st.session_state:
    st.session_state.current_idx = 0

worker_id = st.text_input("Enter your Prolific/Connect ID:")

if worker_id:
    idx = st.session_state.current_idx

    if idx < len(df):
        row = df.iloc[idx]

        st.progress((idx + 1) / len(df))
        st.subheader(f"Item {idx + 1} of {len(df)}: {row['item_id']}")

        if task == "plan":
            col1, col2 = st.columns([1, 1])
            with col1:
                st.markdown(f"**Question:**\n> {row['question']}")
                st.markdown(f"**Search Plan:**\n```text\n{row['search_plan']}\n```")
            with col2:
                st.markdown(f"**Gold Answer:**\n{row['correct_answer']}")
                st.info(f"**Reference Passages:**\n{row['reference_passages']}")

            st.divider()
            col_r1, col_r2, col_r3 = st.columns(3)
            r1 = col_r1.radio("Grounded", RATING_OPTIONS, horizontal=True, key=f"g_{idx}",
                               help="Are the facts in the plan actually implied by the question, with nothing invented?")
            r2 = col_r2.radio("Coverage", RATING_OPTIONS, horizontal=True, key=f"c_{idx}",
                               help="Does the plan include every step needed to reach the answer?")
            r3 = col_r3.radio("Specificity", RATING_OPTIONS, horizontal=True, key=f"s_{idx}",
                               help="Is each step sufficiently concrete about what to retrieve?")
        else:  # sufficiency
            # 2026-09-14: recent_reasoning is multi-paragraph -- Markdown's
            # "> " blockquote syntax only wraps the FIRST paragraph (it
            # breaks at the first blank line), so the rest silently fell
            # back to plain unquoted text, visually splitting one field
            # into two different styles. st.info's box doesn't have that
            # problem, so it's used here too instead of "> " prefixing.
            st.markdown(f"**Question:**\n> {row['question']}")
            st.info(f"**Prior reasoning:**\n\n{row['recent_reasoning']}")
            st.markdown(f"**Search query:**\n> {row['search_query']}")
            st.info(f"**Retrieved information:**\n\n{row['extracted_info']}")

            st.divider()
            r1 = st.radio(
                "Is the retrieved information SUFFICIENT to answer the question "
                "(given the prior reasoning so far)?",
                SUFFICIENCY_OPTIONS, horizontal=True, key=f"suff_{idx}",
            )
            r2, r3 = "", ""

        notes = st.text_input("Notes (Optional)", key=f"n_{idx}")

        if st.button("Submit & Next"):
            save_response(worker_id, task, part, row['item_id'], r1, r2, r3, notes)
            st.session_state.current_idx += 1
            st.rerun()
    else:
        st.balloons()
        st.success(f"🎉 You have completed all {len(df)} items! Thank you.")
else:
    st.warning("Please enter your Connect ID to start.")
