from aletheia.pipeline.ingestion_pipeline import IngestionPipeline
from pathlib import Path
import os

# Get test data path
test_data_dir = Path(__file__).parent.parent / "data"
test_pdf = test_data_dir / "paper.pdf"

# Fallback to sample PDF if paper.pdf doesn't exist
if not test_pdf.exists():
    # Try to find any PDF in data directory
    pdf_files = list(test_data_dir.glob("*.pdf"))
    if pdf_files:
        test_pdf = pdf_files[0]
    else:
        print("⚠️  No PDF files found in data directory. Please add a PDF to test.")
        exit(1)

try:
    # Initialize pipeline
    pipeline = IngestionPipeline(
        vision_provider="gemini",
        vision_model=None
    )
    
    # Setup indices
    pipeline.setup_indices(drop_existing=True)
    
    # Ingest document
    doc_id = pipeline.ingest_document(
        pdf_path=str(test_pdf)
    )
    
    print(f"\n✓ Document ingested successfully!")
    print(f"  Document ID: {doc_id}")
    print(f"  You can now query using retriever.py")
    
    # Close connections
    pipeline.close()
    
except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()