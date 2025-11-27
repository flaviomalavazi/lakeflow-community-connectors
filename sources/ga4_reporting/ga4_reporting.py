# Google Analytics 4 Reporting Data API connector implementation

import requests
import json
import time
import base64
import os
from typing import Dict, List, Iterator
from datetime import datetime, timedelta
from pyspark.sql.types import (
    StructType,
    StructField,
    StringType,
    LongType,
    DoubleType,
    BooleanType,
)

try:
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request
    GOOGLE_AUTH_AVAILABLE = True
except ImportError:
    GOOGLE_AUTH_AVAILABLE = False


class LakeflowConnect:
    def __init__(self, options: Dict[str, str]) -> None:
        """
        Initialize the GA4 Reporting connector with API credentials.

        Args:
            options: Dictionary containing:
                - service_account_json: Google Service Account credentials as:
                    * JSON string (escaped)
                    * JSON object (dict)
                    * File path to .json file (string ending with .json)
                - property_id: GA4 property ID (e.g., "123456789")
                - start_date: Start date for reports (default: "30daysAgo")
                - end_date: End date for reports (default: "yesterday")
        """
        self.property_id = options["property_id"]
        self.start_date = options.get("start_date", "30daysAgo")
        self.end_date = options.get("end_date", "yesterday")
        self.report_configs = options.get("report_configs", self._build_default_report_configurations())

        # Parse service account credentials from various input formats
        self.service_account_info = self._parse_service_account_credentials(
            options.get("service_account_json", options)
        )

        # Get access token
        self.access_token = self._get_access_token()
        self.token_expiry = None

        # Base URL for GA4 Data API
        self.base_url = "https://analyticsdata.googleapis.com/v1beta"

        # Build report configurations
        self._report_configs = self._build_default_report_configurations()

    def _parse_service_account_credentials(self, credentials_input) -> Dict:
        """
        Parse service account credentials from various input formats.

        Args:
            credentials_input: Can be:
                - A JSON string (escaped)
                - A dictionary (already parsed JSON)
                - A file path to a .json file

        Returns:
            Dictionary containing service account credentials

        Raises:
            ValueError: If credentials cannot be parsed
        """
        # Case 1: Already a dictionary with service account fields
        if isinstance(credentials_input, dict):
            # Check if it looks like service account credentials directly
            if "type" in credentials_input and credentials_input.get("type") == "service_account":
                return credentials_input
            # Check if service_account_json is nested in the dict
            elif "service_account_json" in credentials_input:
                return self._parse_service_account_credentials(
                    credentials_input["service_account_json"]
                )
            else:
                raise ValueError(
                    "Invalid credentials format: dictionary must contain 'type': 'service_account' "
                    "or 'service_account_json' key"
                )

        # Case 2: String - could be JSON or file path
        elif isinstance(credentials_input, str):
            # Check if it's a file path
            if credentials_input.endswith(".json"):
                try:
                    with open(credentials_input, "r") as f:
                        return json.load(f)
                except FileNotFoundError:
                    raise ValueError(
                        f"Service account JSON file not found: {credentials_input}"
                    )
                except json.JSONDecodeError as e:
                    raise ValueError(
                        f"Invalid JSON in service account file {credentials_input}: {str(e)}"
                    )

            # Try to parse as JSON string
            try:
                parsed = json.loads(credentials_input)
                if isinstance(parsed, dict) and parsed.get("type") == "service_account":
                    return parsed
                else:
                    raise ValueError(
                        "Parsed JSON does not contain valid service account credentials"
                    )
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"service_account_json must be valid JSON string, file path, or dict. "
                    f"Parse error: {str(e)}"
                )

        else:
            raise ValueError(
                f"service_account_json must be a string or dict, got {type(credentials_input)}"
            )

    def build_report_configurations(self, report_configs: Dict) -> None:
        """
        Build and return GA4 report configurations.
        
        Args:
            report_configs: Dictionary containing report configurations
        """
        self._report_configs = report_configs

    def _build_default_report_configurations(self) -> Dict:
        """
        Build and return GA4 report configurations.
        
        Each report configuration defines:
        - dimensions: List of dimension objects to group by
        - metrics: List of metric objects to aggregate
        - primary_key: List of dimension names that form the composite key
        
        Returns:
            Dictionary mapping report names to their configurations
        """
        return {
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
        Get access token using service account credentials.

        Returns:
            Access token string
        """
        if GOOGLE_AUTH_AVAILABLE:
            # Use google-auth library if available (preferred method)
            scopes = ["https://www.googleapis.com/auth/analytics.readonly"]
            credentials = service_account.Credentials.from_service_account_info(
                self.service_account_info, scopes=scopes
            )
            credentials.refresh(Request())
            self.token_expiry = credentials.expiry
            return credentials.token
        else:
            # Fallback to manual JWT creation if google-auth not available
            return self._create_jwt_token()

    def _create_jwt_token(self) -> str:
        """
        Create JWT token manually for service account authentication.
        This is a fallback method when google-auth library is not available.

        Returns:
            Access token string
        """
        import hashlib
        import hmac

        # JWT Header
        header = {"alg": "RS256", "typ": "JWT"}
        header_encoded = base64.urlsafe_b64encode(
            json.dumps(header).encode()
        ).decode().rstrip("=")

        # JWT Claim Set
        now = int(time.time())
        claim = {
            "iss": self.service_account_info["client_email"],
            "scope": "https://www.googleapis.com/auth/analytics.readonly",
            "aud": "https://oauth2.googleapis.com/token",
            "exp": now + 3600,
            "iat": now,
        }
        claim_encoded = base64.urlsafe_b64encode(
            json.dumps(claim).encode()
        ).decode().rstrip("=")

        # Create signature
        message = f"{header_encoded}.{claim_encoded}"

        # Import cryptography for RSA signing
        try:
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import padding
            from cryptography.hazmat.backends import default_backend

            # Load private key
            private_key_str = self.service_account_info["private_key"]
            private_key = serialization.load_pem_private_key(
                private_key_str.encode(), password=None, backend=default_backend()
            )

            # Sign the message
            signature = private_key.sign(
                message.encode(),
                padding.PKCS1v15(),
                hashes.SHA256()
            )

            signature_encoded = base64.urlsafe_b64encode(signature).decode().rstrip("=")

            # Combine to create JWT
            jwt_token = f"{message}.{signature_encoded}"

            # Exchange JWT for access token
            token_url = "https://oauth2.googleapis.com/token"
            data = {
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": jwt_token,
            }

            response = requests.post(token_url, data=data)

            if response.status_code != 200:
                raise Exception(
                    f"Failed to get access token: {response.status_code} {response.text}"
                )

            token_data = response.json()
            self.token_expiry = datetime.now() + timedelta(seconds=token_data.get("expires_in", 3600))
            return token_data["access_token"]

        except ImportError:
            raise Exception(
                "Neither google-auth nor cryptography library is available. "
                "Please install one of them: 'pip install google-auth' or 'pip install cryptography'"
            )

    def _refresh_token_if_needed(self):
        """
        Refresh the access token if it's expired or about to expire.
        """
        if self.token_expiry is None or datetime.now() >= self.token_expiry - timedelta(minutes=5):
            self.access_token = self._get_access_token()

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
            # Refresh token if needed
            self._refresh_token_if_needed()

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
            # Refresh token if needed
            self._refresh_token_if_needed()

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

