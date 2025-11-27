
# Testing the connector:

#%%
from sources.ga4_reporting.ga4_reporting import LakeflowConnect

config = {
    "service_account_json": "../configs/service_account_config.json",
    "property_id": "123456789",
    "start_date": "7daysAgo",
    "end_date": "yesterday"
}

connector = LakeflowConnect(config)

#%%
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

## Common Test Scenarios

#%%
### Test Different Report Types

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

# %%
