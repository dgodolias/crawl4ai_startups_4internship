import pandas as pd
import re

# List of keywords to match in email addresses (before the @ symbol)
# You can modify this list to add or remove keywords
KEYWORDS = ['info', 'support', 'hello', 'hk', 'supportdt','email','contact','contactus','team']

def extract_emails_with_keywords(email):
    """
    Check if the email address has any of the keywords before the @ symbol.
    
    Args:
        email (str): The email address to check.
    
    Returns:
        bool: True if the email matches any of the keywords, False otherwise.
    """
    if not isinstance(email, str):
        return False
    
    # Split the email at '@'
    parts = email.split('@')
    if len(parts) != 2:
        return False
    
    # Get the local part (before the '@')
    local_part = parts[0].lower()
    
    # Check if the local part matches any of our keywords
    for keyword in KEYWORDS:
        # Check if keyword is exactly the local part or is a complete word within it
        if local_part == keyword or re.search(r'\b' + re.escape(keyword) + r'\b', local_part) is not None:
            return True
    
    return False

# Read the CSV file into a DataFrame
df = pd.read_csv('european_ai_startups_contact_info.csv')

# Filter emails using our custom function
filtered_emails = []
if 'email' in df.columns:
    for email in df['email'].dropna():
        if extract_emails_with_keywords(email):
            filtered_emails.append(email)

# If there are multiple emails in a cell (comma-separated), split and check each one
if len(filtered_emails) == 0 and df.shape[0] > 0:
    # Try to handle the case where emails are comma-separated in a single cell
    for row in df.itertuples():
        for col in df.columns:
            val = getattr(row, col, None)
            if isinstance(val, str) and '@' in val:
                # Split by comma if multiple emails are in the same cell
                potential_emails = [e.strip() for e in val.split(',')]
                for email in potential_emails:
                    if extract_emails_with_keywords(email):
                        filtered_emails.append(email)

# Print each filtered email on a new line
for email in filtered_emails:
    print(email)

# Also save to a file for reference
if filtered_emails:
    with open('extracted_emails.txt', 'w') as f:
        for email in filtered_emails:
            f.write(f"{email}\n")
    print(f"\nExtracted {len(filtered_emails)} emails matching keywords {KEYWORDS} and saved to extracted_emails.txt")