# app.py
import streamlit as st
import requests
import html
import re

st.set_page_config(page_title="The Library", layout="wide")
st.title("The Library")

query = st.text_input("Search", placeholder="Dai Viet, Sherlock Holmes, Red-teaming, ...")

if query:
    resp = requests.get("http://127.0.0.1:8000/search", params={"q": query})
    results = resp.json()

    st.caption(f"{len(results)} results")

    cleaned_results = {}

    for r in results:
        if r['title'] not in cleaned_results:
            cleaned_results[r['title']] = {
                "rel_path": r['rel_path'],
                "pages": [],
                "snippets": []
            }
        cleaned_results[r['title']]['pages'].append(r['page_num'])
        cleaned_results[r['title']]['snippets'].append(r['snippet'])

    for r in cleaned_results:
        with st.container(border=True):
            st.markdown(f"**{r}**")
            st.caption(f"{cleaned_results[r]['rel_path']}")
            for p, s in zip(cleaned_results[r]['pages'], cleaned_results[r]['snippets']):
                safe = html.escape(s)
                safe = safe.replace("#", "&#35;")         # kill # so it can't start a header
                # NOW restore only your mark tags:
                safe = safe.replace("&lt;mark&gt;", "<mark>").replace("&lt;/mark&gt;", "</mark>")
                st.markdown(f"- *(pg {p}):* " + safe, unsafe_allow_html=True)
