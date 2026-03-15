"""
Aletheia RAG - Simple Test UI
Giao diện đơn giản để test RAG system

Usage:
    streamlit run aletheia/rag/test_ui.py
"""

import streamlit as st
import sys
import os
from pathlib import Path
import tempfile
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# ============================================
# PAGE SETUP
# ============================================
st.set_page_config(
    page_title="Aletheia RAG Test",
    page_icon="🧬",
    layout="wide",
)

# ============================================
# SIMPLE CSS
# ============================================
st.markdown(
    """
<style>
    .main-header {
        font-size: 2rem;
        font-weight: bold;
        color: #10a37f;
        margin-bottom: 1rem;
    }
    .status-online { color: #10a37f; font-weight: bold; }
    .status-offline { color: #ff4444; font-weight: bold; }
    .info-box {
        background: #f0f0f0;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #10a37f;
    }
    .message-user {
        background: #10a37f;
        color: white;
        padding: 0.8rem 1rem;
        border-radius: 15px 15px 4px 15px;
        margin: 0.5rem 0;
        max-width: 80%;
        margin-left: auto;
    }
    .message-bot {
        background: #f5f5f5;
        color: #333;
        padding: 0.8rem 1rem;
        border-radius: 15px 15px 15px 4px;
        margin: 0.5rem 0;
        max-width: 80%;
        border-left: 3px solid #10a37f;
    }
    .source-chip {
        display: inline-block;
        background: #e8f5e9;
        color: #2e7d32;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.8em;
        margin: 2px;
        border: 1px solid #c8e6c9;
    }
</style>
""",
    unsafe_allow_html=True,
)

# ============================================
# IMPORTS & INIT
# ============================================
from aletheia.rag.pipeline.ingestion_pipeline import IngestionPipeline
from aletheia.rag.retrieval.retrieval import HybridRetrieval
from aletheia.rag.storage.sqlite_store import SQLiteStore
from aletheia.config.settings import storage_config

# Session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_upload" not in st.session_state:
    st.session_state.last_upload = None
if "services_checked" not in st.session_state:
    st.session_state.services_checked = False


# ============================================
# SERVICE STATUS
# ============================================
def check_services():
    """Check service status."""
    import requests
    import sqlite3
    from aletheia.config.settings import milvus_config, elasticsearch_config, kimi_config

    status = {
        "Milvus": "❌ Offline",
        "Elasticsearch": "❌ Offline",
        "SQLite": "❌ Offline",
        "Kimi API": "❌ No Key",
    }

    # Check Milvus
    try:
        response = requests.get(f"http://localhost:9091/healthz", timeout=2)
        if response.status_code == 200:
            status["Milvus"] = "✅ Online"
    except:
        pass

    # Check Elasticsearch
    try:
        response = requests.get("http://localhost:9200/_cluster/health", timeout=2)
        if response.status_code == 200:
            status["Elasticsearch"] = "✅ Online"
    except:
        pass

    # Check SQLite
    try:
        conn = sqlite3.connect(storage_config.db_path)
        conn.execute("SELECT 1")
        conn.close()
        status["SQLite"] = "✅ Online"
    except:
        pass

    # Check Kimi
    if kimi_config.api_key:
        status["Kimi API"] = "✅ Configured"

    return status


# ============================================
# HEADER
# ============================================
st.markdown(
    '<div class="main-header">🧬 Aletheia RAG Test Interface</div>', unsafe_allow_html=True
)

# Check services
if not st.session_state.services_checked:
    with st.spinner("Checking services..."):
        services = check_services()
        st.session_state.services = services
        st.session_state.services_checked = True

# Show service status
cols = st.columns(4)
for i, (service, status) in enumerate(st.session_state.services.items()):
    with cols[i]:
        is_online = "✅" in status
        st.markdown(
            f"""
        <div style="text-align: center; padding: 10px; 
                    background: {"#e8f5e9" if is_online else "#ffebee"}; 
                    border-radius: 8px;
                    border: 1px solid {"#c8e6c9" if is_online else "#ffcdd2"};">
            <div style="font-size: 1.5rem">{status.split()[0]}</div>
            <div style="font-size: 0.9rem; font-weight: bold;
                        color: {"#2e7d32" if is_online else "#c62828"};">
                {service}
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )

st.markdown("---")

# ============================================
# MAIN TABS
# ============================================
tab1, tab2, tab3 = st.tabs(["📤 Upload & Ingest", "💬 Chat", "🔍 Test Retrieval"])

# ============================================
# TAB 1: UPLOAD & INGEST
# ============================================
with tab1:
    st.header("📤 Upload PDF Document")

    uploaded_file = st.file_uploader(
        "Chọn file PDF để upload",
        type=["pdf"],
        help="Upload một file PDF để hệ thống phân tích",
    )

    if uploaded_file:
        col1, col2 = st.columns([2, 1])

        with col1:
            st.info(
                f"📄 File: **{uploaded_file.name}** ({uploaded_file.size / 1024:.1f} KB)"
            )

            if st.button("🚀 Bắt đầu Ingest", type="primary", use_container_width=True):
                with st.spinner("Đang xử lý..."):
                    try:
                        # Save temp file
                        with tempfile.NamedTemporaryFile(
                            delete=False, suffix=".pdf"
                        ) as tmp:
                            tmp.write(uploaded_file.getvalue())
                            tmp_path = tmp.name

                        # Process
                        progress_bar = st.progress(0)
                        status_text = st.empty()

                        status_text.text("Step 1/3: Khởi tạo pipeline...")
                        pipeline = IngestionPipeline()
                        progress_bar.progress(33)

                        status_text.text(
                            "Step 2/3: Đang phân tích PDF với Vision LLM..."
                        )
                        doc_id = pipeline.ingest_document(tmp_path, uploaded_file.name)
                        progress_bar.progress(66)

                        status_text.text("Step 3/3: Đang lưu vào database...")
                        pipeline.close()
                        progress_bar.progress(100)

                        # Cleanup
                        os.unlink(tmp_path)

                        st.session_state.last_upload = {
                            "doc_id": doc_id,
                            "filename": uploaded_file.name,
                            "time": datetime.now().strftime("%H:%M:%S"),
                        }

                        st.success(f"✅ Upload thành công!\nDocument ID: {doc_id}")
                        status_text.empty()
                        progress_bar.empty()

                    except Exception as e:
                        st.error(f"❌ Lỗi: {str(e)}")
                        import traceback

                        st.code(traceback.format_exc())

        with col2:
            st.markdown("""
            **Quy trình:**
            1. 📄 Phân tích PDF
            2. 🤖 Vision LLM (Kimi)
            3. 💾 Lưu vào 3 layers:
               - SQLite
               - Milvus
               - Elasticsearch
            
            ⏱️ Thờigian: ~2-5 phút
            """)

    # Show uploaded documents
    st.markdown("---")
    st.subheader("📚 Documents đã upload")

    try:
        store = SQLiteStore()
        docs = store.get_all_documents()

        if docs:
            for doc in docs:
                col1, col2 = st.columns([4, 1])
                with col1:
                    doc_id = doc.get("doc_id", doc.get("id", "unknown"))
                    st.markdown(f"""
                    📄 **{doc["filename"]}**  
                    ID: `{doc_id[:8]}...` | Status: {doc.get("status", "N/A")}
                    """)
                with col2:
                    doc_id = doc.get("doc_id", doc.get("id", "unknown"))
                    if st.button("🗑️ Xóa", key=f"del_{doc_id}"):
                        try:
                            pipeline = IngestionPipeline()
                            pipeline.delete_document(doc_id)
                            pipeline.close()
                            st.success("Đã xóa!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Lỗi xóa: {e}")
        else:
            st.info("Chưa có documents nào. Hãy upload PDF ở trên.")
    except Exception as e:
        st.warning(f"Không thể load danh sách documents: {e}")

# ============================================
# TAB 2: CHAT
# ============================================
with tab2:
    st.header("💬 Chat với Documents")

    # Chat history
    chat_container = st.container()
    with chat_container:
        if not st.session_state.messages:
            st.markdown(
                """
            <div class="info-box">
                👋 <strong>Bắt đầu chat!</strong><br>
                Hãy đặt câu hỏi về tài liệu đã upload.
            </div>
            """,
                unsafe_allow_html=True,
            )

        for msg in st.session_state.messages:
            if msg["role"] == "user":
                st.markdown(
                    f'<div class="message-user">{msg["content"]}</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div class="message-bot">{msg["content"]}</div>',
                    unsafe_allow_html=True,
                )
                if msg.get("sources"):
                    sources_html = " ".join(
                        [
                            f'<span class="source-chip">[{i + 1}] {s["filename"]} p.{s["page_num"]}</span>'
                            for i, s in enumerate(msg["sources"][:3])
                        ]
                    )
                    st.markdown(
                        f"<div style='margin-left: 20px; margin-bottom: 10px;'>{sources_html}</div>",
                        unsafe_allow_html=True,
                    )

    # Input
    st.markdown("---")
    query = st.text_input(
        "Nhập câu hỏi của bạn:",
        placeholder="VD: Tóm tắt nội dung chính của tài liệu...",
    )

    col1, col2, col3 = st.columns([1, 1, 4])
    with col1:
        if st.button("📨 Gửi", type="primary", use_container_width=True) and query:
            with st.spinner("Đang tìm kiếm và trả lờ..."):
                try:
                    # Add user message
                    st.session_state.messages.append(
                        {"role": "user", "content": query, "sources": []}
                    )

                    # Search
                    retriever = HybridRetrieval()
                    results = retriever.hybrid_search(query, top_k=3)

                    # Generate simple response
                    if results:
                        response = f"Dựa vào tài liệu, tôi tìm thấy {len(results)} đoạn liên quan:\n\n"
                        for i, r in enumerate(results[:2], 1):
                            text = r.get("text", "")[:200]
                            response += f"{i}. {text}...\n\n"

                        sources = [
                            {
                                "filename": r.get("filename", "Unknown"),
                                "page_num": r.get("page_num", 0),
                            }
                            for r in results[:3]
                        ]
                    else:
                        response = "Xin lỗi, tôi không tìm thấy thông tin liên quan trong tài liệu."
                        sources = []

                    # Add bot message
                    st.session_state.messages.append(
                        {"role": "assistant", "content": response, "sources": sources}
                    )

                    retriever.close()
                    st.rerun()

                except Exception as e:
                    st.error(f"Lỗi: {str(e)}")

    with col2:
        if st.button("🗑️ Xóa chat", use_container_width=True):
            st.session_state.messages = []
            st.rerun()

    # Quick questions
    st.markdown("**Câu hỏi nhanh:**")
    qcols = st.columns(4)
    quick_questions = [
        "Tóm tắt tài liệu",
        "Ý chính là gì?",
        "Có những gì?",
        "Kết luận?",
    ]
    for i, q in enumerate(quick_questions):
        with qcols[i]:
            if st.button(q, key=f"qq_{i}", use_container_width=True):
                # Simulate clicking
                pass

# ============================================
# TAB 3: TEST RETRIEVAL
# ============================================
with tab3:
    st.header("🔍 Test Retrieval")
    st.markdown("Test tính năng tìm kiếm hybrid (Vector + BM25)")

    test_query = st.text_input("Query test:", placeholder="Nhập query để test...")

    col1, col2 = st.columns(2)
    with col1:
        top_k = st.slider("Số kết quả:", 1, 10, 3)
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        search_clicked = st.button(
            "🔍 Tìm kiếm", type="primary", use_container_width=True
        )

    if search_clicked and test_query:
        with st.spinner("Đang tìm kiếm..."):
            try:
                retriever = HybridRetrieval()
                results = retriever.hybrid_search(test_query, top_k=top_k)

                if results:
                    st.success(f"Tìm thấy {len(results)} kết quả")

                    for i, r in enumerate(results, 1):
                        with st.expander(
                            f"Kết quả {i} (Score: {r.get('score', 0):.3f})"
                        ):
                            st.markdown(f"""
                            **File:** {r.get("filename", "N/A")}  
                            **Page:** {r.get("page_num", "N/A")}  
                            **Text:**
                            ```
                            {r.get("text", "N/A")[:500]}
                            ```
                            """)
                else:
                    st.warning("Không tìm thấy kết quả nào.")

                retriever.close()

            except Exception as e:
                st.error(f"Lỗi tìm kiếm: {str(e)}")
                import traceback

                st.code(traceback.format_exc())

# ============================================
# FOOTER
# ============================================
st.markdown("---")
st.caption("Aletheia RAG Test UI v0.1.0 | Sử dụng để test và kiểm tra hệ thống RAG")
