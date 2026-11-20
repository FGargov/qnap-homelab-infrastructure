# QNAP Homelab Infrastructure

This project documents how I recover and monitor services in my homelab on a QNAP TS-473A. It covers a verified recovery exercise for Nextcloud and MariaDB, including file checks against an HBS 3 restore, and a reproducible monitoring stack for Nextcloud and ONLYOFFICE.

## What the project covers

### Disaster recovery

- Restored Nextcloud 34.0.5 and MariaDB in isolated Docker containers.
- Confirmed that the restored Nextcloud instance responded over HTTP.
- Verified 82 user files by comparing the working copy with the HBS 3 restore using rsync checksums.

### Monitoring and alerting

Docker Compose runs the monitoring stack on a Rocky Linux VM. Blackbox Exporter checks the Nextcloud status endpoint and the ONLYOFFICE health endpoint. Prometheus collects the probe results, and Grafana displays service availability and evaluates alert rules.

Grafana loads its Prometheus data source, dashboard, alert rules, and email contact point from version-controlled configuration. I verified the dashboard and rules on a clean Grafana instance and confirmed that a test alert reached Gmail through SMTP.

## Repository layout

| Path | Contents |
| --- | --- |
| `compose/` | Docker Compose definitions for the monitoring stack and Grafana provisioning |
| `prometheus/` | Scrape configuration and monitored targets |
| `blackbox/` | HTTP health-check modules for Nextcloud and ONLYOFFICE |
| `grafana/` | Dashboard JSON and provisioning for the data source, dashboard, and alerting |
| `docs/` | Recovery and monitoring guides |

## Getting started

The monitoring stack requires Docker Engine, the Docker Compose plugin, and network access from the monitoring host to both service endpoints. Set the target URLs for your environment in `prometheus/prometheus.yml`. Store SMTP credentials and the alert recipient in a local environment file outside Git. Grafana is bound to the monitoring host's loopback interface and can be accessed remotely through an SSH tunnel.

## Documentation

- [Disaster recovery guide](docs/disaster-recovery.md) — Nextcloud and MariaDB restore procedure and verification results.
- [Monitoring guide](docs/monitoring.md) — Docker Compose setup, Grafana provisioning, SMTP settings, and validation on a separate instance.
- [Monitoring runbook](docs/monitoring-runbook.md) — Architecture, local reviewer demo, troubleshooting, and verification evidence.

## Next step

Automate monitoring deployment with Ansible roles.
