import streamlit as st
import requests
import time

BACKEND_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="ClauseAI - Contract Analyzer", layout="wide")

st.title("📄 ClauseAI - AI Contract Review System")

st.write("Upload a contract to analyze clauses, risks, and generate a legal review report.")

uploaded_file = st.file_uploader("Upload Contract (PDF)", type=["pdf"])

if uploaded_file:

    if st.button("Analyze Contract"):

        with st.spinner("Uploading and analyzing..."):

            files = {"file": uploaded_file.getvalue()}

            response = requests.post(
                f"{BACKEND_URL}/analyze",
                files={"file": (uploaded_file.name, uploaded_file, "application/pdf")}
            )

            if response.status_code != 200:
                st.error("Failed to start analysis.")
            else:
                task_id = response.json()["task_id"]
                st.session_state["task_id"] = task_id
                st.success(f"Analysis started. Task ID: {task_id}")

# Poll result
if "task_id" in st.session_state:

    task_id = st.session_state["task_id"]

    status_placeholder = st.empty()

    while True:
        result_response = requests.get(f"{BACKEND_URL}/result/{task_id}")
        result_data = result_response.json()

        status = result_data["status"]

        status_placeholder.info(f"Status: {status}")

        if status == "completed":
            st.success("Analysis Completed!")

            st.subheader("📊 Final Report")
            st.markdown(result_data["result"])

            download_response = requests.get(f"{BACKEND_URL}/download/{task_id}")

            st.download_button(
                label="⬇ Download Report",
                data=download_response.text,
                file_name=f"{task_id}_report.md",
                mime="text/markdown"
            )

            break

        elif status == "failed":
            st.error("Analysis Failed.")
            break

        time.sleep(3)
