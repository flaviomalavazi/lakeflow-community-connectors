# GA4 Reporting Connector - Quick Start Guide

This guide helps you quickly set up and test the Google Analytics 4 Reporting connector.

## Testing the Connector Locally

### 1. Set Up Your Credentials

Edit `sources/ga4_reporting/configs/dev_config.json` with your actual credentials:

```json
{
  "client_id": "YOUR_GOOGLE_CLIENT_ID.apps.googleusercontent.com",
  "client_secret": "YOUR_GOOGLE_CLIENT_SECRET",
  "refresh_token": "YOUR_REFRESH_TOKEN",
  "property_id": "YOUR_GA4_PROPERTY_ID",
  "start_date": "30daysAgo",
  "end_date": "yesterday"
}
```

**Important:** 
- Use only the numeric Property ID (e.g., "123456789"), not "properties/123456789"
- Ensure your refresh token has the `https://www.googleapis.com/auth/analytics.readonly` scope
- Do NOT commit this file to version control - it's in .gitignore for security

### 2. Install Dependencies

```bash
pip install requests pyspark
```

### 3. Run the Tests

From the repository root, run:

```bash
pytest sources/ga4_reporting/test/test_ga4_reporting_lakeflow_connect.py -v
```

This will:
- Test connection to the GA4 API
- Verify all report types are accessible
- Validate schemas match the API responses
- Fetch sample data from each report

### 4. Test Individual Components

You can also test the connector interactively:

```python
from sources.ga4_reporting.ga4_reporting import LakeflowConnect

# Initialize with your config
config = {
    "client_id": "YOUR_CLIENT_ID",
    "client_secret": "YOUR_CLIENT_SECRET",
    "refresh_token": "YOUR_REFRESH_TOKEN",
    "property_id": "123456789",
    "start_date": "7daysAgo",
    "end_date": "yesterday"
}

connector = LakeflowConnect(config)

# Test connection
result = connector.test_connection()
print(result)

# List available reports
tables = connector.list_tables()
print(f"Available reports: {tables}")

# Get schema for a report
schema = connector.get_table_schema("basic_report")
print(f"Schema: {schema}")

# Read data
records, offset = connector.read_table("basic_report", {})
for i, record in enumerate(records):
    print(record)
    if i >= 2:  # Print first 3 records
        break
```

## Common Test Scenarios

### Test with Different Date Ranges

```python
# Last 7 days
config["start_date"] = "7daysAgo"
config["end_date"] = "yesterday"

# Specific month
config["start_date"] = "2024-01-01"
config["end_date"] = "2024-01-31"

# Yesterday only
config["start_date"] = "yesterday"
config["end_date"] = "yesterday"
```

### Test Different Report Types

```python
reports_to_test = [
    "basic_report",
    "user_demographics", 
    "traffic_sources",
    "page_performance",
    "event_data"
]

for report in reports_to_test:
    print(f"\nTesting {report}...")
    records, _ = connector.read_table(report, {})
    count = sum(1 for _ in records)
    print(f"Retrieved {count} records")
```

## Troubleshooting Tests

### Authentication Errors

**Error:** `Failed to get access token: 400`

**Solutions:**
- Verify your client_id and client_secret are correct
- Ensure refresh_token hasn't been revoked
- Regenerate refresh token using OAuth 2.0 Playground

### Empty Results

**Error:** No data returned from reports

**Solutions:**
- Verify your GA4 property has data for the date range
- Check that your OAuth account has access to the property
- Ensure the property_id is correct (use Admin > Property Settings to verify)
- Try a wider date range (e.g., "90daysAgo")

### API Quota Exceeded

**Error:** `429 Too Many Requests`

**Solutions:**
- Wait for quotas to reset (typically at midnight PT)
- Test fewer reports at once
- Use narrower date ranges to reduce data volume

## Next Steps

After successful testing:

1. **Remove Sensitive Data**: Delete or clear `dev_config.json` before committing
2. **Create UC Connection**: Set up Unity Catalog connection with your credentials
3. **Deploy Pipeline**: Follow the README.md to deploy to Databricks
4. **Schedule Sync**: Set up appropriate sync schedule based on your needs

## Additional Resources

- Full documentation: [README.md](README.md)
- API documentation: [ga4_reporting_api_doc.md](ga4_reporting_api_doc.md)
- GA4 API reference: https://developers.google.com/analytics/devguides/reporting/data/v1

