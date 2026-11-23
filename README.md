# QNAP Homelab Infrastructure

This project documents the recovery of Nextcloud and MariaDB and provides a reproducible monitoring stack for Nextcloud and ONLYOFFICE. The live deployment runs on a QNAP TS-473A with a Rocky Linux VM hosting the monitoring services.

## Project workflows

| Task | Guide |
| --- | --- |
| Run the local monitoring demo | Follow the [quick start](#local-demo). You need Docker, Compose 2.24.4 or newer, Bash, and Python 3. |
| Monitor existing Nextcloud and ONLYOFFICE instances | [Prepare the monitoring VM](docs/monitoring.md#prerequisites), then deploy with [Docker Compose](docs/monitoring.md) or [Ansible over SSH](docs/monitoring-deployment.md). |
| Review the backup restore | Read the [recorded recovery exercise](docs/disaster-recovery.md#recorded-exercise) for the database, HTTP, and file checksum results. Repeating it requires a compatible backup and an isolated recovery environment. |

## Local demo

1. Open a terminal in the project directory containing this README.

2. Start the demo containers.

   ```bash
   ./demo/reviewer.sh up
   ```

   The script runs Docker Compose with the base monitoring config, the Grafana provisioning config, and a demo override. The override points Prometheus at a small Python service that mimics the Nextcloud `/status.php` and ONLYOFFICE `/healthcheck` responses. The actual Nextcloud and ONLYOFFICE applications are external to this demo.

3. Open Grafana at [127.0.0.1:13000](http://127.0.0.1:13000) and the local Mailpit inbox at [127.0.0.1:18025](http://127.0.0.1:18025) on the Docker host. On first use, sign in to Grafana with `admin` / `admin` and follow the password prompt.

4. Start the smoke test in a terminal.

   ```bash
   ./demo/reviewer.sh test
   ```

   The test starts with healthy responses, changes both responses to simulate a failure, and then restores them. It checks each probe's `1 → 0 → 1` transition and looks for **FIRING** and **RESOLVED** notifications for both rules in Mailpit. Allow several minutes for the Grafana evaluation and notification intervals.

5. Stop the demo containers.

   ```bash
   ./demo/reviewer.sh down
   ```

Run the script commands with `sudo` if your Docker host requires it. See the [reviewer demo guide](docs/reviewer-demo.md) for the expected results and the separate real-document check.

## Monitor live applications on Rocky Linux

1. Start with a running Rocky Linux VM with Docker and the Compose plugin.
2. Confirm the VM can reach an existing Nextcloud instance and ONLYOFFICE Document Server. Configure their health URLs using the [monitoring setup guide](docs/monitoring.md#prerequisites).
3. Create the [local SMTP environment file](docs/monitoring.md#configure-email). Choose [Docker Compose on the VM](docs/monitoring.md#start-with-a-clean-grafana-database) or [Ansible over SSH](docs/monitoring-deployment.md) to deploy the stack.
4. Open Grafana through the SSH tunnel. Check that both live jobs report `probe_success = 1`. For a separate application-level check, edit, save, and reopen a disposable document in Nextcloud using ONLYOFFICE.

Grafana loads the Prometheus data source, dashboard, alert rules, and email contact point from configuration committed to Git. On the homelab, I verified that the dashboard and rules loaded on an isolated Grafana instance and that a temporary test rule delivered an email to Gmail.

## Disaster recovery results

- Restored Nextcloud 34.0.5 and MariaDB in isolated Docker containers.
- Confirmed that the restored Nextcloud instance responded over HTTP.
- Compared 82 user files from the working copy and the HBS 3 restore using rsync checksums.

See the [disaster recovery guide](docs/disaster-recovery.md) for the procedure and validation evidence.

## Operations

- [Monitoring runbook](docs/monitoring-runbook.md) — Architecture, triage, recovery, and evidence.
- [Monitoring setup](docs/monitoring.md) — Compose, Grafana, SMTP, and isolated verification against live targets.
- [Ansible deployment](docs/monitoring-deployment.md) — SSH inventory, preflight, deployment, verification, and rollback.
