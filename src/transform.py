from datetime import datetime, timedelta


POST_START = datetime(2010, 8, 1)
POST_END = datetime(2010, 9, 24)
OBSERVATION_END = datetime(2010, 10, 1)
RESPONSE_WINDOW = timedelta(days=7)


def parse_timestamp(value):
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def clean_users(users):
    accounts = {}
    for user in users:
        user_id = user["id"]
        account_type = user["type"]
        if user_id.strip().lower() in ("", "null", "\\n"):
            raise ValueError("Konto saknar ID.")
        if account_type not in ("user", "group"):
            raise ValueError(f"Okänd kontotyp för {user_id}: {account_type!r}")
        if user_id in accounts and accounts[user_id] != account_type:
            raise ValueError(f"Motstridiga kontotyper för {user_id}.")
        accounts[user_id] = account_type

    for user_id, account_type in accounts.items():
        yield {"id": user_id, "type": account_type}


def clean_likes(likes):
    earliest = {}
    for like in likes:
        pair = (like["userID"], like["PostID"])
        if any(value.strip().lower() in ("", "null", "\\n") for value in pair):
            raise ValueError(f"Like saknar konto- eller inläggs-ID: {pair!r}")
        timestamp = parse_timestamp(like["Timestamp"])
        if pair not in earliest or timestamp < earliest[pair]:
            earliest[pair] = timestamp

    for (user_id, post_id), timestamp in earliest.items():
        yield {"userID": user_id, "PostID": post_id, "Timestamp": timestamp}


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
