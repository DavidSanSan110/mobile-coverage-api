"""Locust load test scenarios for the mobile-coverage-api.

Three scenarios:
  single_address  (weight 3) — baseline latency floor
  batch_5         (weight 2) — confirms asyncio.gather: latency ≈ single_address
  batch_20        (weight 1) — stress the gather pattern at higher fan-out

If the async design is correct, batch_5 latency should be roughly equal to
single_address latency (all 5 geocoding requests fire in parallel).

Run (server must be running on http://localhost:8000):

    uv run locust -f locust/locustfile.py --headless \\
        -u 20 -r 5 --run-time 60s \\
        --host http://localhost:8000 \\
        --html locust/results/report.html \\
        --csv locust/results/stats
"""

import random

from locust import HttpUser, between, task

SAMPLE_ADDRESSES = [
    "157 boulevard Mac Donald 75019 Paris",
    "20 Rue de la Paix 75002 Paris",
    "1 Place du General de Gaulle 13001 Marseille",
    "1 Place Bellecour 69002 Lyon",
    "10 Rue de la Republique 69001 Lyon",
    "5 Allee des Roses 33000 Bordeaux",
    "12 Rue du Faubourg Saint-Antoine 75012 Paris",
    "3 Rue de Rivoli 75001 Paris",
    "15 Cours Mirabeau 13100 Aix-en-Provence",
    "2 Place de la Comedie 34000 Montpellier",
]


class CoverageUser(HttpUser):
    wait_time = between(0.5, 2)

    @task(3)
    def single_address(self) -> None:
        self.client.post(
            "/coverage",
            json={"id1": random.choice(SAMPLE_ADDRESSES)},
            name="/coverage [1 address]",
        )

    @task(2)
    def batch_5_addresses(self) -> None:
        payload = {f"id{i}": random.choice(SAMPLE_ADDRESSES) for i in range(5)}
        self.client.post(
            "/coverage",
            json=payload,
            name="/coverage [5 addresses]",
        )

    @task(1)
    def batch_20_addresses(self) -> None:
        payload = {f"id{i}": random.choice(SAMPLE_ADDRESSES) for i in range(20)}
        self.client.post(
            "/coverage",
            json=payload,
            name="/coverage [20 addresses]",
        )
