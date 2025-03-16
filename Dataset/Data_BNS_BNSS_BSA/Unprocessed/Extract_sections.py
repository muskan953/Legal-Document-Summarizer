import json
import os
import re

# ================== CONFIG ====================

# Base directory where files are located
base_path = r"D:\Legal-Document-Summarizer\Dataset\Data_BNS_BNSS_BSA"

# Mapping of input text files to their corresponding output JSON files and statute names
input_output_files = {
    r"Unprocessed\BNS.txt": (r"Unprocessed\BNS_sections.json", "Bharatiya Nyaya Sanhita"),
    r"Unprocessed\BNSS.txt": (r"Unprocessed\BNSS_sections.json", "Bharatiya Nagrik Suraksha Sanhita"),
    r"Unprocessed\BSA.txt": (r"Unprocessed\BSA_sections.json", "Bharatiya Suraksha Adhiniyam"),
}


# ==========Function to Clean the Content==========
def clean_content(text):
    """
    Cleans the input text by removing encoding artifacts, normalizing spaces, and fixing broken lines.

    Args:
        text (str): The raw text content to be cleaned.

    Returns:
        str: The cleaned text content.
    """
    # Remove encoding artifacts
    text = re.sub(r'[—”‘’ââââ¦â€“]', '', text)

    # Remove large empty space blocks
    text = re.sub(r'\n{5,}.*?(?=\n{2,}|\Z)', '', text, flags=re.DOTALL)

    # Normalize spaces and tabs
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r' +\n', '\n', text)

    # Fix broken lines
    text = re.sub(r'(?<!\n)\n(?!\n)', ' ', text)

    # Preserve paragraph breaks
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Fix spaces after section numbers or subsections
    text = re.sub(r'\(\d+\)\s*', lambda m: m.group(0).strip() + ' ', text)
    text = re.sub(r'\([a-z]\)\s*', lambda m: m.group(0).strip() + ' ', text)

    return text

# ==========Function to Extract and Clean Sections==========
def extract_and_clean_sections(input_file_path, output_file_path, statute_name):
    """
    Extracts sections from a legal document, cleans the content, and saves the result as a JSON file.

    Args:
        input_file_path (str): Path to the input text file.
        output_file_path (str): Path to the output JSON file.
        statute_name (str): Name of the statute being processed.

    Returns:
        None
    """
    with open(input_file_path, 'r', encoding='utf-8') as f:
        full_text = f.read()

    # Regex to detect sections like "4." at the start of lines
    section_pattern = re.compile(
        r'^\s*(\d{1,4})\.\s*(.*?)'  # Section number and content
        r'(?=(?:\n\s*\d{1,4}\.\s)|\Z)',  # Lookahead for next section number or EOF
        re.DOTALL | re.MULTILINE
    )

    matches = list(section_pattern.finditer(full_text))
    print(f"File: {os.path.basename(input_file_path)} — Found {len(matches)} sections before merging.")

    cleaned_sections = []
    previous_section_number = None

    for match in matches:
        section_number = int(match.group(1).strip())
        section_content = match.group(2).strip()

        # Clean current section content
        cleaned_content = clean_content(section_content)

        if previous_section_number is None:
            # First section — start fresh
            cleaned_sections.append({
                'section_number': str(section_number),
                'content': cleaned_content,
                'statute': statute_name
            })
            previous_section_number = section_number
        else:
            if section_number - previous_section_number == 1:
                # Proper next section — append as new
                cleaned_sections.append({
                    'section_number': str(section_number),
                    'content': cleaned_content,
                    'statute': statute_name
                })
                previous_section_number = section_number
            else:
                # Non-consecutive — append content to the previous section
                print(f"Appending content of section {section_number} to previous section {previous_section_number} (non-consecutive).")
                cleaned_sections[-1]['content'] += "\n\n" + cleaned_content
                # Note: Do NOT update previous_section_number — keep tracking the last valid number

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_file_path), exist_ok=True)

    # Save cleaned and merged sections to JSON
    with open(output_file_path, 'w', encoding='utf-8') as f:
        json.dump(cleaned_sections, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(cleaned_sections)} sections to {output_file_path}\n")


# ==================== Main Runner ====================
if __name__ == "__main__":
    """
    Main entry point of the script. Processes all input files defined in the configuration
    and extracts/cleans their sections.
    """
    for input_filename, (output_filename, statute_name) in input_output_files.items():
        input_path = os.path.join(base_path, input_filename)
        output_path = os.path.join(base_path, output_filename)

        extract_and_clean_sections(input_path, output_path, statute_name)

    print("All files processed successfully.")