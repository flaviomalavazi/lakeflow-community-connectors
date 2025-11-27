# GA4 Reporting Connector - Quick Start Guide

This guide helps you quickly set up and test the Google Analytics 4 Reporting connector.

## Testing the Connector Locally

### 1. Set Up Your Credentials

The connector supports **three configuration formats**. Choose the one that works best for you:

#### **Option A: Direct JSON Object (Easiest for Local Testing)**

Simply paste your service account JSON content directly into `dev_config.json`:

```json
{
  "type": "service_account",
  "project_id": "your-project-id",
  "private_key_id": "abc123...",
  "private_key": "-----BEGIN PRIVATE KEY-----\nYOUR_ACTUAL_KEY\n-----END PRIVATE KEY-----\n",
  "client_email": "your-sa@project.iam.gserviceaccount.com",
  "client_id": "123456789",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/...",
  "universe_domain": "googleapis.com",
  "property_id": "123456789",
  "start_date": "30daysAgo",
  "end_date": "yesterday"
}
```

#### **Option B: File Path (Most Secure)**

Keep your service account key in a separate file and reference it:

```json
{
  "service_account_json": "configs/my-service-account.json",
  "property_id": "123456789",
  "start_date": "30daysAgo",
  "end_date": "yesterday"
}
```

#### **Option C: Escaped JSON String (For Unity Catalog)**

Provide the entire JSON as an escaped string:

```json
{
  "service_account_json": "{\"type\": \"service_account\", \"project_id\": \"...\", ...}",
  "property_id": "123456789"
}
```

**Important:** 
- Use only the numeric Property ID (e.g., "123456789"), not "properties/123456789"
- Ensure the service account has been granted access to your GA4 property with at least "Viewer" role
- Do NOT commit service account credentials to version control - they're in .gitignore

### 2. Install Dependencies

```bash
pip install requests pyspark google-auth
```

**Note:** The connector can also work with `cryptography` library as a fallback:
```bash
pip install requests pyspark cryptography
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

You can also test the connector interactively with any of the three formats:

**Using File Path (Recommended):**
```python
from sources.ga4_reporting.ga4_reporting import LakeflowConnect

config = {
    "service_account_json": "path/to/service-account-key.json",
    "property_id": "123456789",
    "start_date": "7daysAgo",
    "end_date": "yesterday"
}

connector = LakeflowConnect(config)
```

**Using Direct JSON Object:**
```python
import json

with open("service-account-key.json", "r") as f:
    sa_dict = json.load(f)

config = {
    **sa_dict,  # Spread service account fields into config
    "property_id": "123456789",
    "start_date": "7daysAgo",
    "end_date": "yesterday"
}

connector = LakeflowConnect(config)
```

**Using Escaped JSON String:**
```python
import json

with open("service-account-key.json", "r") as f:
    sa_json_string = json.dumps(json.load(f))

config = {
    "service_account_json": sa_json_string,
    "property_id": "123456789"
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

**Error:** `Failed to get access token: 400` or `401 Unauthorized`

**Solutions:**
- Verify your service account JSON is complete and valid
- Ensure the service account has been granted access to the GA4 property (Admin > Property Access Management)
- Check that the Google Analytics Data API is enabled in your GCP project
- Verify the service account email and private key are correct
- Install required dependencies: `pip install google-auth` or `pip install cryptography`

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

