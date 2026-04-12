from datetime import datetime, timedelta, timezone

# Define Indian Standard Time (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))

def get_now():
    """Returns the current datetime in Indian Standard Time (IST)."""
    return datetime.now(IST)

def get_now_formatted():
    """Returns IST datetime formatted as string."""
    return get_now().strftime("%Y-%m-%d %H:%M:%S")
