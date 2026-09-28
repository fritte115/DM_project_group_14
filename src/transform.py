from datetime import datetime, timedelta


POST_START = datetime(2010, 8, 1)
POST_END = datetime(2010, 9, 24)
OBSERVATION_END = datetime(2010, 10, 1)
RESPONSE_WINDOW = timedelta(days=7)


def parse_timestamp(value):
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def filter_entries(entries):
    for entry in entries:
        published_at = parse_timestamp(entry["Timestamp"])
        if POST_START <= published_at < POST_END:
            yield {**entry, "Timestamp": published_at}


def is_response_in_window(published_at, response_at):
    return (
        POST_START <= published_at < POST_END
        and published_at <= response_at < published_at + RESPONSE_WINDOW
        and response_at < OBSERVATION_END
    )
