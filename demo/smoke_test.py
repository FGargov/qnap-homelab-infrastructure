import json
import subprocess
import sys
import time
from http.client import HTTPException
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from health_endpoints import FAILURE_FLAG


JOBS = {"nextcloud", "onlyoffice"}
RULES = {"Nextcloud unavailable", "ONLYOFFICE unavailable"}


def get_json(url):
    with urlopen(url, timeout=5) as response:
        return json.load(response)


def wait_for(description, check, timeout):
    print(f"Waiting for {description} (up to {timeout}s)...", flush=True)
    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        try:
            if check():
                print(f"PASS: {description}", flush=True)
                return
            last_error = None
        except (URLError, TimeoutError, HTTPException) as error:
            last_error = error
        time.sleep(5)
    raise RuntimeError(f"Timed out waiting for {description}. Last HTTP error: {last_error}")


def metric_values(metric):
    query = f'{metric}{{job=~"nextcloud|onlyoffice"}}'
    result = get_json(
        "http://127.0.0.1:19090/api/v1/query?" + urlencode({"query": query})
    )
    series = result["data"]["result"]
    if len(series) != len(JOBS):
        return {}
    return {item["metric"]["job"]: float(item["value"][1]) for item in series}


def probes_are(expected):
    return (
        metric_values("probe_success") == dict.fromkeys(JOBS, expected)
        and metric_values("up") == dict.fromkeys(JOBS, 1)
    )


def messages():
    return get_json("http://127.0.0.1:18025/api/v1/messages")["messages"]


def mailbox_contains(transition, existing_ids):
    subjects = [
        message["Subject"]
        for message in messages()
        if message["ID"] not in existing_ids
        and message["Subject"].startswith(f"[{transition}")
    ]
    return all(any(rule in subject for subject in subjects) for rule in RULES)


def set_target_health(compose, healthy):
    operation = ["rm", "-f"] if healthy else ["touch"]
    subprocess.run(
        [*compose, "exec", "-T", "demo-targets", *operation, str(FAILURE_FLAG)],
        check=True,
    )


def main(compose):
    set_target_health(compose, healthy=True)
    wait_for(
        "Grafana database to be ready",
        lambda: get_json("http://127.0.0.1:13000/api/health")["database"] == "ok",
        120,
    )
    wait_for("both probes healthy", lambda: probes_are(1), 120)
    wait_for("Mailpit API to be ready", lambda: isinstance(messages(), list), 60)
    old_ids = {message["ID"] for message in messages()}

    try:
        set_target_health(compose, healthy=False)
        wait_for("both probes fail but scrapes still succeed", lambda: probes_are(0), 120)
        wait_for("FIRING emails for both rules", lambda: mailbox_contains("FIRING", old_ids), 360)
    finally:
        set_target_health(compose, healthy=True)

    wait_for("both probes recover", lambda: probes_are(1), 120)
    wait_for("RESOLVED emails for both rules", lambda: mailbox_contains("RESOLVED", old_ids), 360)


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except (RuntimeError, subprocess.CalledProcessError) as error:
        sys.exit(str(error))
