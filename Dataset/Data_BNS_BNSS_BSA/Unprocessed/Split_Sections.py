import json
import os
import re
from transformers import AutoTokenizer

# ================== CONFIG ====================

# Base directory where files are located
base_path = r"D:\Legal-Document-Summarizer\Dataset\Data_BNS_BNSS_BSA"

# Mapping of input JSON files to their corresponding output JSON files
input_output_files = {
    r"Unprocessed\BNS_sections.json": r"Statutes\BNS_sections.json",
    r"Unprocessed\BNSS_sections.json": r"Statutes\BNSS_sections.json",
    r"Unprocessed\BSA_sections.json": r"Statutes\BSA_sections.json"
}

# Model configuration
model_name = "law-ai/InLegalBERT"
max_tokens = 510  # Safe limit for tokenization

# ==============================================

# Load tokenizer
tokenizer = AutoTokenizer.from_pretrained(model_name)


def split_into_sentences(text):
    """
    Splits the input text into sentences based on common sentence-ending punctuation.

    Args:
        text (str): The input text to split.

    Returns:
        list: A list of sentences.
    """
    sentence_endings = re.compile(r'(?<=[.!?])\s+')
    sentences = sentence_endings.split(text.strip())
    return [s for s in sentences if s]


def split_long_sentence(sentence, max_tokens=510):
    """
    Splits a long sentence into smaller parts without exceeding the max_tokens limit.

    Args:
        sentence (str): The sentence to split.
        max_tokens (int): The maximum number of tokens allowed per chunk.

    Returns:
        list: A list of smaller sentence chunks.
    """
    max_content_tokens = max_tokens - 2  # Reserve space for [CLS] and [SEP]
    words = sentence.split()
    sub_chunks = []
    current_chunk = ""
    current_length = 0

    for word in words:
        word_length = len(tokenizer.encode(word, add_special_tokens=False))

        if current_length + word_length > max_content_tokens:
            if current_chunk:
                sub_chunks.append(current_chunk.strip())
            current_chunk = word
            current_length = word_length
        else:
            current_chunk += " " + word
            current_length += word_length

    if current_chunk:
        sub_chunks.append(current_chunk.strip())

    return sub_chunks


def sentence_aware_split(content, max_tokens=510):
    """
    Splits content into chunks while preserving sentence boundaries and adhering to the max_tokens limit.

    Args:
        content (str): The content to split.
        max_tokens (int): The maximum number of tokens allowed per chunk.

    Returns:
        list: A list of content chunks.
    """
    sentences = split_into_sentences(content)
    chunks = []
    current_chunk = ""

    for sentence in sentences:
        sentence_tokens = len(tokenizer.encode(sentence, add_special_tokens=False))

        # If sentence itself is too long, split it
        if sentence_tokens > max_tokens:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""
            long_chunks = split_long_sentence(sentence, max_tokens)
            chunks.extend(long_chunks)
            continue

        # Check if adding sentence exceeds max_tokens
        temp_chunk = (current_chunk + " " + sentence).strip()
        temp_tokens = len(tokenizer.encode(temp_chunk, add_special_tokens=False))

        if temp_tokens > max_tokens:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence  # Start a new chunk
        else:
            current_chunk = temp_chunk

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks


def process_and_chunk_file(input_file_path, output_file_path):
    """
    Processes a JSON file containing sections, splits the content into chunks, and saves the result.

    Args:
        input_file_path (str): Path to the input JSON file.
        output_file_path (str): Path to the output JSON file.

    Returns:
        None
    """
    with open(input_file_path, 'r', encoding='utf-8') as f:
        sections = json.load(f)

    all_chunks = []
    for section in sections:
        section_number = section['section_number']
        content = section['content']
        statute = section['statute']

        chunks = sentence_aware_split(content, max_tokens=max_tokens)

        for idx, chunk in enumerate(chunks, start=1):
            all_chunks.append({
                "section_number": section_number,
                "chunk_number": idx,
                "content": chunk,
                "statute": statute
            })

    # Save final chunked file
    with open(output_file_path, 'w', encoding='utf-8') as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)

    # Token stats for debug
    max_len = max(len(tokenizer.encode(c['content'], add_special_tokens=False)) for c in all_chunks)
    min_len = min(len(tokenizer.encode(c['content'], add_special_tokens=False)) for c in all_chunks)
    avg_len = sum(len(tokenizer.encode(c['content'], add_special_tokens=False)) for c in all_chunks) / len(all_chunks)
    over_limit = sum(1 for c in all_chunks if len(tokenizer.encode(c['content'], add_special_tokens=False)) > max_tokens)

    print(f"Processed '{os.path.basename(input_file_path)}' — {len(sections)} sections split into {len(all_chunks)} chunks.")
    print(f"Stats — Max tokens: {max_len}, Min tokens: {min_len}, Avg tokens: {round(avg_len, 2)}, Over limit: {over_limit}/{len(all_chunks)}")
    print(f"Output saved to '{output_file_path}'\n")


# ==================== Main Runner ====================

if __name__ == "__main__":
    """
    Main entry point of the script. Processes all input files defined in the configuration
    and splits their content into chunks.
    """
    for input_filename, output_filename in input_output_files.items():
        input_path = os.path.join(base_path, input_filename)
        output_path = os.path.join(base_path, output_filename)

        process_and_chunk_file(input_path, output_path)

    print("✅ All files processed and chunked safely.")