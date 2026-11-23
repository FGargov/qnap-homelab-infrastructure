# Review the monitoring stack locally

Use a local Docker host with the Compose plugin v2.24.4 or newer, Python 3, Bash, and access to pull the images in the Compose files. Ports 13000, 18025, and 19090 must be available on loopback. Once you have a checkout of the repository, the demo can run without a QNAP, Gmail credentials, or running copies of Nextcloud and ONLYOFFICE.

The demo runs the repository's Grafana provisioning, Prometheus, Blackbox Exporter, and availability rules. A small HTTP service supplies the two response formats expected by the probes. Mailpit captures notification messages locally. All demo services run under the `qnap-review` Compose project and it has its own Grafana and Prometheus volumes.

## Launch and verify

From the repository root on a host where your account can use Docker, run:

```bash
./demo/reviewer.sh up
./demo/reviewer.sh test
```

If Docker requires root on your host, run each script with `sudo`. The smoke test can take several minutes because it waits for the deployed evaluation interval and pending period.

| Stage | Expected result |
| --- | --- |
| Healthy endpoints | Both services have `probe_success = 1` and `up = 1`. |
| Unhealthy responses | Both endpoints still return HTTP 200, but Nextcloud reports maintenance and ONLYOFFICE returns `false`. Both probes report `0` while `up` stays at `1`. |
| Availability rules fire | Mailpit receives new **FIRING** emails for `Nextcloud unavailable` and `ONLYOFFICE unavailable`. |
| Endpoints recover | Both probes return to `1` and Mailpit receives both **RESOLVED** emails. |

Open Grafana at [127.0.0.1:13000](http://127.0.0.1:13000) and Mailpit at [127.0.0.1:18025](http://127.0.0.1:18025) on the Docker host. A clean Grafana database starts with username `admin` and initial password `admin`. Change the password at the prompt. Find the provisioned dashboard under **Dashboards** and the two rules in the `QNAP` folder under **Alerting**.

If a check times out, leave the demo running and inspect Grafana's alert state or Mailpit's inbox. The test restores healthy responses on normal completion and on handled failures. Run the same test again to reset demo responses after a forced stop. Stop the demo when finished:

```bash
./demo/reviewer.sh down
```

The demo checks monitoring and alert delivery against controlled HTTP responses. To validate the actual application integration, point the [real stack](monitoring.md) at a reachable deployment of both services. Sign in to Nextcloud, create or upload a disposable document, open it in ONLYOFFICE, save an edit, and reopen the file to confirm persistence. The [disaster recovery guide](disaster-recovery.md) covers the separate restore exercise.
