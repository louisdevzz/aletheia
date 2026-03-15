import os
import io
import base64
import re
from typing import List, Optional
from pathlib import Path
from dotenv import load_dotenv
from pdf2image import convert_from_path
import argparse
from openai import OpenAI
from .types import Sentence, Paragraph, DisplayMath, Table, Figure, Page, Document

# Load environment variables
load_dotenv()

# Prompt template for Vision LLM parsing
VISION_PROMPT = """You are a document parsing engine for citation-critical systems.

Your task is to faithfully reconstruct ONLY the actual academic/scientific content from the provided page image.

CONTENT TO EXTRACT (Include these):
- Title, authors, abstract
- Section headings (Introduction, Methods, Results, Discussion, Conclusion, References)
- Main text paragraphs with full sentences
- Mathematical equations (convert to LaTeX)
- Tables with data (convert to HTML)
- Figure captions (text describing figures)
- Bibliographic references

CONTENT TO EXCLUDE (Do NOT include these):
- Page headers and footers
- Page numbers
- "Downloaded from..." or "Accessed on..." text
- IP addresses
- "View table of contents" or navigation links
- Journal website branding (IOPscience, Nature.com, etc.)
- Terms and conditions
- Legal disclaimers
- Pricing information
- Standalone URLs (unless part of citations)
- Copyright notices
- "Some figures may appear in colour only in the online journal"

STRICT RULES (must follow):
- Do NOT summarize.
- Do NOT paraphrase.
- Do NOT improve wording.
- Do NOT merge sentences.
- Do NOT split sentences unless the original sentence is clearly broken by layout.
- Preserve original sentence boundaries as much as possible.
- Preserve original paragraph boundaries.
- Preserve original reading order.
- Do NOT add any new content.
- Do NOT include metadata, headers, or footers.

You are NOT an editor.
You are NOT a writer.
You are a faithful renderer of ONLY the academic content.

TASK DESCRIPTION
Process the attached image of a single document page and return a structured, citation-safe markdown representation containing ONLY the academic content.

Requirements:
1. Text
   - Return the plain text exactly as written.
   - Keep punctuation and capitalization.
   - Preserve sentence boundaries.
   - EXCLUDE headers, footers, and page numbers.

2. Mathematical expressions
   - Convert all equations into valid LaTeX.
   - Inline math must be wrapped with $...$.
   - Display math must be wrapped with $$...$$.
   - Do NOT simplify or rewrite equations.

3. Tables
   - Convert tables to HTML.
   - Preserve row and column order.
   - Do NOT infer missing values.

4. Figures
   - Extract figure captions (descriptive text).
   - Use [FIGURE] tag for captions.
   - Do NOT describe the visual appearance, only extract the caption text.

5. Layout
   - Preserve paragraph separation.
   - Preserve section and heading order.
   - Do NOT merge content across sections.
   - Do NOT include repeating headers/footers from each page.

OUTPUT FORMAT (MANDATORY)
---
primary_language: <ISO-639-1 code>
is_rotation_valid: <true|false>
rotation_correction: <degrees>
contains_table: <true|false>
contains_figure: <true|false>
---

[SECTION]
<Section title if present>

[PARAGRAPH]
Sentence 1.
Sentence 2.

[PARAGRAPH]
Sentence 3.

[DISPLAY_MATH]
$$
LaTeX equation
$$

[TABLE]
<table>...</table>

[FIGURE]
Figure 1. Description of the figure.

ADDITIONAL CONSTRAINTS (CRITICAL FOR CITATION)
- Do NOT reorder sentences.
- Do NOT merge paragraphs.
- Each sentence must remain an independent textual unit.
- Output must be deterministic: the same input page must produce the same output structure.
- EXCLUDE all metadata, headers, footers, and navigation elements.
"""


class IngestionParser:
    """
    Parser for canonical markdown format from Vision LLM.

    Configurable figure caption detection to avoid misclassification.
    """

    # Default patterns - can be overridden via constructor
    DEFAULT_FIGURE_INDICATORS = [
        r"^Figure\s+\d+",
        r"^Fig\.\s*\d+",
        r"^Scheme\s+\d+",
        r"^Diagram\s+\d+",
        r"^Chart\s+\d+",
        r"^Plot\s+\d+",
        r"^Graph\s+\d+",
        r"^Image\s+\d+",
    ]

    def __init__(self, figure_patterns: Optional[List[str]] = None):
        """
        Initialize parser.

        Args:
            figure_patterns: Optional list of regex patterns for figure detection.
                           If None, uses DEFAULT_FIGURE_INDICATORS.
        """
        patterns = (
            figure_patterns if figure_patterns else self.DEFAULT_FIGURE_INDICATORS
        )
        self._figure_patterns = [re.compile(p, re.IGNORECASE) for p in patterns]

    def set_figure_patterns(self, patterns: List[str]):
        """
        Update figure detection patterns at runtime.

        Args:
            patterns: List of regex patterns
        """
        self._figure_patterns = [re.compile(p, re.IGNORECASE) for p in patterns]

    def _is_figure_caption(self, content: str) -> bool:
        """
        Check if content is actually a figure caption misclassified as math.

        Args:
            content: The content to check

        Returns:
            True if content appears to be a figure caption
        """
        content_stripped = content.strip()

        # Check against figure patterns
        for pattern in self._figure_patterns:
            if pattern.match(content_stripped):
                return True

        # Check for low math symbol density (figure captions rarely have complex math)
        math_symbols = len(re.findall(r"[\\=+\-_\^\{\}\[\]\$]", content))
        total_chars = len(content)

        if total_chars > 0:
            math_ratio = math_symbols / total_chars
            # If very few math symbols and starts with capital letter, likely a caption
            if math_ratio < 0.05 and content_stripped[0].isupper():
                # Additional check: contains words typical of captions
                caption_words = [
                    "shows",
                    "displays",
                    "illustrates",
                    "depicts",
                    "presents",
                ]
                if any(word in content_stripped.lower() for word in caption_words):
                    return True

        return False

    def parse_canonical_markdown(self, markdown_text: str, page_index: int = 1) -> Page:
        items = []
        lines = markdown_text.splitlines()
        current_mode = None
        buffer = []

        # Simple ID counters
        para_count = 0
        math_count = 0
        table_count = 0
        fig_count = 0

        # Character offset tracking
        char_offset = 0

        def flush_buffer():
            nonlocal \
                current_mode, \
                buffer, \
                para_count, \
                math_count, \
                table_count, \
                fig_count, \
                char_offset
            if not current_mode:
                return

            content = "\n".join(buffer).strip()
            if not content:
                buffer = []
                current_mode = None
                return

            # Track start offset for this item
            item_start_offset = char_offset

            if current_mode == "PARAGRAPH":
                para_count += 1
                sentences = []
                # Naive sentence splitting by line, since prompt enforces sentence/line or explicit boundaries
                # The prompt says: "Sentence 1.\nSentence 2."
                # So we can split by newline.
                sent_lines = content.splitlines()
                sent_offset = item_start_offset
                for s_idx, s_text in enumerate(sent_lines):
                    if s_text.strip():
                        s_id = f"p{page_index}_para{para_count}_s{s_idx + 1}"
                        sent_start = sent_offset
                        sent_end = sent_offset + len(s_text)
                        sentences.append(
                            Sentence(s_id, s_text.strip(), sent_start, sent_end)
                        )
                        sent_offset = sent_end + 1  # +1 for newline
                if sentences:
                    items.append(
                        Paragraph(f"p{page_index}_para{para_count}", sentences)
                    )

            elif current_mode == "DISPLAY_MATH":
                # Check if content is actually a figure caption (misclassified)
                if self._is_figure_caption(content):
                    fig_count += 1
                    items.append(Figure(f"p{page_index}_fig{fig_count}", content, ""))
                else:
                    math_count += 1
                    items.append(
                        DisplayMath(f"p{page_index}_math{math_count}", content)
                    )

            elif current_mode == "TABLE":
                table_count += 1
                items.append(Table(f"p{page_index}_table{table_count}", content))

            elif current_mode == "FIGURE":
                fig_count += 1
                # Parsing ![Desc](path)
                desc = "Figure"
                path = ""
                if content.startswith("![") and "](" in content:
                    parts = content.split("](", 1)
                    desc = parts[0][2:]
                    path = parts[1][:-1]
                items.append(Figure(f"p{page_index}_fig{fig_count}", desc, path))

            # Update char_offset to end of this item
            char_offset = (
                item_start_offset + len(content) + 1
            )  # +1 for newline after item

            buffer = []
            current_mode = None

        for line in lines:
            line_stripped = line.strip()
            if line_stripped in [
                "[PARAGRAPH]",
                "[DISPLAY_MATH]",
                "[TABLE]",
                "[FIGURE]",
            ]:
                flush_buffer()
                current_mode = line_stripped.strip("[]")
            elif line_stripped == "[SECTION]":
                flush_buffer()
                # Section handling can be added here, treating as a special item or property
                current_mode = None
            elif line_stripped.startswith("---") and not current_mode:
                # Metadata block, skip for item parsing
                continue
            else:
                if current_mode:
                    buffer.append(line)

        flush_buffer()
        return Page(f"p{page_index}", items)


class DocumentRenderer:
    @staticmethod
    def render_for_reading(document: Document) -> str:
        output_lines = []
        for page in document.pages:
            for item in page.items:
                if isinstance(item, Paragraph):
                    # Join sentences for reading flow
                    text = " ".join([s.text for s in item.sentences])
                    output_lines.append(text)
                    output_lines.append("")  # Blank line after paragraph
                elif isinstance(item, DisplayMath):
                    output_lines.append("$$")
                    output_lines.append(item.latex)
                    output_lines.append("$$")
                    output_lines.append("")
                elif isinstance(item, Table):
                    # For reading, we might just output the HTML or a placeholder
                    # User requested stripping markers but keeping content.
                    output_lines.append(item.html)
                    output_lines.append("")
                elif isinstance(item, Figure):
                    output_lines.append(f"![{item.description}]({item.placeholder})")
                    output_lines.append("")
        return "\n".join(output_lines)


from aletheia.rag.parsers.dots_ocr.parser import DotsOCRParser
import tempfile
import shutil


class VisionLLMParser:
    def __init__(self, model_name: str = None, provider: str = None):
        """
        Initialize the Vision LLM Parser using Kimi only.

        Args:
            model_name: Specific model to use. If None, defaults to kimi-k2.5.
            provider: Deprecated, always uses 'kimi'
        """
        self.provider = "kimi"

        # Lazy import to avoid circular dep if needed, or just import here
        from aletheia.config.settings import kimi_config

        if model_name:
            self.model_name = model_name
        else:
            # Default to kimi-k2.5
            self.model_name = "kimi-k2.5"

        # Initialize DotsOCRParser
        self.dots_parser = DotsOCRParser(
            model_name=self.model_name,
            min_pixels=3136,  # Use defaults or tune
            max_pixels=11289600,
            num_thread=1,  # Single image processing usually
        )

        # Validate API key exists
        self._validate_api_key()

    def _validate_api_key(self):
        """Validate that API key is configured for the Kimi provider."""
        from aletheia.config.settings import kimi_config

        if not kimi_config.api_key:
            raise ValueError("KIMI_API_KEY not set in environment variables!")

        print(f"  ✅ API Key validated for KIMI provider")

    def get_pdf_info(self, pdf_path: str) -> int:
        """Get number of pages in PDF without converting everything."""
        from pdf2image import pdfinfo_from_path

        info = pdfinfo_from_path(pdf_path)
        return info["Pages"]

    def get_page_image(self, pdf_path: str, page_num: int, dpi: int = 300):
        """Convert a specific page to image (lazy loading)."""
        # pdf2image uses 1-based indexing for first_page/last_page
        images = convert_from_path(
            pdf_path, dpi=dpi, first_page=page_num, last_page=page_num
        )
        if images:
            return images[0]
        return None

    def parse_image(self, image) -> str:
        """Sends image to Vision LLM and extracts structured text via DotsOCR."""
        return self.parse_image_with_logging(image, page_num=None)

    def _encode_image(self, image) -> str:
        """Encode PIL Image to base64 string."""
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG")
        return base64.b64encode(buffered.getvalue()).decode("utf-8")

    def _parse_kimi(self, image) -> str:
        """Parse image using Kimi Coding API."""
        from aletheia.config.settings import kimi_config

        # Initialize OpenAI client with Kimi configuration
        client = OpenAI(
            api_key=kimi_config.api_key,
            base_url=kimi_config.base_url,
            default_headers={
                "User-Agent": kimi_config.user_agent,
            },
        )

        # Encode image to base64
        base64_image = self._encode_image(image)

        # Call Kimi API
        response = client.chat.completions.create(
            model=self.model_name,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": VISION_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}",
                            },
                        },
                    ],
                }
            ],
            temperature=0.0,
        )

        return response.choices[0].message.content

    def parse_image_with_logging(self, image, page_num=None) -> str:
        """Sends image to Vision LLM with detailed logging."""
        import time

        page_info = f"[Page {page_num}] " if page_num else ""

        # Handle Kimi provider separately
        if self.provider == "kimi":
            try:
                print(
                    f"  {page_info}📤 Sending request to {self.provider.upper()} API..."
                )
                api_start = time.time()

                content = self._parse_kimi(image)

                api_time = time.time() - api_start
                print(f"  {page_info}📥 API response received in {api_time:.1f}s")

                if content:
                    print(f"  {page_info}📝 Extracted {len(content)} characters")
                else:
                    print(f"  {page_info}⚠️  Empty content returned from API")

                return content

            except Exception as e:
                print(
                    f"  {page_info}❌ Error in VisionLLMParser: {type(e).__name__}: {e}"
                )
                import traceback

                traceback.print_exc()
                raise e

        # DotsOCR writes output to files. We use a temp dir.
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                print(
                    f"  {page_info}📤 Sending request to {self.provider.upper()} API..."
                )
                api_start = time.time()

                # We need to pass the image to _parse_single_image
                # It expects 'origin_image' as PIL Image.
                result = self.dots_parser._parse_single_image(
                    origin_image=image,
                    prompt_mode="prompt_aletheiarag",
                    save_dir=temp_dir,
                    save_name="temp_processing",
                    source="image",
                )

                api_time = time.time() - api_start
                print(f"  {page_info}📥 API response received in {api_time:.1f}s")

                # Retrieve content from result dict (we added this key)
                content = result.get("content", "")

                if not content:
                    # Fallback check file if 'content' key is missing for some reason
                    md_path = result.get("md_content_path")
                    if md_path and os.path.exists(md_path):
                        print(f"  {page_info}📂 Reading from file: {md_path}")
                        with open(md_path, "r", encoding="utf-8") as f:
                            content = f.read()

                if content:
                    print(f"  {page_info}📝 Extracted {len(content)} characters")
                else:
                    print(f"  {page_info}⚠️  Empty content returned from API")

                return content

            except Exception as e:
                print(
                    f"  {page_info}❌ Error in VisionLLMParser: {type(e).__name__}: {e}"
                )
                import traceback

                traceback.print_exc()
                raise e
