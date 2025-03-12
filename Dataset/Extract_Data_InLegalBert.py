"""
Legal Document PDF Processor
Requirements:
- pdfplumber
- pandas
- tqdm
- re (regex)
- json
- os
- collections (defaultdict)

Usage:
1. Place PDF files in the INPUT_DIR directory
2. Run the script: python script_name.py
3. Processed data will be saved to OUTPUT_DIR
"""

import os
import re
import json
import pandas as pd
import pdfplumber
from tqdm import tqdm
from collections import defaultdict

# Configuration parameters
INPUT_DIR = 'Dataset/Data_BNS_BNSS_BSA'  # Directory containing source PDF files
OUTPUT_DIR = 'Dataset'                   # Directory for output files
MIN_CHUNK_WORDS = 20                     # Minimum word count for a text chunk
MAX_CHUNK_LENGTH = 1000                  # Maximum character length for a text chunk

# Create output directory if it doesn't exist
os.makedirs(OUTPUT_DIR, exist_ok=True)

def extract_text_with_tables(pdf_path):
    """
    Extract text and detect tables from a PDF file using pdfplumber.
    
    This function:
    1. Opens each page of the PDF
    2. Crops pages to remove headers/footers
    3. Extracts main text content
    4. Detects and formats tables with special markup
    
    Args:
        pdf_path (str): Path to the PDF file
        
    Returns:
        str: Extracted text with table formatting
    """
    text_output = ""

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            # Crop to remove headers and footers (50px margins)
            # This helps eliminate repeating page numbers, document titles, etc.
            cropped_page = page.within_bbox((0, 50, page.width, page.height - 50))
            page_text = cropped_page.extract_text()
            if page_text:
                text_output += page_text + "\n\n"

            # Extract tables without cropping to preserve complete table structure
            # Tables often extend to edges and might be cut off if cropped
            tables = page.extract_tables()
            for table in tables:
                text_output += "[TABLE]\n"  # Table start marker
                for row in table:
                    # Format each row with tab separators for readability
                    formatted_row = "\t".join(cell.strip() if cell else '' for cell in row)
                    text_output += formatted_row + "\n"
                text_output += "[/TABLE]\n\n"  # Table end marker

    return text_output

def process_text(text, doc_source):
    """
    Process extracted text to identify document structure and create properly sized chunks.
    
    This function:
    1. Cleans and normalizes text
    2. Detects chapter and section markers
    3. Splits text into appropriate chunks while preserving metadata
    4. Handles tables as special cases
    
    Args:
        text (str): Raw text extracted from PDF
        doc_source (str): Source identifier for the document
        
    Returns:
        tuple: (list of text chunks, list of corresponding metadata)
    """
    try:
        # Clean and normalize text
        text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
        text = re.sub(r'[^\x00-\x7F]+', ' ', text)  # Remove non-ASCII characters

        # Regular expressions to detect document structure
        # Matches various formats of chapter headings (Roman numerals, digits)
        chapter_pattern = r'\b(?:CHAPTER|Chapter|CHP)\s+([IVXLCDM]+|\d+)\b'
        # Matches section formats like "Section 1.2" or "SEC. 3(1)(a)"
        section_pattern = r'\b(?:Section|SECTION|Sec\.|SEC\.|Clause|CLAUSE)\s+(\d+[A-Z]?(\(\d+\))*(\([a-z]\))?)\b'

        # Find all chapters and sections with their positions in text
        chapters = {m.start(): m.group(1) for m in re.finditer(chapter_pattern, text)}
        sections = {m.start(): m.group(1) for m in re.finditer(section_pattern, text)}

        # Split text into paragraphs
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        chunks, metadata = [], []
        current_chapter, current_section = "Unknown", "Unknown"

        # Process each paragraph
        for para in paragraphs:
            # Update current chapter and section based on position in document
            for pos in sorted(chapters.keys()):
                if pos <= text.find(para):
                    current_chapter = chapters[pos]
            for pos in sorted(sections.keys()):
                if pos <= text.find(para):
                    current_section = sections[pos]

            # Special handling for tables - keep them intact
            if '[TABLE]' in para:
                chunks.append(para.strip())  # Always keep tables as a single chunk
                metadata.append({"source": doc_source, "chapter": current_chapter, "section": current_section})
            # Split large paragraphs that exceed maximum length
            elif len(para) > MAX_CHUNK_LENGTH:
                # Split on sentence boundaries to maintain coherence
                sentences = re.split(r'(?<=[.!?])\s+', para)
                current_chunk = ""
                for sentence in sentences:
                    # Add sentence to current chunk if within size limit
                    if len(current_chunk) + len(sentence) <= MAX_CHUNK_LENGTH:
                        current_chunk += " " + sentence if current_chunk else sentence
                    # Otherwise, save current chunk and start a new one
                    else:
                        if len(current_chunk.split()) > MIN_CHUNK_WORDS:  # Only keep if meets minimum size
                            chunks.append(current_chunk.strip())
                            metadata.append({"source": doc_source, "chapter": current_chapter, "section": current_section})
                        current_chunk = sentence
                # Save the final chunk if it meets minimum size
                if len(current_chunk.split()) > MIN_CHUNK_WORDS:
                    chunks.append(current_chunk.strip())
                    metadata.append({"source": doc_source, "chapter": current_chapter, "section": current_section})
            # Normal-sized paragraphs
            else:
                if len(para.split()) > MIN_CHUNK_WORDS:  # Only keep if meets minimum size
                    chunks.append(para.strip())
                    metadata.append({"source": doc_source, "chapter": current_chapter, "section": current_section})

        return chunks, metadata
    except Exception as e:
        print(f"Error processing text for {doc_source}: {e}")
        return [], []

def export_to_jsonl(data, output_path):
    """
    Export data to JSONL (JSON Lines) format.
    
    Each line in the output file is a valid JSON object.
    
    Args:
        data (list): List of dictionaries to export
        output_path (str): Path to save the JSONL file
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')

def extract_glossary_terms(text):
    """
    Extract terms and definitions from glossary documents.
    
    Uses regex pattern matching to identify term-definition pairs in the format:
    TERM
    Definition text that may span multiple lines
    
    Args:
        text (str): Raw text from glossary document
        
    Returns:
        list: List of dictionaries with 'term' and 'definition' keys
    """
    glossary_entries = []
    # Pattern matches capitalized terms followed by definitions
    # Term is uppercase first letter followed by text, then definition follows on next line(s)
    # until another term is found or end of text
    pattern = r'\n*([A-Z][A-Za-z\s\-\(\)/]+)\n+([^A-Z\n][\s\S]+?)(?=\n[A-Z]|\Z)'
    matches = re.findall(pattern, text)
    for term, definition in matches:
        glossary_entries.append({
            'term': term.strip(),
            'definition': ' '.join(definition.strip().split())  # Normalize whitespace
        })
    return glossary_entries

def process_pdfs():
    """
    Main processing function that:
    1. Identifies PDF files in input directory
    2. Extracts and processes text based on file type
    3. Handles glossary files specially
    4. Exports processed data to CSV and JSONL formats
    5. Reports statistics on processing results
    """
    # Find all PDF files in input directory
    pdf_files = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith('.pdf')]
    if not pdf_files:
        print("No PDF files found.")
        return

    all_chunks, all_metadata = [], []
    stats = defaultdict(int)  # Track statistics by document type
    print(f"Found {len(pdf_files)} PDFs in {INPUT_DIR}")

    # Process each PDF file
    for pdf_file in tqdm(pdf_files, desc="🔄 Processing PDFs"):
        pdf_path = os.path.join(INPUT_DIR, pdf_file)
        
        # Determine document type based on filename
        doc_type = "Unknown"
        if "bns" in pdf_file.lower(): doc_type = "BNS"
        elif "bnss" in pdf_file.lower(): doc_type = "BNSS"
        elif "bsa" in pdf_file.lower(): doc_type = "BSA"

        # Extract text from PDF
        text = extract_text_with_tables(pdf_path)
        if text:
            # Special handling for glossary files
            if "glossary" in pdf_file.lower():
                glossary = extract_glossary_terms(text)
                export_to_jsonl(glossary, os.path.join(OUTPUT_DIR, "glossary.jsonl"))
                print(f"Glossary extracted → glossary.jsonl")
            # Standard processing for non-glossary files
            else:
                chunks, metadata = process_text(text, f"{doc_type}_{pdf_file}")
                stats[doc_type] += len(chunks)  # Track chunks per document type
                all_chunks.extend(chunks)
                all_metadata.extend(metadata)

    # Create dataset with all extracted chunks and metadata
    data = [{"id": i, 
             "text": chunk, 
             "source": meta["source"], 
             "doc_type": meta["source"].split("_")[0],  # Extract doc type from source
             "chapter": meta["chapter"], 
             "section": meta["section"], 
             "length": len(chunk.split())}  # Add word count
            for i, (chunk, meta) in enumerate(zip(all_chunks, all_metadata))]

    # Export dataset if data was extracted
    if data:
        # Save as both CSV and JSONL for flexibility
        df = pd.DataFrame(data)
        df.to_csv(os.path.join(OUTPUT_DIR, "legal_dataset.csv"), index=False)
        export_to_jsonl(data, os.path.join(OUTPUT_DIR, "legal_dataset.jsonl"))
        print(f"Dataset created with {len(df)} chunks. CSV and JSONL saved.")
        print(stats)  # Print statistics by document type

# Run script if executed directly
if __name__ == "__main__":
    process_pdfs()