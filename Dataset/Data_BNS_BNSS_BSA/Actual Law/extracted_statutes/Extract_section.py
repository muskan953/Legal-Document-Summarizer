import re
import json
import os
import pdfplumber
import logging
import sys
from pathlib import Path
from tqdm import tqdm

# ---------------------- Setup Logging ---------------------------
def setup_logging():
    log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler = logging.FileHandler("statute_extraction.log", encoding='utf-8')
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_formatter)
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger

logger = setup_logging()


# ---------------------- Extract Text from PDF ---------------------------
def extract_text_from_pdf(pdf_path):
    if not os.path.exists(pdf_path):
        logger.error(f"File not found: {pdf_path}")
        return ""

    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            logger.info(f"Processing {len(pdf.pages)} pages from {pdf_path}")
            for page in tqdm(pdf.pages, desc="Extracting pages"):
                page_text = page.extract_text() or ""
                text += f"\n{page_text}\n"
    except Exception as e:
        logger.error(f"Error reading {pdf_path}: {e}")
    return text.strip()


# ---------------------- Clean & Trim Text ---------------------------
def preprocess_text(text):
    # Remove PAGE markers and Gazette headers/footers
    text = re.sub(r'\[PAGE\s*\d+\]', '', text, flags=re.IGNORECASE)
    text = re.sub(r'THE\s*GAZETTE\s*OF\s*INDIA\s*EXTRAORDINARY\s*\[.*?\]', '', text, flags=re.IGNORECASE)
    text = re.sub(r'[_\-–—=]{5,}', '', text)
    text = re.sub(r'\b(PART\s*II|Hkkx II — \[k\.M 1|EXTRAORDINARY|vlk/kkj\.k|PUBLISHED BY AUTHORITY)\b.*', '', text, flags=re.IGNORECASE)

    # Normalize spaces and fix hyphenated line breaks
    text = re.sub(r'\n{3,}', '\n\n', text)  # Remove excessive newlines
    text = re.sub(r'\s+', ' ', text)  # Normalize all spaces
    text = re.sub(r'([a-z])- *\n *([a-z])', r'\1\2', text, flags=re.IGNORECASE)  # Hyphenation
    text = re.sub(r'([^\n])\n([^\n])', r'\1 \2', text)  # Newline in middle of sentence
    # Pre-normalizing possible inline section number issues
    #text = re.sub(r'(?<!\n)(\d{1,3}[A-Z]?\.)\s', r'\n\1 ', text)

    # Trim to start from "CHAPTER I" or "1."
    chapter_1_index = re.search(r'(CHAPTER\s*I\b)', text, re.IGNORECASE)
    if chapter_1_index:
        text = text[chapter_1_index.start():]
        logger.info("✅ Trimmed text to start from 'CHAPTER I'.")
    else:
        section_1_index = re.search(r'^\s*1\.\s', text, re.MULTILINE)
        if section_1_index:
            text = text[section_1_index.start():]
            logger.warning("⚠️ Could not find 'CHAPTER I', starting from 'Section 1' instead.")
        else:
            logger.warning("⚠️ Could not find 'CHAPTER I' or 'Section 1'. Check document formatting.")

    return text.strip()


# ---------------------- Split Sections ---------------------------
def split_sections_by_number(text, statute_name):
    """
    Split sections based on section numbers like '1. (1) ...' appearing inline or at fresh line.
    """
    text = re.sub(r'(?<!\n)(\d{1,3}[A-Z]?\.)\s*\(1\)', r'\n\1 (1)', text)

    # Regex to capture sections whether inline or newline
    pattern = (
        r'(?:^|\n|\s)'                 # Start from line start or inline after space/newline
        r'(\d{1,3}[A-Z]?)\.\s*'       # Section number like 1. or 36A.
        r'((?:.|\n)*?)'               # Content non-greedy until next section
        r'(?=\n\d{1,3}[A-Z]?\.\s|\s\d{1,3}[A-Z]?\.\s|\Z)'  # Stop before next section or end
    )

    matches = re.findall(pattern, text, re.MULTILINE)
    
    if not matches:
        logger.error("❌ No sections found. Please check formatting.")
        return []

    sections = []
    for sec_num, content in matches:
        num = sec_num.strip('.')
        # Filter out any wrong section numbers, assuming max 358
        if num.isdigit() and int(num) > 358:
            continue  # Skip beyond valid sections

        # Strip unwanted leading/trailing whitespace
        content = content.strip()
        if not content:
            continue  # Skip empty contents

        sections.append({
            "section_number": num,
            "content": content,
            "statute": statute_name
        })

    logger.info(f"✅ Extracted {len(sections)} valid sections for {statute_name}.")
    return sections


# ---------------------- Main Pipeline ---------------------------
def process_statute(pdf_path, statute_name, output_dir):
    logger.info(f"📄 Processing file: {pdf_path}")
    raw_text = extract_text_from_pdf(pdf_path)
    if not raw_text:
        logger.error("❌ No text extracted from PDF. Skipping file.")
        return

    # Preprocess text to clean it first
    clean_text = preprocess_text(raw_text)
    raw_output_path = os.path.join(output_dir, f"{Path(pdf_path).stem}_raw.txt")
    with open(raw_output_path, 'w', encoding='utf-8') as f:
        f.write(clean_text)
    logger.info(f"✅ Saved cleaned raw text to: {raw_output_path}")

    # Split and process sections
    sections = split_sections_by_number(clean_text, statute_name)

    # Save final JSON output
    json_output_path = os.path.join(output_dir, f"{Path(pdf_path).stem}_sections.json")
    with open(json_output_path, 'w', encoding='utf-8') as f:
        json.dump(sections, f, ensure_ascii=False, indent=2)
    logger.info(f"✅ Final sections JSON saved to: {json_output_path}")


# ---------------------- Run ---------------------------
if __name__ == "__main__":
    output_dir = "extracted_statutes"
    os.makedirs(output_dir, exist_ok=True)
    files = [{'pdf': 'Dataset\Data_BNS_BNSS_BSA\Actual Law\BNS.pdf', 'name': 'Bharatiya Nyaya Sanhita'}]  # List all files here
    for file in files:
        process_statute(file['pdf'], file['name'], output_dir)
