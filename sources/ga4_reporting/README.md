# Lakeflow Google Analytics 4 Reporting Community Connector

This documentation provides setup instructions and reference information for the Google Analytics 4 (GA4) Reporting Data API source connector.

## Prerequisites

To use this connector, you need:

- A Google Analytics 4 property with data to report on
- Google Cloud Platform project with Analytics Reporting API enabled
- OAuth 2.0 credentials (Client ID and Client Secret)
- A refresh token with appropriate Analytics API scopes
- The GA4 Property ID you want to query

## Setup

### Required Connection Parameters

To configure the connector, provide the following parameters in your connector options:

| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `service_account_json` OR service account fields | String/Dict/File | Yes | Google Service Account credentials - see formats below | Multiple formats supported |
| `property_id` | String | Yes | GA4 Property ID (numeric only, no "properties/" prefix) | `123456789` |
| `initial_date` | String | No | Initial date for first-time ingestion (default: "2024-01-01") | `2024-01-01` or `2024-06-01` |
| `end_date` | String | No | End date for all report queries (default: "yesterday") | `2024-01-31`, `yesterday`, or `2daysAgo` |
| `lookback_days` | Integer | No | Number of days to re-ingest for data freshness (default: 3) | `3`, `7`, or `1` |

### Service Account Configuration Formats

The connector accepts service account credentials in **three flexible formats**:

#### **Format 1: Direct JSON Object (Recommended for dev_config.json)**
Place the service account fields directly in your configuration file without escaping:

```json
{
  "type": "service_account",
  "project_id": "your-project-id",
  "private_key_id": "abc123...",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
  "client_email": "service-account@project.iam.gserviceaccount.com",
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

#### **Format 2: File Path (Recommended for Production)**
Reference the path to your service account JSON file:

```json
{
  "service_account_json": "/path/to/service-account-key.json",
  "property_id": "123456789",
  "start_date": "30daysAgo",
  "end_date": "yesterday"
}
```

Or use relative paths:
```json
{
  "service_account_json": "configs/service-account-key.json",
  "property_id": "123456789"
}
```

#### **Format 3: Escaped JSON String (For Unity Catalog Connections)**
Provide the entire JSON key as an escaped string:

```json
{
  "service_account_json": "{\"type\": \"service_account\", \"project_id\": \"your-project\", ...}",
  "property_id": "123456789"
}
```

### How to Obtain Google Service Account Credentials

1. **Create a Google Cloud Project**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select an existing one

2. **Enable the Google Analytics Data API**:
   - Navigate to "APIs & Services" > "Library"
   - Search for "Google Analytics Data API"
   - Click "Enable"

3. **Create a Service Account**:
   - Go to "IAM & Admin" > "Service Accounts"
   - Click "Create Service Account"
   - Provide a name and description (e.g., "GA4 Reporting Connector")
   - Click "Create and Continue"
   - Skip granting roles (not needed for this step)
   - Click "Done"

4. **Create and Download Service Account Key**:
   - Click on the newly created service account
   - Go to the "Keys" tab
   - Click "Add Key" > "Create new key"
   - Choose "JSON" format
   - Click "Create" - the JSON key file will be downloaded
   - **Keep this file secure** - it provides access to your GCP resources

5. **Grant Service Account Access to GA4 Property**:
   - Go to [Google Analytics](https://analytics.google.com/)
   - Navigate to Admin > Property Access Management
   - Click "+" and select "Add users"
   - Enter the service account email (found in the JSON key, looks like `xxx@xxx.iam.gserviceaccount.com`)
   - Assign "Viewer" role (or higher if needed)
   - Click "Add"

6. **Find Your GA4 Property ID**:
   - In Google Analytics, go to Admin > Property Settings
   - Your Property ID is shown at the top (e.g., "123456789")
   - Use only the numeric value, without the "properties/" prefix

7. **Use the Service Account JSON**:
   - **Option A (Easiest)**: Copy the JSON fields directly into your config (see Format 1 above)
   - **Option B (Most Secure)**: Reference the file path (see Format 2 above)
   - **Option C (Unity Catalog)**: Use escaped JSON string (see Format 3 above)

### Create a Unity Catalog Connection

A Unity Catalog connection for this connector can be created in two ways via the UI:
1. Follow the Lakeflow Community Connector UI flow from the "Add Data" page
2. Navigate to the Unity Catalog UI and create a "Lakeflow Community Connector" connection

The connection can also be created using the standard Unity Catalog API.

## Supported Objects

This connector provides predefined report types that combine commonly used dimensions and metrics:

### Default Report Types

| Report Name | Description | Primary Key | Ingestion Type |
|-------------|-------------|-------------|----------------|
| `basic_report` | Basic traffic and engagement metrics with source and medium | `_composite_key` | Incremental |
| `user_demographics` | User demographic information including geography and user attributes | `_composite_key` | Incremental |
| `traffic_sources` | Traffic source analysis with campaign information | `_composite_key` | Incremental |
| `page_performance` | Page-level performance metrics | `_composite_key` | Incremental |
| `event_data` | Custom event tracking data | `_composite_key` | Incremental |

### Report Dimensions and Metrics

#### basic_report
- **Dimensions**: date, sessionSource, sessionMedium
- **Metrics**: activeUsers, sessions, screenPageViews, bounceRate, averageSessionDuration

#### user_demographics
- **Dimensions**: date, country, city, userGender, userAgeBracket
- **Metrics**: activeUsers, newUsers, sessions

#### traffic_sources
- **Dimensions**: date, sessionSource, sessionMedium, sessionCampaignName
- **Metrics**: activeUsers, sessions, conversions, totalRevenue

#### page_performance
- **Dimensions**: date, pagePath, pageTitle
- **Metrics**: screenPageViews, averageSessionDuration, bounceRate

#### event_data
- **Dimensions**: date, eventName, sessionSource
- **Metrics**: eventCount, eventValue, conversions

### Primary Keys

Each report uses a composite key (`_composite_key`) generated by concatenating the dimension values with a pipe delimiter (|). This ensures unique identification of each aggregated data point.

### Ingestion Strategy

All reports use **CDC (Change Data Capture)** ingestion with a **lookback window** to handle GA4's data freshness period:

- **First Run**: Ingests all data from `initial_date` to `end_date`
- **Subsequent Runs**: Re-ingests last N days (default: 3) + any new data
- **Lookback Window**: Captures late-arriving events and data corrections
- **Automatic Deduplication**: CDC mode keeps only latest version of each row
- **Checkpoint**: Tracks maximum date ingested per report
- **New Reports**: Automatically start from `initial_date` and catch up

**How it handles GA4's 24-48 hour processing window:**
1. Re-ingests the last 3 days on every run
2. Captures late-arriving events and updates
3. Deduplicates automatically by primary key (date + dimensions)
4. Only the latest, most complete data is kept in your tables

**Result:** You always have complete, accurate data without manual intervention!

### Special Columns

- `_composite_key`: Auto-generated composite key combining all dimension values
- Date dimensions are in YYYYMMDD format (e.g., "20240115")
- Dimension values may contain "(not set)" for missing data

## Data Type Mapping

| GA4 Metric Type | Description | Spark Type |
|-----------------|-------------|------------|
| Integer metrics (users, sessions, counts) | Whole number values | LongType |
| Decimal metrics (rates, durations, revenue) | Floating point values | DoubleType |
| All dimensions | Text values | StringType |
| Composite key | Generated concatenated string | StringType |

### Specific Field Types

| Field | Type | Notes |
|-------|------|-------|
| date | String | Format: YYYYMMDD |
| activeUsers | Long | Count of active users |
| sessions | Long | Count of sessions |
| screenPageViews | Long | Count of page views |
| eventCount | Long | Count of events |
| conversions | Long | Count of conversions |
| newUsers | Long | Count of new users |
| bounceRate | Double | Decimal (0.45 = 45%) |
| averageSessionDuration | Double | Seconds as decimal |
| totalRevenue | Double | Revenue in property currency |
| eventValue | Double | Custom event value |

## How to Run

### Step 1: Clone/Copy the Source Connector Code
Follow the Lakeflow Community Connector UI, which will guide you through setting up a pipeline using the selected source connector code.

### Step 2: Configure Your Pipeline

1. Update the `pipeline_spec` in the main pipeline file (e.g., `ingest.py`).
2. Ensure your Unity Catalog connection contains:
   - The complete service account JSON key as a string in `service_account_json`
   - The GA4 Property ID in `property_id`
   - The `initial_date` for first-time ingestion of any report
3. (Optional) Customize the date parameters:
   - `initial_date`: Starting point for new reports (default: "2024-01-01")
     - Use absolute dates in YYYY-MM-DD format like "2024-01-01"
   - `end_date`: End date for all queries (default: "yesterday")
     - Use relative dates like "yesterday", "2daysAgo", "7daysAgo"
     - **Recommended**: Use "2daysAgo" to avoid GA4's data freshness window

### Step 3: Run and Schedule the Pipeline

#### Best Practices

- **Start Small**: Begin by syncing one or two reports to test your pipeline
- **Set Appropriate Initial Date**: 
  - Choose `initial_date` based on how much historical data you need
  - Example: "2024-01-01" for year-to-date data
  - Older dates = more data to ingest on first run
- **Trust the Lookback Window**:
  - Default 3-day lookback handles GA4's data freshness automatically
  - Re-ingests recent data to capture late-arriving events
  - CDC mode automatically deduplicates, keeping only latest values
  - **No need to set `end_date` to "2daysAgo"** - the lookback window handles it!
- **Leverage Incremental Ingestion with Freshness Handling**:
  - First run fetches all data from `initial_date` to `end_date`
  - Subsequent runs fetch: last 3 days (freshness) + new data
  - Old data (>3 days) is stable and not re-fetched
  - Recent data (<3 days) is re-fetched and updated automatically
- **Monitor API Quotas**: GA4 has daily quotas on requests and token usage:
  - 200 requests per day per property (standard)
  - 40,000 tokens per day (each dimension/metric = 1 token)
  - 10 concurrent requests per property
  - Incremental ingestion significantly reduces quota usage
- **Schedule Daily Syncs**: 
  - Run daily to stay current
  - Each run is fast (only fetches 1-2 days of new data)
  - Consider running in off-peak hours
- **New Reports Auto-Catch-Up**: When adding new reports, they'll automatically fetch from `initial_date`

#### Troubleshooting

**Common Issues:**

1. **Authentication Errors (401 Unauthorized)**
   - **Cause**: Invalid service account credentials or expired token
   - **Solution**: 
     - Verify the service account JSON is complete and valid
     - Ensure the service account has been granted access to the GA4 property
     - Check that the Google Analytics Data API is enabled in your GCP project

2. **Property Not Found (404)**
   - **Cause**: Incorrect Property ID or insufficient permissions
   - **Solution**: 
     - Verify the Property ID in GA4 Admin settings
     - Ensure the service account email has been added as a user in Property Access Management with at least "Viewer" role

3. **Quota Exceeded (429 Too Many Requests)**
   - **Cause**: Exceeded daily API quota
   - **Solution**: 
     - Reduce the number of reports synced
     - Increase sync interval (e.g., daily instead of hourly)
     - Consider upgrading to Analytics 360 for higher quotas

4. **Incompatible Dimension/Metric Combination**
   - **Cause**: Some dimensions and metrics cannot be combined in GA4
   - **Solution**: Use the predefined report types or consult GA4 documentation for compatible combinations

5. **Empty Results**
   - **Cause**: No data for the specified date range or filter criteria
   - **Solution**: 
     - Verify data exists in GA4 for the date range
     - Check if the property has sufficient traffic
     - Wait 24-48 hours for recent data to process

6. **Data Freshness Issues**
   - **Cause**: GA4 data processing delay
   - **Solution**: 
     - Use "yesterday" as end_date instead of "today"
     - Expect final data to be available 24-48 hours after event occurrence

## References

- [GA4 Data API v1beta Documentation](https://developers.google.com/analytics/devguides/reporting/data/v1)
- [GA4 Data API Basics](https://developers.google.com/analytics/devguides/reporting/data/v1/basics)
- [GA4 Dimensions and Metrics](https://developers.google.com/analytics/devguides/reporting/data/v1/api-schema)
- [GA4 API Quotas and Limits](https://developers.google.com/analytics/devguides/reporting/data/v1/quotas)
- [Google OAuth 2.0 Documentation](https://developers.google.com/identity/protocols/oauth2)
- [OAuth 2.0 Playground](https://developers.google.com/oauthplayground/)

