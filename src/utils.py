import logging
from datetime import datetime
import re

def parse_time_string(time_str: str):
    """Parse a comma separated string of hours and hour ranges.

    Args:
        time_str: String like ``"9, 13-15, 20"``.

    Returns:
        List of dicts in the form ``{"hour": int}`` sorted by hour.
    """
    times_list = []
    if not time_str:
        return times_list

    for part in time_str.split(','):
        part = part.strip()
        if not part:
            continue

        range_match = re.match(r'^(\d{1,2})-(\d{1,2})$', part)
        if range_match:
            try:
                start = int(range_match.group(1))
                end = int(range_match.group(2))
                if 0 <= start <= 23 and 0 <= end <= 23 and start <= end:
                    for hour in range(start, end + 1):
                        time_obj = {"hour": hour}
                        if time_obj not in times_list:
                            times_list.append(time_obj)
                else:
                    logging.warning(f"Invalid hour range: {part}")
            except ValueError:
                logging.warning(f"Invalid number in range: {part}")
        else:
            try:
                hour = int(part)
                if 0 <= hour <= 23:
                    time_obj = {"hour": hour}
                    if time_obj not in times_list:
                        times_list.append(time_obj)
                else:
                    logging.warning(f"Invalid hour: {part}")
            except ValueError:
                logging.warning(f"Invalid time format: {part}")

    times_list.sort(key=lambda x: x['hour'])
    return times_list

# Example utility function (though logging handles formatting now)
# def format_timestamp(dt_object=None):
#     """Formats a datetime object into the desired string format."""
#     if dt_object is None:
#         dt_object = datetime.now()
#     try:
#         # Format: Jan 05 2025 03:45:48 PM
#         return dt_object.strftime('%b %d %Y %I:%M:%S %p')
#     except Exception as e:
#         logging.error(f"Error formatting timestamp: {e}")
#         return str(dt_object) # Fallback to default string representation

# Add other potential utility functions here if needed later.
# For example, functions to validate input, parse specific data formats, etc.

if __name__ == "__main__":
    print("This is a utility module, not meant to be run directly.")
    # now = datetime.now()
    # print(f"Current time formatted: {format_timestamp(now)}")
