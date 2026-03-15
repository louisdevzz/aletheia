# RAG Test UI

Giao diện test đơn giản bằng Streamlit cho hệ thống RAG Aletheia.

## 🚀 Quick Start

### Cách 1: Dùng UV (Khuyến nghị - Nhanh hơn)

```bash
# 1. Install UV (nếu chưa có)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Setup project
cd /home/phanvantai/Documents/Finding/run/aletheia
uv sync

# 3. Tạo .env và start infrastructure
cp .env.example .env
docker-compose -f docker/milvus/docker-compose.yml up -d
docker-compose -f docker/elasticsearch/docker-compose.yml up -d

# 4. Chạy UI
uv run streamlit run aletheia/rag/test_ui.py
```

### Cách 2: Dùng pip

```bash
# 1. Cài đặt dependencies
pip install -e .
pip install streamlit

# 2. Tạo .env và start infrastructure
cp .env.example .env
docker-compose -f docker/milvus/docker-compose.yml up -d
docker-compose -f docker/elasticsearch/docker-compose.yml up -d

# 3. Chạy UI
streamlit run aletheia/rag/test_ui.py
```

**Mở browser:** http://localhost:8501

---

## 🖥️ Web UI Features

### Tab 1: Upload Document 📄
- **Drag & drop** PDF upload
- **Chọn Vision LLM provider**: OpenAI / Gemini / Kimi
- **Drop existing indices**: Checkbox để xóa data cũ (⚠️ cẩn thận)
- **Real-time progress**: Hiển thị trạng thái ingestion
- **Auto refresh**: Cập nhật stats sau khi ingest

### Tab 2: Search 🔍
- **Query input**: Nhập câu hỏi tìm kiếm
- **Top K**: Số kết quả trả về (1-10)
- **Document filter**: Chọn tìm trong tất cả docs hoặc doc cụ thể
- **Advanced Options** (⚙️):
  - **Alpha**: Cân bằng Vector (1.0) vs BM25 (0.0), default 0.5
  - **Rerank Method**: Weighted fusion hoặc RRF (Reciprocal Rank Fusion)
  - **Cumulative Context**: Enrich context từ preceding paragraphs (cần LLM)
- **Kết quả hiển thị**:
  - Score (độ tương đồng)
  - Document ID, Page, Paragraph
  - Char offset (cho citations chính xác)
  - Content preview
  - Cumulative stats (nếu bật): số text chunks, tables, formulas

### Tab 3: Documents 📚
- **List tất cả documents**: Xem ID, số pages, thởi gian tạo
- **View Raw Text**: Xem toàn bộ text content của document để verify citations
- **Delete**: Xóa document khỏi cả 3 storage layers (SQLite + Milvus + ES)

### Sidebar
- **🔧 Services Status**: Kiểm tra Milvus và Elasticsearch có running không
- **📊 Database Stats**: Số documents, sentences, chat messages

---

## 🔧 Prerequisites

Trước khi chạy test, đảm bảo:

### 1. Infrastructure Running
```bash
# Start Milvus
docker-compose -f docker/milvus/docker-compose.yml up -d

# Start Elasticsearch
docker-compose -f docker/elasticsearch/docker-compose.yml up -d

# Verify
curl http://localhost:9091/healthz        # Milvus
curl http://localhost:9200/_cluster/health  # Elasticsearch
```

### 2. API Keys Configured (file `.env`)
```bash
cp .env.example .env
# Edit .env và thêm ít nhất 1 key:

OPENAI_API_KEY=sk-...
# hoặc
GOOGLE_API_KEY=...
# hoặc  
KIMI_API_KEY=...
```

### 3. Python Dependencies

**Với UV (khuyến nghị):**
```bash
uv sync
```

**Với pip:**
```bash
pip install -e .
pip install streamlit
```

---

## 📊 Test Scenarios

### Scenario 1: Basic Ingestion & Search
1. **Upload**: Chọn PDF → Chọn Vision Provider → Click "Start Ingestion"
2. **Verify**: Check Document ID hiển thị
3. **Search**: Sang tab Search → Nhập query → Click "Search"
4. **Verify**: Xem kết quả có đúng không, check citations

### Scenario 2: Hybrid Search Tuning
- **Alpha = 0**: Pure BM25 (keyword matching)
- **Alpha = 1**: Pure Vector (semantic matching)
- **Alpha = 0.5**: Balanced (kết hợp cả 2)

### Scenario 3: Cumulative Context
1. Bật **Cumulative Context** trong Advanced Options
2. Search: "explain the methodology"
3. Verify: Kết quả có enriched context

### Scenario 4: Verify Citations
1. Search và nhận kết quả với char offset
2. Sang tab Documents → Click "View Raw Text"
3. Verify: Text ở char offset có khớp không

### Scenario 5: Multi-document Search
1. Upload nhiều documents
2. Search với "All Documents" selected
3. Test filter: Chọn 1 doc cụ thể

### Scenario 6: Delete & Verify
1. Note document ID
2. Click "Delete"
3. Verify: Document biến mất, không còn trong search results

---

## 🔧 UV Commands (Thêm nhanh)

```bash
# Cài đặt
uv sync

# Chạy UI
uv run streamlit run aletheia/rag/test_ui.py

# Chạy với docker
uvx docker-compose -f docker/milvus/docker-compose.yml up -d

# View SQLite database
uv pip install sqlite-web
uvx sqlite-web ~/.aletheia/database/aletheia.db

# Cập nhật dependencies
uv sync --upgrade

# Lock dependencies
uv lock
```

---

## 🐛 Troubleshooting

### Infrastructure Issues

**Milvus not accessible:**
```bash
docker-compose -f docker/milvus/docker-compose.yml up -d
docker logs milvus-standalone
```

**Elasticsearch not accessible:**
```bash
docker-compose -f docker/elasticsearch/docker-compose.yml up -d
sudo sysctl -w vm.max_map_count=262144  # Linux only
docker logs elasticsearch
```

### Python Issues

**No module named 'streamlit':**
```bash
# UV
uv pip install streamlit

# pip
pip install streamlit
```

**No module named 'aletheia':**
```bash
# UV
uv pip install -e .

# pip
pip install -e .
```

**Import errors (general):**
```bash
# UV
uv pip install --force-reinstall -e .

# pip
pip install --force-reinstall -e .
```

### UV Issues

**command not found: uv**
```bash
export PATH="$HOME/.cargo/bin:$PATH"
exec $SHELL
```

**Permission denied**
```bash
chmod +x .venv/bin/*
# Hoặc recreate venv
rm -rf .venv && uv venv && uv pip install -e .
```

### API Issues

**API Key invalid:**
```bash
cat .env | grep -E "(OPENAI|GOOGLE|KIMI)"
curl https://api.openai.com/v1/models -H "Authorization: Bearer $OPENAI_API_KEY"
```

**Cumulative context failed:**
- Cần OpenAI API key
- Hoặc tắt Cumulative Context

### Performance Issues

**Ingestion chậm/treo:**
- Vision LLM parsing tốn thởi gian
- Kimi thường nhanh hơn OpenAI/Gemini
- Kiểm tra logs trong terminal

---

## 📈 Expected Output

### Successful Ingestion
```
✅ Document ingested successfully!
Document ID: abc-123-456-def
💡 You can now search this document in the Search tab
```

### Search Results
```
Found 3 results

Result #1 (Score: 0.8567)
----------------------------------------
Document: abc-123...
Page: 5
Paragraph: p5_para2
Char Offset: 1024 - 2048

Content:
[Text content hiển thị ở đây]
```

### With Cumulative Context
```
📊 Cumulative: 3 text chunks, 1 tables, 0 formulas
[Enriched content với summary và tables]
```

---

## 🎯 Validation Checklist

Trước khi coi là test thành công:

- [ ] **Ingestion**: PDF được parse thành công
- [ ] **Storage**: Document xuất hiện trong tab Documents
- [ ] **Vector Search**: Alpha=1 trả về kết quả semantic
- [ ] **BM25 Search**: Alpha=0 trả về kết quả keyword
- [ ] **Hybrid**: Alpha=0.5 kết hợp cả 2
- [ ] **Citations**: Char offset khớp với raw text
- [ ] **Cumulative**: Bật cumulative có enriched context
- [ ] **Delete**: Xóa document thành công

---

## 📝 Notes

**Vision LLM:**
- OpenAI (GPT-4o): Chất lượng cao, giá đắt
- Gemini (Flash): Nhanh, giá rẻ
- Kimi: Nhanh, parse tốt table/formula

**Embedding:**
- Ollama (local): Miễn phí, cần GPU/CPU mạnh
- OpenAI: Nhanh, phí per token

**Storage:**
- SQLite: Local file (~/.aletheia/database/aletheia.db) - **KHÔNG cần start**
- Milvus: Vector DB (Docker) - **CẦN start**
- Elasticsearch: BM25 index (Docker) - **CẦN start**

---

## 🆘 Next Steps

Sau khi test thành công:
1. Tune **alpha** parameter cho use case
2. Chọn **rerank method** phù hợp
3. Quyết định có dùng **cumulative context**
4. Chạy full test suite: `uv run pytest tests/`
5. Xem báo cáo: `RAG_INTEGRATION_REPORT.md`

---

## 📚 Tài Liệu Tham Khảo

- [RAG Integration Report](../../RAG_INTEGRATION_REPORT.md) - Báo cáo chi tiết
- [UV Documentation](https://docs.astral.sh/uv/) - UV package manager
- [Streamlit Documentation](https://docs.streamlit.io/) - Streamlit framework

---

**Phiên bản:** 0.1.0  
**Cập nhật:** 2026-03-03
