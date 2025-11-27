# GA4 Reporting Connector - Architecture

This document describes the architecture and organization of the GA4 Reporting connector code.

## Code Organization

The connector is organized into three main logical sections:

### 1. Authentication & Configuration
Handles service account credentials and API setup.

### 2. Report Configuration
Defines the report types and their dimensions/metrics.

### 3. Data Retrieval
Executes API requests and transforms data.

## Class Structure

```
LakeflowConnect
├── __init__()                               # Initialization
├── Authentication Methods
│   ├── _parse_service_account_credentials() # Parse credentials from various formats
│   ├── _get_access_token()                  # Get access token using service account
│   ├── _create_jwt_token()                  # Fallback JWT creation
│   └── _refresh_token_if_needed()           # Auto-refresh expired tokens
│
├── Report Configuration Methods
│   └── _build_report_configurations()       # Build report definitions
│
├── LakeflowConnect Interface Methods
│   ├── list_tables()                        # List available report types
│   ├── get_table_schema()                   # Get schema for a report
│   ├── read_table_metadata()                # Get metadata (pk, ingestion type)
│   └── read_table()                         # Read data from a report
│
├── Data Retrieval Methods
│   ├── _fetch_report_data()                 # Fetch data with pagination
│   └── _transform_row()                     # Transform API row to our schema
│
└── Utility Methods
    └── test_connection()                    # Test API connectivity
```

## Initialization Flow

```
__init__(options)
    │
    ├─► Parse property_id, start_date, end_date from options
    │
    ├─► _parse_service_account_credentials()
    │   │
    │   ├─► Detect format (dict/string/file path)
    │   ├─► Load/parse credentials
    │   └─► Return service_account_info dict
    │
    ├─► _get_access_token()
    │   │
    │   ├─► Try google-auth library (preferred)
    │   └─► Fallback to _create_jwt_token()
    │
    └─► _build_report_configurations()
        │
        └─► Return dict of report configs
```

## Report Configuration

The `_build_report_configurations()` method is the **single source of truth** for all report definitions.

### Purpose
- Centralizes all report configurations
- Makes it easy to add/modify/remove reports
- Separates report logic from authentication
- Allows for future dynamic report generation

### Structure

```python
def _build_report_configurations(self) -> Dict:
    return {
        "report_name": {
            "dimensions": [
                {"name": "dimension1"},
                {"name": "dimension2"}
            ],
            "metrics": [
                {"name": "metric1"},
                {"name": "metric2"}
            ],
            "primary_key": ["dimension1", "dimension2"]
        }
    }
```

### Adding a New Report

To add a new report type, simply add it to the returned dictionary in `_build_report_configurations()`:

```python
def _build_report_configurations(self) -> Dict:
    return {
        # ... existing reports ...
        
        "my_new_report": {
            "dimensions": [
                {"name": "date"},
                {"name": "customDimension"}
            ],
            "metrics": [
                {"name": "customMetric"}
            ],
            "primary_key": ["date", "customDimension"]
        }
    }
```

That's it! The report will automatically:
- Appear in `list_tables()`
- Have a schema generated in `get_table_schema()`
- Have metadata available in `read_table_metadata()`
- Be queryable via `read_table()`

## Authentication Architecture

### Multi-Format Credential Support

The connector accepts credentials in three formats:

```
options
    │
    ├─► Format 1: Direct JSON Object
    │   {
    │     "type": "service_account",
    │     "project_id": "...",
    │     ...
    │   }
    │
    ├─► Format 2: File Path
    │   {
    │     "service_account_json": "path/to/file.json"
    │   }
    │
    └─► Format 3: Escaped JSON String
        {
          "service_account_json": "{\"type\": \"service_account\", ...}"
        }
```

### Token Management

```
_get_access_token()
    │
    ├─► google-auth available?
    │   ├─► YES: Use service_account.Credentials
    │   └─► NO:  Use _create_jwt_token()
    │
    └─► Set token_expiry (1 hour)

_refresh_token_if_needed()
    │
    └─► If token expires in < 5 minutes
        └─► Call _get_access_token()
```

Tokens are automatically refreshed:
- Before each API request in `_fetch_report_data()`
- Before connection tests in `test_connection()`
- When token expires in less than 5 minutes

## Data Flow

### Reading Report Data

```
read_table(table_name, start_offset)
    │
    └─► _fetch_report_data(table_name)
        │
        ├─► Loop with pagination
        │   │
        │   ├─► _refresh_token_if_needed()
        │   │
        │   ├─► Build request body with:
        │   │   ├─► dateRanges (start_date, end_date)
        │   │   ├─► dimensions from config
        │   │   ├─► metrics from config
        │   │   └─► offset & limit
        │   │
        │   ├─► POST to GA4 API
        │   │
        │   ├─► For each row:
        │   │   └─► _transform_row()
        │   │       ├─► Extract dimension values
        │   │       ├─► Extract & convert metric values
        │   │       └─► Generate composite key
        │   │
        │   └─► Yield transformed records
        │
        └─► Return (iterator, offset_dict)
```

## Schema Generation

Schemas are dynamically generated based on report configurations:

```python
get_table_schema(table_name)
    │
    ├─► Get config from _report_configs
    │
    ├─► Build StructType with:
    │   ├─► _composite_key (StringType, required)
    │   ├─► Each dimension (StringType, nullable)
    │   └─► Each metric (LongType or DoubleType, nullable)
    │
    └─► Return StructType
```

### Type Mapping Logic

```python
Integer Metrics (LongType):
- activeUsers
- sessions  
- screenPageViews
- eventCount
- conversions
- newUsers

Decimal Metrics (DoubleType):
- bounceRate
- averageSessionDuration
- totalRevenue
- eventValue
```

## Error Handling

### Credential Parsing
- `ValueError` with clear message for invalid formats
- File not found errors
- JSON decode errors

### API Errors
- Token refresh failures
- API request failures (with status code)
- Rate limiting (with 100ms delay between requests)

### Data Validation
- Unknown table names raise `ValueError`
- Invalid metric/dimension responses handled gracefully

## Extensibility

### Future Enhancements

The architecture supports easy addition of:

1. **Dynamic Reports**: Allow users to define custom dimension/metric combinations
   ```python
   def add_custom_report(self, name, dimensions, metrics):
       self._report_configs[name] = {
           "dimensions": dimensions,
           "metrics": metrics,
           "primary_key": [d["name"] for d in dimensions]
       }
   ```

2. **Report Filters**: Add dimension/metric filters
   ```python
   "report_name": {
       "dimensions": [...],
       "metrics": [...],
       "filters": {
           "dimensionFilter": {...},
           "metricFilter": {...}
       }
   }
   ```

3. **Custom Date Ranges per Report**
   ```python
   "report_name": {
       "dimensions": [...],
       "metrics": [...],
       "date_range_override": {
           "start_date": "7daysAgo",
           "end_date": "yesterday"
       }
   }
   ```

4. **Report Templates**: Pre-configured report bundles
   ```python
   REPORT_TEMPLATES = {
       "ecommerce": ["traffic_sources", "conversions", ...],
       "content": ["page_performance", "event_data", ...]
   }
   ```

## Best Practices

### When Adding New Reports

1. Add report configuration in `_build_report_configurations()`
2. Verify dimensions/metrics are compatible (check GA4 docs)
3. Choose appropriate primary key dimensions
4. Test with actual data to verify schema
5. Update documentation (README.md, QUICKSTART.md)

### When Modifying Authentication

1. Maintain backward compatibility with all three formats
2. Add clear error messages for debugging
3. Test token refresh logic
4. Handle network failures gracefully

### When Changing Data Processing

1. Preserve composite key generation logic
2. Maintain type mappings (Long vs Double)
3. Handle null/missing values properly
4. Test with various date ranges

## Performance Considerations

### Pagination
- Max 100,000 rows per API request
- 100ms delay between requests (rate limiting)
- Automatic handling of multiple pages

### Token Caching
- Tokens cached for 1 hour
- Automatic refresh before expiry
- Minimal API calls for token renewal

### Memory Efficiency
- Uses generators/iterators for data streaming
- Records yielded one at a time
- No full dataset loaded into memory

## Security

### Credential Handling
- Never logged or printed
- Stored only in memory during runtime
- Support for external file references
- Clear separation from configuration

### API Access
- Read-only operations only
- Minimal required permissions (Viewer role)
- Automatic token expiry
- HTTPS only communication

## Testing

The connector can be tested at multiple levels:

1. **Unit Testing**: Test individual methods
2. **Integration Testing**: Test with GA4 API
3. **End-to-End Testing**: Full data pipeline

See `test/test_ga4_reporting_lakeflow_connect.py` for examples.

## Dependencies

- **Required**: `requests`, `pyspark`
- **Authentication** (one of):
  - `google-auth` (recommended)
  - `cryptography` (fallback)

## Summary

The refactored architecture provides:

✅ **Clear Separation** - Authentication vs Report Configuration vs Data Retrieval  
✅ **Easy Maintenance** - Single method for all report definitions  
✅ **Extensibility** - Simple to add new reports or features  
✅ **Flexibility** - Multiple credential formats supported  
✅ **Reliability** - Automatic token refresh, error handling  
✅ **Performance** - Streaming data, efficient pagination  
✅ **Security** - Proper credential handling, minimal permissions

