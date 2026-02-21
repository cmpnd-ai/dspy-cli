"""
Locust load test for dspy-cli.

Single-scenario run:
    locust -f tests/load/locustfile.py \
           --host http://localhost:8000 \
           --headless -u 100 -r 10 \
           --run-time 60s \
           --csv results/test

Matrix run (preferred):
    bash tests/load/run_matrix.sh
"""
import uuid
from locust import HttpUser, task, between, events


def unique_payload():
    """Generate a unique question per request to defeat any caching layer."""
    return {"question": f"What is the capital of France? [{uuid.uuid4().hex[:8]}]"}


class SyncModuleUser(HttpUser):
    """Hits the sync-fallback module (no aforward)."""
    wait_time = between(0.01, 0.1)
    weight = 1

    @task
    def call_simple_predict(self):
        with self.client.post(
            "/SimplePredict",
            json=unique_payload(),
            catch_response=True
        ) as response:
            if response.status_code != 200:
                response.failure(f"Got {response.status_code}: {response.text[:200]}")
            elif "answer" not in response.json():
                response.failure("Missing 'answer' in response")


class AsyncModuleUser(HttpUser):
    """Hits the native async module (has aforward)."""
    wait_time = between(0.01, 0.1)
    weight = 1

    @task
    def call_async_predict(self):
        with self.client.post(
            "/AsyncPredict",
            json=unique_payload(),
            catch_response=True
        ) as response:
            if response.status_code != 200:
                response.failure(f"Got {response.status_code}: {response.text[:200]}")
            elif "answer" not in response.json():
                response.failure("Missing 'answer' in response")


@events.quitting.add_listener
def on_quit(environment, **kwargs):
    """Fail CI if error rate exceeds threshold."""
    if environment.runner.stats.total.fail_ratio > 0.01:
        print(f"ERROR: Failure rate {environment.runner.stats.total.fail_ratio:.1%} > 1%")
        environment.process_exit_code = 1
