import pandas as pd 
import json
from transformers import AutoTokenizer

def generate_json_from_excel(excel_path, json_output_path,sheet_name = 1):
    
    df  = pd.read_excel(excel_path, sheet_name=sheet_name)

    df.columns = df.columns.str.strip().str.replace(r'\s+', ' ', regex=True)
    print("Columns found: ", df.columns.tolist())

    records = []

    for index,row in df.iterrows():
        if pd.notnull(row['BNSS Sections']) and pd.notnull(row['CrPC Sections']):
            # Process summary if "Ditto." is present in the summary, use previous summary
            if pd.notnull(row['Summary of Comparison']):
                current_summary = str(row['Summary of Comparison']).strip()
                if "Ditto" in current_summary:
                    # Use previous summary if it exists
                    current_summary = records[-1]['summary'] if records else ""
                else:
                    summary = current_summary
            else:
                summary = ""

        record = {
            "bnss_section": str(row['BNSS Sections']).strip().replace("\n", " ").replace("\r", " "),
            "bnss_subject": str(row['Subject']).strip().replace("\n", " ").replace("\r", " "),
            "crpc_section": str(row['CrPC Sections']).strip().replace("\n", " ").replace("\r", " "),
            "crpc_subject": str(row['Subject']).strip().replace("\n", " ").replace("\r", " "),
            "summary": summary.replace("\n", " ").replace("\r", " "),
        }

        records.append(record)

    with open(json_output_path, 'w', encoding= "utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
    
    print(f"JSON file generated and saved as {json_output_path}")
    return records

def check_chunk_size(json_records, tokenizer, threshold = 510):
    """
    Checks the token count (chunk size) of each record using InLegalBERT's tokenizer.
    
    The chunk size is defined as the total number of tokens across the concatenation
    of selected text fields.
    
    For InLegalBERT training, the maximum allowed chunk size is assumed to be 510 tokens.
    This function prints any record whose token count exceeds that threshold.
    """

    keys_to_include = ['bnss_subject','bnss_section', 'crpc_subject','crpc_section', 'summary']

    for record in json_records:
        # Concatenate selected text fields
        chunk_text = " ".join([str(record.get(key,"")) for key in keys_to_include])

        # Tokenize the concatenated text
        tokens = tokenizer.tokenize(chunk_text)
        chunk_size = len(tokens)

        if chunk_size > threshold:
            print(f"Chunk size ({chunk_size}) exceeds threshold ({threshold}) for record:")
            print(record)
            print()
    print("Chunk size check complete.")

def main():
    excel_file_path = r"d:\Legal-Document-Summarizer\Dataset\Data_BNS_BNSS_BSA\Unprocessed\Comparison_summary_BNSS_CrPC.xlsx"
    json_file_path = r'd:\Legal-Document-Summarizer\Dataset\Data_BNS_BNSS_BSA\Comparative\CrPC_BNSS_mapping.json'

    records = generate_json_from_excel(excel_file_path, json_file_path)

    tokenizer = AutoTokenizer.from_pretrained("law-ai/InLegalBERT")
    check_chunk_size(records, tokenizer)

if __name__ == "__main__":
    main()