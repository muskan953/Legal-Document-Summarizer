import os
import re
import pandas as pd
import fitz  # PyMuPDF for handling PDFs
from tqdm import tqdm
from collections import defaultdict

# Configuration
INPUT_DIR = 'Dataset/Data_BNS_BNSS_BSA'  # Directory containing PDFs
OUTPUT_DIR = 'Dataset'  # Directory for output files
MIN_CHUNK_WORDS = 20  # Minimum words per text chunk
MAX_CHUNK_LENGTH = 1000  # Maximum characters per chunk

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Function to extract text from a PDF file
def extract_text_from_pdf(pdf_path):

    """
    Extracts text from a given PDF file.

    Args:
        pdf_path (str): Path to the PDF file.

    Returns:
        str or None: Extracted text if successful, None if an error occurs or if the PDF is empty.
    """

    try:
        text = ""
        with fitz.open(pdf_path) as doc:
            total_pages = len(doc)
            start_page = min(5, total_pages - 1)  # Skip cover pages

            for page_num in range(start_page, total_pages):
                page = doc[page_num]
                page_text = page.get_text("text")
                if page_text:
                    text += f"[Page {page_num + 1}]\n{page_text}\n\n"

        if not text.strip():
            print(f"Warning: No text extracted from {pdf_path}")
            return None  # Skip empty files

        return text  
    except Exception as e:
        print(f"Error extracting text from {pdf_path}: {e}")
        return None

# Function to process extracted text and chunk it into smaller segments
def process_text(text, doc_source):

    """
    Cleans, structures, and chunks legal text into smaller segments.

    Args:
        text (str): The extracted text from a PDF.
        doc_source (str): The document's name or source for metadata tagging.

    Returns:
        tuple: A list of text chunks and a list of corresponding metadata dictionaries.
    """

    try:
        # Normalize whitespace and remove non-ASCII characters
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'[^\x00-\x7F]+', ' ', text)

        # Patterns to detect chapters and sections in legal documents
        chapter_pattern = r'\b(?:CHAPTER|Chapter)\s+([IVXLCDM]+|\d+)\b'
        section_pattern = r'\b(?:Section|SECTION|Sec\.|SEC\.)\s+(\d+[A-Z]?(\.\d+)*)\b'

        # Map positions of chapters and sections within the text
        chapters = {m.start(): m.group(1) for m in re.finditer(chapter_pattern, text)}
        sections = {m.start(): m.group(1) for m in re.finditer(section_pattern, text)}

        # Split text into paragraphs
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        chunks, metadata = [], []
        current_chapter, current_section = "Unknown", "Unknown"

        # Iterate through paragraphs and assign chapter/section metadata
        for para in paragraphs:
            # Determine chapter and section for the current paragraph
            for pos in sorted(chapters.keys()):
                if pos <= text.find(para):
                    current_chapter = chapters[pos]
            for pos in sorted(sections.keys()):
                if pos <= text.find(para):
                    current_section = sections[pos]

            # Chunking logic
            if len(para) > MAX_CHUNK_LENGTH:
                sentences = re.split(r'(?<=[.!?])\s+', para)
                current_chunk = ""

                for sentence in sentences:
                    if len(current_chunk) + len(sentence) <= MAX_CHUNK_LENGTH:
                        current_chunk += " " + sentence if current_chunk else sentence
                    else:
                        if len(current_chunk.split()) > MIN_CHUNK_WORDS:
                            chunks.append(current_chunk.strip())
                            metadata.append({"source": doc_source, "chapter": current_chapter, "section": current_section})
                        current_chunk = sentence  

                if len(current_chunk.split()) > MIN_CHUNK_WORDS:
                    chunks.append(current_chunk.strip())
                    metadata.append({"source": doc_source, "chapter": current_chapter, "section": current_section})
            else:
                if len(para.split()) > MIN_CHUNK_WORDS:
                    chunks.append(para.strip())
                    metadata.append({"source": doc_source, "chapter": current_chapter, "section": current_section})

        return chunks, metadata
    except Exception as e:
        print(f"Error processing text for {doc_source}: {e}")
        return [], []  

# Main function to process all PDFs in the input directory
def process_pdfs():

    """
    Processes all PDFs in the INPUT_DIR and extracts structured legal text data.

    Outputs:
        - A CSV file containing extracted text chunks and metadata.
        - A sample CSV file with a small subset of data.
        - A summary text file with extraction statistics.
    """

    try:
        # Get list of all PDFs in the directory
        pdf_files = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith('.pdf')]
        if not pdf_files:
            print("No PDF files found in the input directory.")
            return

        print(f"Found {len(pdf_files)} PDF files in {INPUT_DIR}")
        all_chunks, all_metadata, stats = [], [], defaultdict(int)

        # Process each PDF file
        for pdf_file in tqdm(pdf_files, desc="🔄 Processing PDFs"):
            pdf_path = os.path.join(INPUT_DIR, pdf_file)
            
            # Determine document type (BNS, BNSS, BSA) based on filename
            doc_type = "Unknown"
            if "bns" in pdf_file.lower() and "bnss" not in pdf_file.lower():
                doc_type = "BNS"
            elif "bnss" in pdf_file.lower() or "nagarik" in pdf_file.lower():
                doc_type = "BNSS"
            elif "bsa" in pdf_file.lower() or "sakshya" in pdf_file.lower():
                doc_type = "BSA"

            text = extract_text_from_pdf(pdf_path)
            if text:
                chunks, metadata = process_text(text, f"{doc_type}_{pdf_file}")
                stats[doc_type] += len(chunks)
                all_chunks.extend(chunks)
                all_metadata.extend(metadata)

        # Create DataFrame with extracted data
        data = [{"id": i, "text": chunk, "source": meta["source"], "doc_type": meta["source"].split("_")[0], 
                 "chapter": meta["chapter"], "section": meta["section"], "length": len(chunk.split())}
                for i, (chunk, meta) in enumerate(zip(all_chunks, all_metadata))]

        df = pd.DataFrame(data)

        if not df.empty:
            output_file = os.path.join(OUTPUT_DIR, "legal_dataset.csv")
            df.to_csv(output_file, index=False)
            print(f"Dataset created with {len(df)} text chunks → {output_file}")

            # Save a sample subset
            sample_file = os.path.join(OUTPUT_DIR, "sample_data.csv")
            df.sample(min(10, len(df))).to_csv(sample_file, index=False)
            print(f"Sample dataset saved → {sample_file}")

            # Save summary statistics
            summary_file = os.path.join(OUTPUT_DIR, "extraction_summary.txt")
            with open(summary_file, "w") as f:
                f.write(f"Extracted {len(df)} text chunks from {len(pdf_files)} PDFs\n")
                for doc_type, count in df['doc_type'].value_counts().items():
                    f.write(f"{doc_type}: {count} chunks\n")
            print(f"Summary saved → {summary_file}")

        print("Processing completed successfully!")

    except Exception as e:
        print(f"Critical error in process_pdfs: {e}")

# Execute the code
if __name__ == "__main__":
    process_pdfs()
