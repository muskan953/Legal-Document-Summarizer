import os
import re
import json
import pdfplumber
import logging

def setup_logging():
    log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(console_handler)
    return logger

logger = setup_logging()

def extract_text_from_pdf(pdf_path, margin=50):
    if not os.path.exists(pdf_path):
        logger.error(f"File not found: {pdf_path}")
        return ""
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            logger.info(f"Processing {len(pdf.pages)} pages from {pdf_path}")
            for page in pdf.pages:
                # Crop out left/right margins by defining a bounding box.
                bbox = (margin, 0, page.width - margin, page.height)
                page_text = page.within_bbox(bbox).extract_text() or ""
                text += "\n" + page_text + "\n"
    except Exception as e:
        logger.error(f"Error reading {pdf_path}: {e}")
    return text.strip()

def preprocess_text(text):
    # Remove common page markers, headers or footers.
    text = re.sub(r'\[PAGE\s*\d+\]', '', text, flags=re.IGNORECASE)
    text = re.sub(r'THE\s+GAZETTE\s+OF\s+INDIA\s+EXTRAORDINARY.*?(?=\d)', '', text, flags=re.IGNORECASE)
    # Normalize whitespace to help mitigate OCR issues (run-on words, etc.)
    text = re.sub(r'\s+', ' ', text)
    return text

def extract_chapters(text):
    """
    Splits the text into chapters using markers like "CHAPTER I", "CHAPTERII", etc.
    Any text before the first chapter is labeled "Preliminary".
    """
    chapters = []
    # Updated pattern allows zero or more spaces between "CHAPTER" and the numeral.
    chapter_pattern = re.compile(r'(CHAPTER\s*[IVXLCDM]+)', re.IGNORECASE)
    splits = chapter_pattern.split(text)
    if splits and splits[0].strip():
        chapters.append(("Preliminary", splits[0].strip()))
    for i in range(1, len(splits), 2):
        chapter_title = splits[i].strip()
        chapter_text = splits[i+1].strip() if (i+1) < len(splits) else ""
        chapters.append((chapter_title, chapter_text))
    return chapters

def extract_sections(chapter_text, chapter_title, statute_name):
    sections = []
    # Use a regex that matches a number (1-3 digits) followed by a dot at a word boundary.
    section_pattern = re.compile(r'(?<!\S)(\d{1,3})\.\s*')
    matches = list(section_pattern.finditer(chapter_text))
    previous_section_num = 0
    for i, match in enumerate(matches):
        sec_num = match.group(1)
        current_num = int(sec_num)
        start_index = match.end()
        end_index = matches[i+1].start() if i+1 < len(matches) else len(chapter_text)
        content = chapter_text[start_index:end_index].strip()
        # If the current section number is less than or equal to the previous one,
        # assume this is an internal subheading/paragraph and merge its content.
        if current_num <= previous_section_num:
            if sections:
                sections[-1]["content"] += " " + content
            else:
                sections.append({
                    "section_number": sec_num,
                    "content": content,
                    "chapter": chapter_title,
                    "statute": statute_name
                })
            continue
        sections.append({
            "section_number": sec_num,
            "content": content,
            "chapter": chapter_title,
            "statute": statute_name
        })
        previous_section_num = current_num
    return sections

def extract_all_sections(text, statute_name):
    cleaned_text = preprocess_text(text)
    chapters = extract_chapters(cleaned_text)
    all_sections = []
    if not chapters:
        all_sections = extract_sections(cleaned_text, "Entire Document", statute_name)
    else:
        for chapter_title, chapter_text in chapters:
            sections = extract_sections(chapter_text, chapter_title, statute_name)
            all_sections.extend(sections)
    return all_sections

def process_statute(pdf_path, statute_name, output_dir):
    logger.info(f"📄 Processing file: {pdf_path}")
    raw_text = extract_text_from_pdf(pdf_path)
    if not raw_text:
        logger.error(f"❌ No text extracted from {pdf_path}. Skipping.")
        return
    sections = extract_all_sections(raw_text, statute_name)
    output_file = os.path.join(output_dir, f"{os.path.splitext(os.path.basename(pdf_path))[0]}_sections.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(sections, f, ensure_ascii=False, indent=2)
    logger.info(f"✅ Extracted {len(sections)} sections for {statute_name}.")
    logger.info(f"✅ Final sections JSON saved to: {output_file}")

if __name__ == "__main__":
    output_dir = "extracted_statutes"
    os.makedirs(output_dir, exist_ok=True)
    pdf_path = "Dataset/Data_BNS_BNSS_BSA/Actual Law/BNS.pdf"  # Update this path as needed.
    statute_name = "Bharatiya Nyaya Sanhita"
    process_statute(pdf_path, statute_name, output_dir)
