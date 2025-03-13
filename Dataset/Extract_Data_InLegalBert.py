import os
import re
import json
import pandas as pd
import pdfplumber
from tqdm import tqdm
from collections import defaultdict

# Configuration parameters
INPUT_DIR = r'D:\Legal-Document-Summarizer\Dataset\Data_BNS_BNSS_BSA'
OUTPUT_DIR = r'D:\Legal-Document-Summarizer\Dataset'
MIN_CHUNK_WORDS = 20
MAX_CHUNK_LENGTH = 450 

# Create directories if they don't exist
os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

def extract_glossary_terms(text):
    """
    Extract terms and definitions from glossary documents.
    Enhanced pattern matching specifically for legal glossaries.
    """
    glossary_entries = []
    
    # Pattern for terms with multiple spaces or tabs as separators
    # This matches patterns like: "Abandonment                       giving up a legal right"
    tab_pattern = r'([A-Z][A-Za-z\s\-\(\)/]+?)\s{2,}([A-Za-z].*?)(?=\n[A-Z]|\Z)'
    
    # Try the tab/space separator pattern first (most common in legal glossaries)
    matches = re.findall(tab_pattern, text)
    if matches:
        for term, definition in matches:
            glossary_entries.append({
                'term': term.strip(), 
                'definition': definition.strip()
            })
    
    # If the above pattern didn't find anything, try these alternative patterns
    if not glossary_entries:
        # Multiple patterns to catch different glossary formats
        patterns = [
            # Standard format: TERM followed by definition on next line
            r'\n*([A-Z][A-Za-z\s\-\(\)/]+)\n+([^A-Z\n][\s\S]+?)(?=\n[A-Z]|\Z)',
            
            # Term with number: "1. TERM" format
            r'\n*(\d+\.\s*[A-Z][A-Za-z\s\-\(\)/]+)\n+([^0-9\.\n][\s\S]+?)(?=\n\d+\.|\Z)',
            
            # Format with quotes: "Term" means definition
            r'\n*["\']([A-Za-z\s\-\(\)/]+)["\'](?:\s+means|\s+refers to)\s+([^\n"\']+(?:\n(?!["\']).+)*)(?=\n["\']\w+|\Z)'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for term, definition in matches:
                glossary_entries.append({
                    'term': term.strip(), 
                    'definition': ' '.join(definition.strip().split())
                })
    
    # If we have very few entries, try a more aggressive approach
    if len(glossary_entries) < 5:
        # Look for terms followed by definitions (common legal format)
        lines = text.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue
                
            # Check if this looks like an entry (term at start, no period at end)
            if (line[0:1].isupper() and not line.endswith('.')
                and len(line.split()) <= 5  # Terms are usually short
                and i + 1 < len(lines)):
                
                # Check if next line looks like a definition (starts lowercase or with "the"/"a")
                next_line = lines[i+1].strip()
                if (next_line and (next_line[0:1].islower() 
                                  or next_line.startswith('The ')
                                  or next_line.startswith('A '))):
                    glossary_entries.append({
                        'term': line,
                        'definition': next_line
                    })
                    i += 2
                else:
                    i += 1
            else:
                i += 1
    
    # Remove duplicates while preserving order
    unique_entries = []
    seen_terms = set()
    for entry in glossary_entries:
        if entry['term'] not in seen_terms:
            seen_terms.add(entry['term'])
            unique_entries.append(entry)
    
    return unique_entries

def process_pdfs():
    """
    Main processing function that:
    1. Identifies PDF files in input directory
    2. Determines document type based on filename
    3. Extracts and processes text content
    4. Handles glossary files specially
    5. Creates structured dataset in CSV and JSONL formats
    """
    pdf_files = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith('.pdf')]
    if not pdf_files:
        print("No PDF files found.")
        return

    all_chunks, all_metadata, all_glossaries = [], [], []
    stats = defaultdict(int)
    print(f"Found {len(pdf_files)} PDFs in {INPUT_DIR}")

    # Force creation of a separate glossary file
    glossary_found = False

    for pdf_file in tqdm(pdf_files, desc="🔄 Processing PDFs"):
        pdf_path = os.path.join(INPUT_DIR, pdf_file)
        doc_type = "Unknown"
        if any(x in pdf_file.lower() for x in ["bns", "bharatiya nyay", "nyay"]):
            doc_type = "BNS"
        elif any(x in pdf_file.lower() for x in ["bnss", "nagarik", "suraksha"]):
            doc_type = "BNSS"
        elif any(x in pdf_file.lower() for x in ["bsa", "sakshya"]):
            doc_type = "BSA"

        text = extract_text_with_tables(pdf_path)
        if text:
            # Check if this could be a glossary (either by filename or content)
            is_glossary = "glossary" in pdf_file.lower() or "definitions" in pdf_file.lower()
                
            if is_glossary:
                glossary_found = True
                glossary = extract_glossary_terms(text)
                if glossary:  # Only add if terms were actually found
                    all_glossaries.extend(glossary)
                    print(f"Extracted {len(glossary)} glossary terms from {pdf_file}")
                else:
                    print(f"No glossary terms found in {pdf_file} despite being identified as a glossary")
            else:
                chunks, metadata = process_text(text, f"{doc_type}_{pdf_file}")
                stats[doc_type] += len(chunks)
                all_chunks.extend(chunks)
                all_metadata.extend(metadata)

    # Always create a glossary.jsonl file, even if empty
    export_to_jsonl(all_glossaries, os.path.join(OUTPUT_DIR, "glossary.jsonl"))
    if all_glossaries:
        print(f"Combined glossary extracted with {len(all_glossaries)} terms → glossary.jsonl")
    else:
        print("No glossary terms found. Empty glossary.jsonl file created.")

    # Create dataset for other documents
    data = [
        {"id": i, "text": chunk, "source": meta["source"],
         "doc_type": meta["source"].split("_")[0] if meta["source"].split("_")[0] != 'Unknown' else 'Misc',
         "chapter": meta["chapter"], "section": meta["section"], "length": len(chunk.split())}
        for i, (chunk, meta) in enumerate(zip(all_chunks, all_metadata))
    ]

    if data:
        df = pd.DataFrame(data)
        df.to_csv(os.path.join(OUTPUT_DIR, "legal_dataset.csv"), index=False)
        export_to_jsonl(data, os.path.join(OUTPUT_DIR, "legal_dataset.jsonl"))
        print(f"Dataset created with {len(df)} chunks. CSV and JSONL saved.")
        print(stats)


def extract_text_with_tables(pdf_path):
    """
    Extract text and tables from PDF files using pdfplumber.
    Removes headers/footers and preserves table structures.

    Args:
        pdf_path (str): Path to the PDF file

    Returns:
        str: Extracted text with table formatting
    """
    text_output = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            cropped_page = page.within_bbox((0, 50, page.width, page.height - 50))
            page_text = cropped_page.extract_text()
            if page_text:
                text_output += page_text + "\n\n"
            tables = page.extract_tables()
            for table in tables:
                text_output += "[TABLE]\n"
                for row in table:
                    formatted_row = "\t".join(cell.strip() if cell else '' for cell in row)
                    text_output += formatted_row + "\n"
                text_output += "[/TABLE]\n\n"
    return text_output

def split_large_paragraph(para, max_length=MAX_CHUNK_LENGTH):
    """
    Split large paragraphs into smaller chunks based on sentence boundaries.
    Uses an overlapping window approach for better context preservation.

    Args:
        para (str): Paragraph text
        max_length (int): Maximum number of words per chunk

    Returns:
        list: List of smaller chunks
    """
    sentences = re.split(r'(?<=[.!?])\s+', para)
    chunks, current_chunk = [], ""
    
    # For very short paragraphs, no need to split
    if len(para.split()) <= max_length:
        return [para]
        
    # For longer paragraphs, use sliding window with overlap
    overlap_words = min(50, max_length // 4)  # 25% overlap, max 50 words
    
    for sentence in sentences:
        sentence_words = len(sentence.split())
        
        # Skip extremely long sentences by force-splitting them
        if sentence_words > max_length:
            words = sentence.split()
            for i in range(0, len(words), max_length - overlap_words):
                chunk = ' '.join(words[i:i + max_length])
                if len(chunk.split()) >= MIN_CHUNK_WORDS:
                    chunks.append(chunk)
            continue
            
        # Normal case - add sentence to current chunk
        if len(current_chunk.split()) + sentence_words <= max_length:
            current_chunk += " " + sentence if current_chunk else sentence
        else:
            # Add current chunk if it's not too short
            if current_chunk and len(current_chunk.split()) >= MIN_CHUNK_WORDS:
                chunks.append(current_chunk.strip())
            
            # Start new chunk with a bit of overlap for context
            overlap_point = current_chunk.split()
            if len(overlap_point) > overlap_words:
                overlap_text = ' '.join(overlap_point[-overlap_words:])
                current_chunk = overlap_text + " " + sentence
            else:
                current_chunk = sentence
    
    # Add the last chunk
    if current_chunk and len(current_chunk.split()) >= MIN_CHUNK_WORDS:
        chunks.append(current_chunk.strip())
        
    return chunks

def process_text(text, doc_source):
    """
    Process extracted text to detect chapters/sections and create structured chunks.
    Enhanced patterns for legal document structure detection.

    Args:
        text (str): Raw extracted text
        doc_source (str): Document source

    Returns:
        tuple: List of text chunks and metadata
    """
    try:
        # Basic text cleaning
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'[^\x00-\x7F]+', ' ', text)
        
        # Enhanced patterns for chapter and section detection
        chapter_patterns = [
            # Roman numerals (I, II, III, etc.)
            r'\b(?:CHAPTER|Chapter|CHP\.?)\s+([IVXLCDM]+)\b',
            # Arabic numerals (1, 2, 3, etc.)
            r'\b(?:CHAPTER|Chapter|CHP\.?)\s+(\d+[A-Z]?)\b',
            # Named chapters
            r'\bCHAPTER\s+([A-Z][A-Z\s]+)(?:\n|\s+-)',
            # Just numbered (1., 2., etc.)
            r'^\s*(\d+\.)\s+[A-Z]'
        ]
        
        section_patterns = [
            # Standard section format
            r'\b(?:Section|SECTION|Sec\.|SEC\.|Clause|CLAUSE)\s+(\d+[A-Z]?(?:\(\d+\))*(?:\([a-z]\))*)\b',
            # Just the number with dot
            r'^\s*(\d+\.\d+\.?)\s+[A-Z]',
            # Articles
            r'\b(?:Article|ARTICLE)\s+(\d+[A-Z]?)\b',
            # Special formats like "§123"
            r'(?:§|Sec\.|Section)\s*(\d+(?:\.\d+)*(?:\([a-z0-9]\))*)'
        ]
        
        # Extract all chapters and sections with their positions
        chapters = {}
        for pattern in chapter_patterns:
            for m in re.finditer(pattern, text):
                chapters[m.start()] = m.group(1)
                
        sections = {}
        for pattern in section_patterns:
            for m in re.finditer(pattern, text):
                sections[m.start()] = m.group(1)
        
        # Get paragraphs by splitting on double newlines
        paragraphs = []
        for p in text.split('\n\n'):
            if p.strip():
                # Further split by single newlines if they look like paragraph breaks
                sub_paras = [sp for sp in p.split('\n') if sp.strip()]
                paragraphs.extend(sub_paras)
        
        chunks, metadata = [], []
        current_chapter, current_section = "Unknown", "Unknown"
        
        for para in paragraphs:
            para_pos = text.find(para)
            
            # Update current chapter if we've passed a chapter marker
            for pos in sorted(chapters.keys()):
                if pos <= para_pos:
                    current_chapter = chapters[pos]
            
            # Update current section if we've passed a section marker
            for pos in sorted(sections.keys()):
                if pos <= para_pos:
                    current_section = sections[pos]
            
            # Check if this paragraph itself is a chapter or section header
            is_header = False
            for pattern in chapter_patterns + section_patterns:
                if re.match(pattern, para.strip()):
                    is_header = True
                    break
            
            # Skip headers as standalone chunks
            if is_header and len(para.split()) < MIN_CHUNK_WORDS:
                continue
                
            # Split large paragraphs
            for sub_chunk in split_large_paragraph(para):
                if len(sub_chunk.split()) >= MIN_CHUNK_WORDS:
                    chunks.append(sub_chunk)
                    metadata.append({
                        "source": doc_source, 
                        "chapter": current_chapter, 
                        "section": current_section
                    })
        
        return chunks, metadata
    except Exception as e:
        print(f"Error processing text for {doc_source}: {e}")
        return [], []

def export_to_jsonl(data, output_path):
    """
    Export structured data to JSONL format.

    Args:
        data (list): List of dictionaries
        output_path (str): Path to save JSONL
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')

if __name__ == "__main__":
    process_pdfs()