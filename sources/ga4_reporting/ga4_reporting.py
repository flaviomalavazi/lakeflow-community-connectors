# Google Analytics 4 Reporting Data API connector implementation

import requests
import json
import time
from typing import Dict, List, Iterator
from pyspark.sql.types import (
    StructType,
    StructField,
    StringType,
    LongType,
    DoubleType,
    BooleanType,
)


class LakeflowConnect:
    def __init__(self, options: Dict[str, str]) -> None:
        """
        Initialize the GA4 Reporting connector with API credentials.

        Args:
            options: Dictionary containing:
                - client_id: Google OAuth client ID
                - client_secret: Google OAuth client secret
                - refresh_token: Google OAuth refresh token
                - property_id: GA4 property ID (e.g., "123456789")
                - start_date: Start date for reports (default: "30daysAgo")
                - end_date: End date for reports (default: "yesterday")
        """
        self.client_id = options["client_id"]
        self.client_secret = options["client_secret"]
        self.refresh_token = options["refresh_token"]
        self.property_id = options["property_id"]
        self.start_date = options.get("start_date", "30daysAgo")
        self.end_date = options.get("end_date", "yesterday")

        # Get access token
        self.access_token = self._get_access_token()

        # Base URL for GA4 Data API
        self.base_url = "https://analyticsdata.googleapis.com/v1beta"

        # Define report configurations
        self._report_configs = {
            "basic_report": {
                "dimensions": [
                    {"name": "date"},
                    {"name": "sessionSource"},
                    {"name": "sessionMedium"},
                ],
                "metrics": [
                    {"name": "activeUsers"},
                    {"name": "sessions"},
                    {"name": "screenPageViews"},
                    {"name": "bounceRate"},
                    {"name": "averageSessionDuration"},
                ],
                "primary_key": ["date", "sessionSource", "sessionMedium"],
            },
            "user_demographics": {
                "dimensions": [
                    {"name": "date"},
                    {"name": "country"},
                    {"name": "city"},
                    {"name": "userGender"},
                    {"name": "userAgeBracket"},
                ],
                "metrics": [
                    {"name": "activeUsers"},
                    {"name": "newUsers"},
                    {"name": "sessions"},
                ],
                "primary_key": ["date", "country", "city", "userGender", "userAgeBracket"],
            },
            "traffic_sources": {
                "dimensions": [
                    {"name": "date"},
                    {"name": "sessionSource"},
                    {"name": "sessionMedium"},
                    {"name": "sessionCampaignName"},
                ],
                "metrics": [
                    {"name": "activeUsers"},
                    {"name": "sessions"},
                    {"name": "conversions"},
                    {"name": "totalRevenue"},
                ],
                "primary_key": ["date", "sessionSource", "sessionMedium", "sessionCampaignName"],
            },
            "page_performance": {
                "dimensions": [
                    {"name": "date"},
                    {"name": "pagePath"},
                    {"name": "pageTitle"},
                ],
                "metrics": [
                    {"name": "screenPageViews"},
                    {"name": "averageSessionDuration"},
                    {"name": "bounceRate"},
                ],
                "primary_key": ["date", "pagePath"],
            },
            "event_data": {
                "dimensions": [
                    {"name": "date"},
                    {"name": "eventName"},
                    {"name": "sessionSource"},
                ],
                "metrics": [
                    {"name": "eventCount"},
                    {"name": "eventValue"},
                    {"name": "conversions"},
                ],
                "primary_key": ["date", "eventName", "sessionSource"],
            },
        }

    def _get_access_token(self) -> str:
        """
        Exchange refresh token for access token.

        Returns:
            Access token string
        """
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
        }

        response = requests.post(token_url, data=data)

        if response.status_code != 200:
            raise Exception(
                f"Failed to get access token: {response.status_code} {response.text}"
            )

        return response.json()["access_token"]

    def list_tables(self) -> List[str]:
        """
        List available GA4 report types.

        Returns:
            List of report type names
        """
        return list(self._report_configs.keys())

    def get_table_schema(self, table_name: str) -> StructType:
        """
        Get the Spark schema for a GA4 report.

        Args:
            table_name: Name of the report type

        Returns:
            StructType representing the report schema
        """
        if table_name not in self._report_configs:
            raise ValueError(f"Unknown report type: {table_name}")

        config = self._report_configs[table_name]

        # Build schema fields
        fields = []

        # Add composite key field
        fields.append(StructField("_composite_key", StringType(), False))

        # Add dimension fields
        for dim in config["dimensions"]:
            fields.append(StructField(dim["name"], StringType(), True))

        # Add metric fields - we'll determine the type dynamically
        # For now, use DoubleType for all metrics as they can be decimal values
        for metric in config["metrics"]:
            # Some metrics are inherently long integers (counts, users)
            if metric["name"] in [
                "activeUsers",
                "sessions",
                "screenPageViews",
                "eventCount",
                "conversions",
                "newUsers",
            ]:
                fields.append(StructField(metric["name"], LongType(), True))
            else:
                # Rates, durations, revenue are doubles
                fields.append(StructField(metric["name"], DoubleType(), True))

        return StructType(fields)

    def read_table_metadata(self, table_name: str) -> Dict:
        """
        Get metadata for a GA4 report.

        Args:
            table_name: Name of the report type

        Returns:
            Dictionary with primary_key and ingestion_type
        """
        if table_name not in self._report_configs:
            raise ValueError(f"Unknown report type: {table_name}")

        # All GA4 reports use snapshot ingestion since data is aggregated
        return {"primary_key": "_composite_key", "ingestion_type": "snapshot"}

    def read_table(
        self, table_name: str, start_offset: Dict
    ) -> tuple[Iterator[Dict], Dict]:
        """
        Read data from a GA4 report.

        Args:
            table_name: Name of the report type
            start_offset: Not used for snapshot ingestion

        Returns:
            Tuple of (records iterator, empty offset dict)
        """
        if table_name not in self._report_configs:
            raise ValueError(f"Unknown report type: {table_name}")

        # For snapshot, we always read all data
        records = self._fetch_report_data(table_name)

        # Return empty offset since this is snapshot ingestion
        return records, {}

    def _fetch_report_data(self, table_name: str) -> Iterator[Dict]:
        """
        Fetch all data for a report using pagination.

        Args:
            table_name: Name of the report type

        Yields:
            Report records as dictionaries
        """
        config = self._report_configs[table_name]

        offset = 0
        limit = 100000  # Max per request
        has_more = True

        while has_more:
            # Build request body
            request_body = {
                "dateRanges": [
                    {"startDate": self.start_date, "endDate": self.end_date}
                ],
                "dimensions": config["dimensions"],
                "metrics": config["metrics"],
                "limit": limit,
                "offset": offset,
                "keepEmptyRows": False,
            }

            # Make API request
            url = f"{self.base_url}/properties/{self.property_id}:runReport"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            }

            response = requests.post(url, headers=headers, json=request_body)

            if response.status_code != 200:
                raise Exception(
                    f"GA4 API error for {table_name}: {response.status_code} {response.text}"
                )

            data = response.json()

            # Extract dimension and metric headers
            dimension_headers = [h["name"] for h in data.get("dimensionHeaders", [])]
            metric_headers = [h["name"] for h in data.get("metricHeaders", [])]

            # Process rows
            rows = data.get("rows", [])

            if not rows:
                break

            for row in rows:
                # Transform row to dict
                record = self._transform_row(
                    row, dimension_headers, metric_headers, config
                )
                yield record

            # Check if there are more pages
            row_count = len(rows)
            if row_count < limit:
                has_more = False
            else:
                offset += limit

            # Rate limiting - be nice to the API
            time.sleep(0.1)

    def _transform_row(
        self,
        row: Dict,
        dimension_headers: List[str],
        metric_headers: List[str],
        config: Dict,
    ) -> Dict:
        """
        Transform a GA4 API row to match our schema.

        Args:
            row: Raw row from GA4 API
            dimension_headers: List of dimension names
            metric_headers: List of metric names
            config: Report configuration

        Returns:
            Transformed record
        """
        record = {}

        # Extract dimension values
        dimension_values = row.get("dimensionValues", [])
        for i, dim_name in enumerate(dimension_headers):
            if i < len(dimension_values):
                record[dim_name] = dimension_values[i].get("value")

        # Extract metric values
        metric_values = row.get("metricValues", [])
        for i, metric_name in enumerate(metric_headers):
            if i < len(metric_values):
                value_str = metric_values[i].get("value")

                # Convert to appropriate type
                if metric_name in [
                    "activeUsers",
                    "sessions",
                    "screenPageViews",
                    "eventCount",
                    "conversions",
                    "newUsers",
                ]:
                    # Integer metrics
                    try:
                        record[metric_name] = int(value_str) if value_str else None
                    except (ValueError, TypeError):
                        record[metric_name] = None
                else:
                    # Decimal metrics (rates, durations, revenue)
                    try:
                        record[metric_name] = float(value_str) if value_str else None
                    except (ValueError, TypeError):
                        record[metric_name] = None

        # Generate composite key
        key_parts = []
        for key_field in config["primary_key"]:
            value = record.get(key_field, "")
            # Handle null/empty values
            key_parts.append(str(value) if value else "(not set)")

        record["_composite_key"] = "|".join(key_parts)

        return record

    def test_connection(self) -> Dict:
        """
        Test the connection to GA4 API.

        Returns:
            Dictionary with status and message
        """
        try:
            # Try to get metadata about the property
            url = f"{self.base_url}/properties/{self.property_id}/metadata"
            headers = {"Authorization": f"Bearer {self.access_token}"}

            response = requests.get(url, headers=headers)

            if response.status_code == 200:
                return {"status": "success", "message": "Connection successful"}
            else:
                return {
                    "status": "error",
                    "message": f"API error: {response.status_code} {response.text}",
                }
        except Exception as e:
            return {"status": "error", "message": f"Connection failed: {str(e)}"}

