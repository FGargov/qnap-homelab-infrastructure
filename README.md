# QNAP Homelab Infrastructure

A home infrastructure project on a QNAP TS-473A, covering Nextcloud
and MariaDB disaster recovery, monitoring, and deployment automation.

## Verified disaster recovery

- Restored Nextcloud 34.0.5 and MariaDB in isolated Docker containers.
- Confirmed that the restored Nextcloud responded over HTTP.
- Verified 82 user files by comparing the working copy with the HBS 3
  restore using rsync checksums.

## Next steps

- Document the recovery procedure and test results in Markdown.
- Define Prometheus and Grafana in Docker Compose.
- Automate monitoring deployment with Ansible roles.

## Monitoring

The Docker Compose stack uses Prometheus and Blackbox Exporter to monitor
Nextcloud and ONLYOFFICE. Grafana loads the dashboard and alert rules from
version-controlled files and sends email notifications via SMTP.

See the [monitoring guide](docs/monitoring.md) for setup and verification.
