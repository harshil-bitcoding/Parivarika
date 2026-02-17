import datetime as dt_module
from django.core.exceptions import ValidationError
import dateutil.parser
from datetime import datetime, timezone


def convert_time_format(time_value):
    """
    Convert time value (in milliseconds) to datetime format.
    """
    try:
        if isinstance(time_value, (int, float)):
            if len(str(time_value)) > 10:
                dt = datetime.fromtimestamp(int(time_value) / 1000)
            else:
                dt = datetime.fromtimestamp(int(time_value))

        else:
            if len(str(time_value)) > 10:
                time_str = str(time_value / 1000)
            else:
                time_str = str(time_value)

            dt = datetime.fromisoformat(time_str)

        return dt.isoformat()
    except ValueError:
        raise ValidationError(f"Unknown time format: {time_value}")


def convert_timestamp_format(time_value):
    """
    Convert time value (in milliseconds or ISO 8601 string) to ISO 8601 datetime format.
    """
    try:
        if isinstance(time_value, (int, float)):
            dt_value = datetime.fromtimestamp(int(time_value), tz=timezone.utc)
        elif isinstance(time_value, str):
            dt_value = dateutil.parser.isoparse(time_value)
        elif isinstance(time_value, dt_module):
            dt_value = time_value
        else:
            raise ValueError("Unsupported time format")
        return dt_value.isoformat()
    except (ValueError, TypeError) as e:
        raise ValidationError(f"Unknown time format: {time_value}. Error: {str(e)}")
