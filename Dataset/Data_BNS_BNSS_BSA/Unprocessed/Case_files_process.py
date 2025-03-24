import os
import re
import json
import fitz  # PyMuPDF

# Updated regex patterns with capturing groups for an optional section number.
patterns = {
    "BNS": re.compile(
        r'[\(\[]?(?:Offence\s+under\s+section\s+(\d+)\s+|as\s+per\s+provisions\s+in\s+)?'
        r'((?:BNS)|(?:B\.N\.S\.)|(?:bhartiya nyaya sanhita)|(?:Bhartiya Nyaya Sanhita)|(?:BHARTIYA NYAYA SANHITA))'
        r'[\)\]]?',
        0  # case sensitive
    ),
    "BNSS": re.compile(
        r'[\(\[]?(?:Offence\s+under\s+section\s+(\d+)\s+|as\s+per\s+provisions\s+in\s+)?'
        r'((?:BNSS)|(?:B\.N\.S\.S\.)|(?:bhariya nagrik suraksha sanhita)|(?:Bhariya Nagrik Suraksha Sanhita)|(?:BHARIYA NAGRIK SURAKSHA SANHITA))'
        r'[\)\]]?',
        0
    ),
    "BSA": re.compile(
        r'[\(\[]?(?:Offence\s+under\s+section\s+(\d+)\s+|as\s+per\s+provisions\s+in\s+)?'
        r'((?:BSA)|(?:B\.S\.A\.)|(?:bhartiya shakshya adhiniyam)|(?:Bhartiya Shakshya Adhiniyam)|(?:BHARTIYA SHAKSHYA ADHINIYAM))'
        r'[\)\]]?',
        0
    )
}

def clean_text(text):
    """
    Remove URLs and any mention of 'indiankanoon' or 'Indian Kanoon' (case insensitive),
    remove isolated page numbers, and collapse extra whitespace.
    """
    text = re.sub(r'https?://\S*indiankanoon\S*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\bindiankanoon\b', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\bIndian\s+Kanoon\b', '', text, flags=re.IGNORECASE)
    # Remove lines that are only numbers (often page numbers)
    text = re.sub(r'(?m)^\s*\d+\s*$', '', text)
    # Replace newlines with spaces and collapse multiple spaces.
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def extract_text_from_pdf(pdf_path):
    """Extract full text from a PDF using PyMuPDF."""
    try:
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text() + "\n"
        doc.close()
        return clean_text(text)
    except Exception as e:
        print(f"Error processing {pdf_path}: {e}")
        return ""

def extract_metadata(text):
    """
    Extract minimal metadata from the text.
    Searches for a date in common formats (including dd Month, yyyy)
    and looks for a mention of a court.
    """
    metadata = {}
    date_regex = (
        r'(\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|'
        r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b|'
        r'\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December),?\s+\d{4}\b)'
    )
    date_match = re.search(date_regex, text)
    if date_match:
        metadata['judgment_date'] = date_match.group(0)
    court_match = re.search(r'\b(?:Supreme Court|High Court|District Court)[^,\n]*', text)
    if court_match:
        metadata['court'] = court_match.group(0)
    return metadata

def extract_case_id(text, default_id):
    """
    Extract a case id from the text using regex.
    It attempts to match patterns like:
      - "PETITION No. - 6601 of 2024"
      - "BA1 No.2007 of 2024"
      - "No. 6601 of 2024"
    The prefix is optional.
    Iterates over all matches and ignores any match where the preceding text (last 50 characters)
    ends with "Citation" (optionally followed by a colon and spaces).
    """
    pattern = re.compile(
        r'\b((?:[A-Z0-9]+(?:\s*[/-]\s*[A-Z0-9]+)?\s+))?No\.?\s*-?\s*(\d+)(?:\s+of\s+(\d{4}))?\b',
        re.IGNORECASE
    )
    for match in pattern.finditer(text):
        start = match.start()
        preceding_text = text[max(0, start-50):start]
        if re.search(r'Citation\s*:?\s*$', preceding_text, re.IGNORECASE):
            continue
        prefix = match.group(1) or ""
        number = match.group(2)
        year = match.group(3) if match.group(3) else ""
        prefix = prefix.strip() if prefix else ""
        if prefix:
            case_id = f"{prefix} No. - {number}"
        else:
            case_id = f"No. - {number}"
        if year:
            case_id += f" of {year}"
        return case_id
    return default_id

def find_statute_mentions(text):
    """
    Split the text into sentences and search each sentence for mentions of the target statutes
    using regex-only matching.
    The context field is the entire cleaned sentence in which the section(s) are mentioned.
    Also uses an additional regex to extract a detailed section reference, capturing multiple
    section numbers (e.g., "221,132, 352 and 351(3)").
    """
    mentions = []
    section_pattern = re.compile(
        r'\b(?:Section(?:s)?|Sec\.?)\s*([0-9]+(?:\([^)]+\))?(?:\s*,\s*[0-9]+(?:\([^)]+\))?)*(?:\s*(?:and)\s*[0-9]+(?:\([^)]+\))?)?)'
    )
    sentences = re.split(r'(?<=[.!?])\s+', text)
    for sentence in sentences:
        for statute, pattern in patterns.items():
            match = pattern.search(sentence)
            if match:
                sec_match = section_pattern.search(sentence)
                section = ""
                if sec_match:
                    section = "Sections " + sec_match.group(1)
                mentions.append({
                    "statute": statute,
                    "section": section,
                    "context": sentence.strip()
                })
    return mentions

def process_pdfs(directory):
    """Process PDF files in the directory and extract case objects if a target statute is mentioned."""
    cases = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(".pdf"):
                pdf_path = os.path.join(root, file)
                text = extract_text_from_pdf(pdf_path)
                if not text:
                    continue
                metadata = extract_metadata(text)
                statute_mentions = find_statute_mentions(text)
                if statute_mentions:
                    case_id = extract_case_id(text, os.path.splitext(file)[0])
                    # Derive case title from filename: remove extension, remove trailing "_BNS", and remove anything starting with "_on".
                    filename = os.path.splitext(file)[0]
                    filename = re.sub(r'_on.*$', '', filename)
                    filename = filename.replace("_BNS", "").strip()
                    case_obj = {
                        "case_id": case_id,
                        "case_title": filename,
                        "judgment_date": metadata.get("judgment_date", ""),
                        "statute_mentions": statute_mentions
                    }
                    cases.append(case_obj)
    return cases

if __name__ == "__main__":
    
    input_output = {
        r"Legal-Document-Summarizer\Dataset\Data_BNS_BNSS_BSA\Unprocessed\BNS" : r"Legal-Document-Summarizer\Dataset\Data_BNS_BNSS_BSA\Case_Files\BNS_cases.json",
        r"Legal-Document-Summarizer\Dataset\Data_BNS_BNSS_BSA\Unprocessed\BNSS" : r"Legal-Document-Summarizer\Dataset\Data_BNS_BNSS_BSA\Case_Files\BNSS_cases.json",
        r"Legal-Document-Summarizer\Dataset\Data_BNS_BNSS_BSA\Unprocessed\BSA" : r"Legal-Document-Summarizer\Dataset\Data_BNS_BNSS_BSA\Case_Files\BSA_cases.json"
    }

    for input_directory, output_json in input_output.items():
        cases = process_pdfs(input_directory)
        print(f"Processed {len(cases)} case files with target statute mentions.")
    
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(cases, f, indent=2, ensure_ascii=False)
        print(f"Saved extracted data to {output_json}")
