import streamlit as st
from airtable_storage import AirtableStorage
import json

st.set_page_config(page_title="Editors", layout="wide")
st.title("Editors — Review Submissions")

storage = AirtableStorage(
    st.secrets["AIRTABLE_TOKEN"],
    st.secrets["AIRTABLE_BASE_ID"],
    st.secrets["AIRTABLE_TABLE_NAME"]
)

status = st.selectbox("Filter by status", ["New", "Approved", "Rejected"])
records = storage.list_records(status=status).get("records", [])

for r in records:
    f = r["fields"]
    with st.container(border=True):
        st.markdown(f"### {f.get('Title')}")
        st.write(f["URL"])
        st.write(f"**Confidence:** {f.get('Confidence')}")
        st.text(f.get("Top Bullets", ""))

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Approve", key=r["id"] + "_a"):
                storage.update_status(f["Article ID"], "Approved")
                st.rerun()
        with col2:
            if st.button("Reject", key=r["id"] + "_r"):
                storage.update_status(f["Article ID"], "Rejected")
                st.rerun()

        with st.expander("Full JSON"):
            st.json(json.loads(f["Full Card JSON"]))
