import os
import sys
import json
import re

from PIL import Image
from aletheia.rag.parsers.dots_ocr.utils.image_utils import PILimage_to_base64


def has_latex_markdown(text: str) -> bool:
    """
    Checks if a string contains LaTeX markdown patterns.
    
    Args:
        text (str): The string to check.
        
    Returns:
        bool: True if LaTeX markdown is found, otherwise False.
    """
    if not isinstance(text, str):
        return False
    
    # Define regular expression patterns for LaTeX markdown
    latex_patterns = [
        r'\$\$.*?\$\$',           # Block-level math formula $$...$$
        r'\$[^$\n]+?\$',          # Inline math formula $...$
        r'\\begin\{.*?\}.*?\\end\{.*?\}',  # LaTeX environment \begin{...}...\end{...}
        r'\\[a-zA-Z]+\{.*?\}',    # LaTeX command \command{...}
        r'\\[a-zA-Z]+',           # Simple LaTeX command \command
        r'\\\[.*?\\\]',           # Display math formula \[...\]
        r'\\\(.*?\\\)',           # Inline math formula \(...\)
    ]
    
    # Check if any of the patterns match
    for pattern in latex_patterns:
        if re.search(pattern, text, re.DOTALL):
            return True
    
    return False


def clean_latex_preamble(latex_text: str) -> str:
    """
    Removes LaTeX preamble commands like document class and package imports.
    
    Args:
        latex_text (str): The original LaTeX text.

    Returns:
        str: The cleaned LaTeX text without preamble commands.
    """
    # Define patterns to be removed
    patterns = [
        r'\\documentclass\{[^}]+\}',  # \documentclass{...}
        r'\\usepackage\{[^}]+\}',    # \usepackage{...}
        r'\\usepackage\[[^\]]*\]\{[^}]+\}',  # \usepackage[options]{...}
        r'\\begin\{document\}',       # \begin{document}
        r'\\end\{document\}',         # \end{document}
    ]
    
    # Apply each pattern to clean the text
    cleaned_text = latex_text
    for pattern in patterns:
        cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.IGNORECASE)
    
    return cleaned_text
    

def get_formula_in_markdown(text: str) -> str:
    """
    Formats a string containing a formula into a standard Markdown block.
    
    Args:
        text (str): The input string, potentially containing a formula.

    Returns:
        str: The formatted string, ready for Markdown rendering.
    """
    # Remove leading/trailing whitespace
    text = text.strip()
    
    # Check if it's already enclosed in $$
    if text.startswith('$$') and text.endswith('$$'):
        text_new = text[2:-2].strip()
        if not '$' in text_new:
            return f"$$\n{text_new}\n$$"
        else:
            return text

    # Handle \[...\] format, convert to $$...$$
    if text.startswith('\\[') and text.endswith('\\]'):
        inner_content = text[2:-2].strip()
        return f"$$\n{inner_content}\n$$"
        
    # Check if it's enclosed in \[ \]
    if len(re.findall(r'.*\\\[.*\\\].*', text)) > 0:
        return text

    # Handle inline formulas ($...$)
    pattern = r'\$([^$]+)\$'
    matches = re.findall(pattern, text)
    if len(matches) > 0:
        # It's an inline formula, return it as is
        return text  

    # If no LaTeX markdown syntax is present, return directly
    if not has_latex_markdown(text):  
        return text

    # Handle unnecessary LaTeX formatting like \usepackage
    if 'usepackage' in text:
        text = clean_latex_preamble(text)

    if text[0] == '`' and text[-1] == '`':
        text = text[1:-1]

    # Enclose the final text in a $$ block with newlines
    text = f"$$\n{text}\n$$"
    return text 


def clean_text(text: str) -> str:
    """
    Cleans text by removing extra whitespace.
    
    Args:
        text: The original text.
        
    Returns:
        str: The cleaned text.
    """
    if not text:
        return ""
    
    # Remove leading and trailing whitespace
    text = text.strip()
    
    # Replace multiple consecutive whitespace characters with a single space
    if text[:2] == '`$' and text[-2:] == '$`':
        text = text[1:-1]
    
    return text


def layoutjson2md(image: Image.Image, cells: list, text_key: str = 'text', no_page_hf: bool = False, model_name: str = None) -> str:
    """
    Converts a layout JSON format to Markdown.
    
    In the layout JSON, formulas are LaTeX, tables are HTML, and text is Markdown.
    
    Args:
        image: A PIL Image object.
        cells: A list of dictionaries, each representing a layout cell.
        text_key: The key for the text field in the cell dictionary.
        no_page_header_footer: If True, skips page headers and footers.
        
    Returns:
        str: The text in Markdown format.
    """
    text_items = []

    for i, cell in enumerate(cells):
        x1, y1, x2, y2 = [int(coord) for coord in cell['bbox']]
        text = cell.get(text_key, "")
        
        if no_page_hf and cell['category'] in ['Page-header', 'Page-footer']:
            continue
        
        if cell['category'] == 'Picture':
            image_crop = image.crop((x1, y1, x2, y2))
            image_base64 = PILimage_to_base64(image_crop)
            text_items.append(f"![]({image_base64})")
        elif cell['category'] == 'Formula':
            text_items.append(get_formula_in_markdown(text))
        else:            
            text = clean_text(text)
            text = normalize_latex_delimiters(text)
            text_items.append(f"{text}")

    markdown_text = '\n\n'.join(text_items)
    return markdown_text


def normalize_latex_delimiters(text: str) -> str:
    r"""
    Standardizes LaTeX delimiters to ensure compatibility with Markdown renderers.
    Converts:
    1. \\( ... \\) -> $ ... $
    2. \\[ ... \\] -> $$ ... $$
    3. Heuristic: (...) containing LaTeX math -> $ ... $
    """
    if not text:
        return text

    # Helper to protect existing $...$ and $$...$$ from double processing could be needed,
    # but simple replacements are usually fine if carefully ordered.

    # 1. Convert \[ ... \] to $$ ... $$
    # Look for \[ not preceded by backslash
    text = re.sub(r'(?<!\\)\\\[(.*?)(?<!\\)\\\]', r'$$\n\1\n$$', text, flags=re.DOTALL)

    # 2. Convert \( ... \) to $ ... $
    text = re.sub(r'(?<!\\)\\\((.*?)(?<!\\)\\\)', r'$\1$', text, flags=re.DOTALL)

    # 3. Heuristic: Fix ( ... ) wrapping obvious LaTeX math like \times, ^{}, _{}
    # Pattern looks for (...) containing \times, \pm, \approx, or ^{...}, _{...}
    # We must be careful not to match normal text.
    # Matches ( 2.2 \times 10^{-5} )
    
    def repl_parens_math(match):
        content = match.group(1)
        # Check for strong signals of math
        if any(x in content for x in [r'\times', r'\cdot', r'\div', r'^{', r'_{', r'\pm', r'\approx', r'\leq', r'\geq']):
             return f"${content}$"
        return match.group(0)

    # Regex for content inside parentheses
    text = re.sub(r'\(([^)]*?\\[a-zA-Z]+[^)]*?)\)', repl_parens_math, text)

    # 4. Heuristic: Fix common hallucinations like \left \int (invalid latex)
    text = re.sub(r'\\left\s*\\int', r'\\int', text)

    # 5. Heuristic: specific fix for equations starting with variable assignments that are not wrapped
    # Example: G = 4\pi... -> $$ G = 4\pi... $$
    # Only if it contains LaTeX commands and =, and NO existing $ wrappers
    if '$' not in text:
        # Check for equation-like structure: Variable = Expression with LaTeX
        # Must contain =, \, and typical math symbols
        if '=' in text and '\\' in text and any(x in text for x in ['^', '_', '\\int', '\\sum', '\\frac', '\\pi']):
             # Check if it looks like a full line equation
             if len(text.split('\n')) <= 1:
                  text = f"$$\n{text}\n$$"

    return text


def fix_streamlit_formulas(md: str) -> str:
    """
    Fixes the format of formulas in Markdown to ensure they display correctly in Streamlit.
    It adds a newline after the opening $$ and before the closing $$ if they don't already exist.
    
    Args:
        md_text (str): The Markdown text to fix.
        
    Returns:
        str: The fixed Markdown text.
    """
    
    # This inner function will be used by re.sub to perform the replacement
    def replace_formula(match):
        content = match.group(1)
        # If the content already has surrounding newlines, don't add more.
        if content.startswith('\n'):
            content = content[1:]
        if content.endswith('\n'):
            content = content[:-1]
        return f'$$\n{content}\n$$'
    
    # Use regex to find all $$....$$ patterns and replace them using the helper function.
    return re.sub(r'\$\$(.*?)\$\$', replace_formula, md, flags=re.DOTALL)
