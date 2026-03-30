from datetime import datetime
import pytz

def get_nepal_time():
    nepal_tz = pytz.timezone('Asia/Kathmandu')
    # Return naive datetime representing Nepal time for easier comparison with SQLite
    return datetime.now(nepal_tz).replace(tzinfo=None)

def format_nepal_time(dt, format='%Y-%m-%d %I:%M %p'):
    if not dt:
        return "N/A"
    # Assuming dt is naive Nepal time as per get_nepal_time()
    return dt.strftime(format)

def is_saturday():
    now = get_nepal_time()
    return now.weekday() == 5 # Monday is 0, Saturday is 5
