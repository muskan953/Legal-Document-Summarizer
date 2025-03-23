import pandas as pd
import json
from transformers import AutoTokenizer

def generate_json_from_excel(excel_path, json_output_path, sheet_name='Sheet1'):
    """
    Reads an Excel file with IPC-to-BNS mapping data and generates a JSON file
    in the following format:
    
    [
      {
        "bns_section": "1(1)",
        "bns_subject": "Short title, commencement and application.",
        "ipc_section": "1",
        "ipc_subject": "Short title, commencement and application.",
        "summary": "This subject is covered by six subsections of Section 1 of BNS, corresponding to five separate sections of IPC, sans separate headings thereof. In IPC, the extent of code operation is also given, which is absent in BNS.",
      },
      ...
    ]
    
    Expected columns (after cleaning) in the Excel file:
      - 'BNS Sections/ Subsections'
      - 'Subject'
      - 'IPC Sections'
      - 'Summary of comparison'
    """
    # Load the Excel file
    df = pd.read_excel(excel_path, sheet_name=sheet_name)
    
    # Clean up column names: remove extra spaces and normalize spacing.
    df.columns = df.columns.str.strip().str.replace(r'\s+', ' ', regex=True)
    print("Columns found:", df.columns.tolist())
    
    records = []
    
    # Loop through each row to build JSON records.
    for index, row in df.iterrows():
        if pd.notnull(row['IPC Sections']) and pd.notnull(row['BNS Sections/ Subsections']):
            # Process summary: if exactly "Ditto." is present, use the summary from the previous record.
            if pd.notnull(row['Summary of comparison']):
                current_summary = str(row['Summary of comparison']).strip()
                if "Ditto" in current_summary:
                    # Use the previous record's summary if it exists.
                    summary = records[-1]['summary'] if records else ""
                else:
                    summary = current_summary
            else:
                summary = ""
    
            record = {
                "bns_section": str(row['BNS Sections/ Subsections']).strip().replace("\n", " ").replace("\r", " "),
                "bns_subject": str(row['Subject']).strip().replace("\n", " ").replace("\r", " "),
                "ipc_section": str(row['IPC Sections']).strip().replace("\n", " ").replace("\r", " "),
                "ipc_subject": str(row['Subject']).strip().replace("\n", " ").replace("\r", " "),
                "summary": summary.replace("\n", " ").replace("\r", " "),
            }
            records.append(record)
    
    # Write the JSON records to the specified file.
    with open(json_output_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
    
    print(f"JSON file generated and saved as {json_output_path}!")
    return records

def check_chunk_size(json_records, tokenizer, threshold=510):
    """
    Checks the token count (chunk size) of each record using InLegalBERT's tokenizer.
    
    The chunk size is defined as the total number of tokens across the concatenation
    of selected text fields.
    
    For InLegalBERT training, the maximum allowed chunk size is assumed to be 510 tokens.
    This function prints any record whose token count exceeds that threshold.
    """
    # Define which keys to include in the chunk size calculation.
    keys_to_include = ["ipc_section", "ipc_subject",
                       "bns_section", "bns_subject", "summary"]
    
    for record in json_records:
        # Concatenate the relevant fields into a single string.
        chunk_text = " ".join([str(record.get(key, "")) for key in keys_to_include])
        # Tokenize using the InLegalBERT tokenizer.
        tokens = tokenizer.tokenize(chunk_text)
        chunk_size = len(tokens)
        if chunk_size > threshold:
            print(f"Record (IPC Section {record['ipc_section']} / BNS Section {record['bns_section']}) exceeds threshold: {chunk_size} tokens.")
    print("Chunk size check complete.")

def main():
    excel_file_path = r"d:\Legal-Document-Summarizer\Dataset\Data_BNS_BNSS_BSA\Unprocessed\COMPARISON_SUMMARY_BNS_IPC.xlsx"
    json_file_path = r'd:\Legal-Document-Summarizer\Dataset\Data_BNS_BNSS_BSA\Comparative\IPC_BNS_mapping.json'

    records = generate_json_from_excel(excel_file_path, json_file_path)

    tokenizer = AutoTokenizer.from_pretrained("law-ai/InLegalBERT")
    check_chunk_size(records, tokenizer)

if __name__ == "__main__":
    main()