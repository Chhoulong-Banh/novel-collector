"""Streamlit dashboard for directory and chapter-URL-range metadata collection."""
from __future__ import annotations
import json
import streamlit as st
from novel_collector.core import collect, collect_url_range, CollectionError
from novel_collector.washai import collect_washai

st.set_page_config(page_title="Novel Collector V0.3", page_icon="📚")
st.title("Novel Collector V0.2")
st.caption("Directory metadata only. Existing directory mode is preserved; no chapter text is downloaded.")
source = st.selectbox("Novel source", ["书海阁 (Washai) — Sample 1", "和图书 (Hetushu) — Sample 2"])
washai = source.startswith("书海阁")
mode = st.radio("Collection mode", ["Directory discovery (existing)", "Start/end chapter URLs (new)"])
if mode.startswith("Directory"):
    url = st.text_input("Novel directory URL", "https://book.washai.net/book/indexList-1262260513468565364.html" if washai else "https://www.hetushu.com/book/7633/index.html")
    col1, col2 = st.columns(2)
    with col1:
        start = st.number_input("Start directory position", min_value=1, value=1, step=1)
    with col2:
        end = st.number_input("End directory position", min_value=1, value=10, step=1)
else:
    start_url = st.text_input("Full start chapter URL", "https://book.washai.net/book/1262260513468565364/2039351400477257412.html" if washai else "https://www.hetushu.com/book/7633/5339798.html")
    end_url = st.text_input("Full end chapter URL", "https://book.washai.net/book/1262260513468565364/2039351400477258011.html" if washai else "https://www.hetushu.com/book/7633/5340394.html")
    st.caption("Both boundary URLs must be found in the accessible directory. Intermediate IDs are never guessed.")
st.selectbox("Export format", ["Markdown (.md)"], disabled=True)
st.selectbox("Storage", ["Local folder"], disabled=True)
delay = st.slider("Minimum request interval (seconds)", min_value=3, max_value=15, value=3)
st.info("HTTP 403 and disallowed robots.txt rules stop live collection. No bypass attempted.")
if st.button("Discover and export directory", type="primary"):
    try:
        if mode.startswith("Directory"):
            md, report = (collect_washai(url, int(start), int(end), float(delay)) if washai else collect(url, int(start), int(end), float(delay)))
        else:
            md, report = (collect_washai(start_url=start_url, end_url=end_url, delay=float(delay)) if washai else collect_url_range(start_url, end_url, float(delay)))
        st.success("Export completed.")
        st.code(str(md), language=None)
        st.code(str(report), language=None)
        st.download_button("Download Markdown", md.read_bytes(), file_name=md.name, mime="text/markdown")
        st.download_button("Download report JSON", report.read_bytes(), file_name=report.name, mime="application/json")
        data = json.loads(report.read_text(encoding="utf-8"))
        st.write({"Discovered": data["discovered_count"], "Selected": data["selected_count"], "Range complete": data["range_complete"]})
    except (CollectionError, OSError) as exc:
        st.error(str(exc))
