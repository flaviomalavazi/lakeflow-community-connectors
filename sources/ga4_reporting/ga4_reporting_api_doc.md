# **Google Analytics 4 Reporting Data API Documentation**

## **Authorization**

The GA4 Reporting Data API uses Google Service Account authentication. The connector stores the complete service account JSON key and uses it to obtain access tokens at runtime.

**Preferred Method: Service Account Authentication**

- **Token Endpoint**: `https://oauth2.googleapis.com/token`
- **Required Scopes**:
  - `https://www.googleapis.com/auth/analytics.readonly` (read-only access)
  - `https://www.googleapis.com/auth/analytics` (read/write access)

**Service Account Key Structure:**

```json
{
  "type": "service_account",
  "project_id": "your-project-id",
  "private_key_id": "key-id",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
  "client_email": "service-account@project-id.iam.gserviceaccount.com",
  "client_id": "123456789",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/service_accounts/v1/metadata/x509/...",
  "universe_domain": "googleapis.com"
}
```

**Authentication Flow:**

1. The connector loads the service account JSON key
2. Creates a JWT (JSON Web Token) signed with the private key
3. Exchanges the JWT for an access token using the OAuth 2.0 JWT bearer flow
4. Access tokens are valid for 1 hour and automatically refreshed as needed

**Access Token Exchange:**

```http
POST https://oauth2.googleapis.com/token
Content-Type: application/x-www-form-urlencoded

grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer
&assertion={signed_jwt_token}
```

**Response:**
```json
{
  "access_token": "ya29.a0AfH6SMBx...",
  "expires_in": 3600,
  "token_type": "Bearer"
}
```

**Using the Access Token:**

All API requests must include the access token in the Authorization header:

```http
Authorization: Bearer {access_token}
```

**Service Account Setup Requirements:**

1. Service account must be created in a Google Cloud project with Analytics Data API enabled
2. Service account email must be granted access to the GA4 property (minimum "Viewer" role)
3. The connector supports two authentication methods:
   - Using `google-auth` library (preferred, install with `pip install google-auth`)
   - Using `cryptography` library for manual JWT signing (fallback, install with `pip install cryptography`)

## **Object List**

The GA4 Reporting Data API doesn't have pre-defined "tables" like traditional databases. Instead, it provides customizable reports based on dimensions and metrics combinations. For this connector, we'll implement a static list of commonly used report types:

**Static Report Types:**
- `basic_report` - Basic traffic and engagement metrics
- `user_demographics` - User demographic information
- `traffic_sources` - Traffic source and medium data
- `page_performance` - Page-level performance metrics
- `event_data` - Custom event tracking data

Each report type represents a specific combination of dimensions and metrics that can be queried from the GA4 Data API.

## **Object Schema**

The schema for GA4 reports is dynamic and depends on the dimensions and metrics requested. However, all reports follow a common structure:

**Common Response Structure:**
```json
{
  "dimensionHeaders": [
    {
      "name": "date"
    },
    {
      "name": "country"
    }
  ],
  "metricHeaders": [
    {
      "name": "activeUsers",
      "type": "TYPE_INTEGER"
    },
    {
      "name": "sessions",
      "type": "TYPE_INTEGER"
    }
  ],
  "rows": [
    {
      "dimensionValues": [
        {
          "value": "20231101"
        },
        {
          "value": "United States"
        }
      ],
      "metricValues": [
        {
          "value": "12345"
        },
        {
          "value": "67890"
        }
      ]
    }
  ],
  "rowCount": 1,
  "metadata": {
    "currencyCode": "USD",
    "timeZone": "America/New_York"
  }
}
```

**Field Descriptions:**
- `dimensionHeaders`: Array of dimension definitions in the report
  - `name`: The API name of the dimension
- `metricHeaders`: Array of metric definitions in the report
  - `name`: The API name of the metric
  - `type`: Data type (TYPE_INTEGER, TYPE_FLOAT, TYPE_CURRENCY, etc.)
- `rows`: Array of data rows
  - `dimensionValues`: Array of dimension values (ordered same as dimensionHeaders)
  - `metricValues`: Array of metric values (ordered same as metricHeaders)
- `rowCount`: Total number of rows in the response
- `metadata`: Additional metadata about the report
  - `currencyCode`: Currency code if applicable
  - `timeZone`: Property timezone

**Report-Specific Schemas:**

### basic_report
**Dimensions:** date, sessionSource, sessionMedium
**Metrics:** activeUsers, sessions, screenPageViews, bounceRate, averageSessionDuration

### user_demographics
**Dimensions:** date, country, city, userGender, userAgeBracket
**Metrics:** activeUsers, newUsers, sessions

### traffic_sources
**Dimensions:** date, sessionSource, sessionMedium, sessionCampaignName
**Metrics:** activeUsers, sessions, conversions, totalRevenue

### page_performance
**Dimensions:** date, pagePath, pageTitle
**Metrics:** screenPageViews, averageSessionDuration, bounceRate

### event_data
**Dimensions:** date, eventName, sessionSource
**Metrics:** eventCount, eventValue, conversions

## **Get Object Primary Key**

For GA4 reports, there's no inherent primary key since reports are aggregated data. However, we use a composite key based on the dimensions and date:

- `basic_report`: Composite key of [date, sessionSource, sessionMedium]
- `user_demographics`: Composite key of [date, country, city, userGender, userAgeBracket]
- `traffic_sources`: Composite key of [date, sessionSource, sessionMedium, sessionCampaignName]
- `page_performance`: Composite key of [date, pagePath]
- `event_data`: Composite key of [date, eventName, sessionSource]

Since composite keys in our connector model use a single field, we'll generate a synthetic `_composite_key` field by concatenating the dimension values.

## **Object's ingestion type**

All GA4 reports use **snapshot** ingestion type because:
- Reports are aggregated data, not transactional records
- Historical data can change as GA4 processes events (data freshness window is typically 24-48 hours)
- There's no reliable way to track individual record changes or deletions
- Each sync should pull the complete dataset for the specified date range

## **Read API for Data Retrieval**

**Endpoint:** `POST https://analyticsdata.googleapis.com/v1beta/properties/{propertyId}:runReport`

**Required Parameters:**
- `propertyId`: The GA4 property ID (format: `properties/123456789`)

**Request Body Structure:**

```json
{
  "dateRanges": [
    {
      "startDate": "2023-11-01",
      "endDate": "2023-11-30"
    }
  ],
  "dimensions": [
    {
      "name": "date"
    },
    {
      "name": "country"
    }
  ],
  "metrics": [
    {
      "name": "activeUsers"
    },
    {
      "name": "sessions"
    }
  ],
  "limit": 100000,
  "offset": 0,
  "keepEmptyRows": false
}
```

**Request Parameters:**
- `dateRanges` (required): Array of date ranges to query
  - `startDate`: Start date in YYYY-MM-DD format or relative date like "30daysAgo"
  - `endDate`: End date in YYYY-MM-DD format or "today", "yesterday"
- `dimensions`: Array of dimension objects to group by
  - `name`: Dimension API name (e.g., "date", "country", "sessionSource")
- `metrics`: Array of metric objects to aggregate
  - `name`: Metric API name (e.g., "activeUsers", "sessions")
- `dimensionFilter` (optional): FilterExpression to filter dimensions
- `metricFilter` (optional): FilterExpression to filter metrics (applied after aggregation)
- `offset` (optional): Row offset for pagination (default: 0)
- `limit` (optional): Number of rows to return (max: 250,000, default: 10,000)
- `keepEmptyRows` (optional): Whether to return rows with all metrics equal to 0
- `orderBys` (optional): Array of ordering specifications
- `currencyCode` (optional): Currency code (e.g., "USD")

**Pagination:**

The API supports offset-based pagination:
1. First request: `offset=0, limit=100000`
2. Second request: `offset=100000, limit=100000`
3. Continue until `rowCount < limit`

**Example Request:**

```bash
curl -X POST \
  'https://analyticsdata.googleapis.com/v1beta/properties/123456789:runReport' \
  -H 'Authorization: Bearer ya29.a0AfH6SMBx...' \
  -H 'Content-Type: application/json' \
  -d '{
    "dateRanges": [{"startDate": "30daysAgo", "endDate": "today"}],
    "dimensions": [{"name": "date"}, {"name": "sessionSource"}],
    "metrics": [{"name": "activeUsers"}, {"name": "sessions"}],
    "limit": 10000,
    "offset": 0
  }'
```

**Example Response:**

```json
{
  "dimensionHeaders": [
    {"name": "date"},
    {"name": "sessionSource"}
  ],
  "metricHeaders": [
    {"name": "activeUsers", "type": "TYPE_INTEGER"},
    {"name": "sessions", "type": "TYPE_INTEGER"}
  ],
  "rows": [
    {
      "dimensionValues": [
        {"value": "20231101"},
        {"value": "google"}
      ],
      "metricValues": [
        {"value": "1234"},
        {"value": "5678"}
      ]
    }
  ],
  "rowCount": 1,
  "metadata": {
    "currencyCode": "USD",
    "timeZone": "America/Los_Angeles"
  }
}
```

**Incremental Data Retrieval:**

Since GA4 uses snapshot ingestion, incremental reads are not applicable. Each sync should:
1. Define a date range (e.g., last 30 days, last 90 days, or specific date range)
2. Pull all data for that date range
3. Replace previous data for those dates

**Rate Limits:**
- 10 concurrent requests per property
- 200 requests per day per property (may vary by Analytics 360 vs standard)
- 40,000 tokens per day per property (each dimension/metric counts as a token)

**Deleted Records:**

GA4 doesn't provide explicit deletion tracking for report data. Historical data may change due to:
- Late-arriving events (within the data freshness window)
- User data deletion requests (GDPR/privacy)
- Data import corrections

The snapshot approach handles these scenarios by replacing all data on each sync.

## **Field Type Mapping**

GA4 API returns metric types that need to be mapped to Spark data types:

| GA4 Metric Type | Description | Spark Type |
|-----------------|-------------|------------|
| TYPE_INTEGER | Integer value | LongType |
| TYPE_FLOAT | Floating point number | DoubleType |
| TYPE_SECONDS | Duration in seconds | DoubleType |
| TYPE_MILLISECONDS | Duration in milliseconds | LongType |
| TYPE_MINUTES | Duration in minutes | DoubleType |
| TYPE_HOURS | Duration in hours | DoubleType |
| TYPE_STANDARD | Generic numeric (can be float or int) | DoubleType |
| TYPE_CURRENCY | Monetary value | DoubleType |
| TYPE_FEET | Distance in feet | DoubleType |
| TYPE_MILES | Distance in miles | DoubleType |
| TYPE_METERS | Distance in meters | DoubleType |
| TYPE_KILOMETERS | Distance in kilometers | DoubleType |

All dimensions are string values and map to `StringType`.

**Special Considerations:**
- Date dimensions (e.g., "date") are formatted as YYYYMMDD and stored as StringType
- Boolean metrics don't exist in GA4; use filters instead
- Percentages (like bounceRate) are returned as decimals (0.45 = 45%)

## **Write API**

The GA4 Reporting Data API is **read-only**. There is no write API for report data.

For writing data to GA4, you would need to use:
- **Measurement Protocol** (for sending events)
- **Data Import** (for uploading dimension/metric data)
- **Admin API** (for configuration changes)

These are out of scope for this reporting connector.

## **Sources and References**

### Research Log

| Source Type | URL | Accessed (UTC) | Confidence | What it confirmed |
|-------------|-----|----------------|------------|-------------------|
| Official Docs | https://developers.google.com/analytics/devguides/reporting/data/v1/rest/v1beta/properties/runReport | 2025-11-21 | High | API endpoint, request/response structure, pagination, authentication |
| Official Docs | https://developers.google.com/analytics/devguides/reporting/data/v1/basics | 2025-11-21 | High | Dimensions, metrics, date ranges, filters |
| Official Docs | https://developers.google.com/analytics/devguides/reporting/data/v1/quotas | 2025-11-21 | High | Rate limits and quotas |
| Airbyte OSS | https://github.com/airbytehq/airbyte/tree/master/airbyte-integrations/connectors/source-google-analytics-data-api | 2025-11-21 | High | OAuth implementation, report configuration patterns |

### Full References

1. **GA4 Data API v1beta Reference**: https://developers.google.com/analytics/devguides/reporting/data/v1/rest/v1beta/properties/runReport
2. **GA4 Data API Basics**: https://developers.google.com/analytics/devguides/reporting/data/v1/basics
3. **GA4 Dimensions & Metrics**: https://developers.google.com/analytics/devguides/reporting/data/v1/api-schema
4. **GA4 API Quotas**: https://developers.google.com/analytics/devguides/reporting/data/v1/quotas
5. **OAuth 2.0**: https://developers.google.com/identity/protocols/oauth2
6. **Airbyte GA4 Connector**: https://github.com/airbytehq/airbyte/tree/master/airbyte-integrations/connectors/source-google-analytics-data-api

## **Known Quirks & Edge Cases**

1. **Data Freshness**: GA4 data has a 24-48 hour processing window. Recent data may change as events are processed.

2. **Cardinality Limits**: High-cardinality dimensions (like userId) have sampling applied automatically.

3. **Metric Compatibility**: Not all metrics can be combined with all dimensions. The API will return an error if an incompatible combination is requested.

4. **Date Format**: The `date` dimension returns YYYYMMDD format (e.g., "20231101"), not ISO format.

5. **Empty Values**: Some dimension values may be "(not set)" or "(none)" for missing data.

6. **Session vs User Scope**: Metrics have different scopes (event, session, user). Combining mismatched scopes can produce unexpected results.

7. **Token Counting**: Each dimension and metric in a request counts toward the daily token quota.

8. **Property ID Format**: The property ID must be prefixed with "properties/" in the endpoint URL but NOT in the API request body.

