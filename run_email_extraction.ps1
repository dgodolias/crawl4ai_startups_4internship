# Run the pipeline to extract emails from EU startup websites
# This script first consolidates all country CSVs, then extracts emails

# Step 1: Run duplicate_remover.py to consolidate CSVs and remove duplicates
Write-Host "`nStep 1: Consolidating CSV files and removing duplicates...`n" -ForegroundColor Cyan
python duplicate_remover.py --output european_startup_websites.csv

# Check if the previous step was successful
if (-not (Test-Path -Path "european_startup_websites.csv")) {
    Write-Host "Error: Consolidated CSV file was not created. Exiting." -ForegroundColor Red
    exit
}

# Step 2: Run find_contact_email.py to extract emails
Write-Host "`nStep 2: Extracting emails from company websites...`n" -ForegroundColor Cyan
python find_contact_email.py --input european_startup_websites.csv --output european_startups_with_emails.csv

# Display success message
Write-Host "`nProcess completed!`n" -ForegroundColor Green
Write-Host "Output file: european_startups_with_emails.csv" -ForegroundColor Green
