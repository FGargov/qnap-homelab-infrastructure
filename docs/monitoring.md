# Monitor existing Nextcloud and ONLYOFFICE instances

The Rocky Linux VM runs Prometheus, Blackbox Exporter, and Grafana with Docker Compose. Prometheus scrapes Blackbox Exporter, which sends HTTP health checks to Nextcloud and ONLYOFFICE on the QNAP. Grafana queries Prometheus for the dashboard and alert rules and sends email through SMTP.

| Service | Healthy response |
| --- | --- |
| Nextcloud | HTTP 200 from `status.php`, with `installed: true`, `maintenance: false`, and `needsDbUpgrade: false` in the JSON response |
| ONLYOFFICE | HTTP 200 from `healthcheck` with a body of `true` |

A successful probe produces `probe_success = 1`. A failed probe produces `0`. Grafana checks each rule every minute and waits for the failure to persist for two minutes before firing. The Nextcloud panel displays the latest status. The ONLYOFFICE panel displays status over the selected time range.

## Prerequisites

Run the commands from the repository root on the monitoring VM. Install Docker
Engine and the Docker Compose plugin. Confirm the VM can reach the actual
Nextcloud `status.php` and ONLYOFFICE `healthcheck` URLs from both the VM and
its Docker network.

The bundled [Prometheus configuration](../prometheus/prometheus.yml) contains
`example.test` URLs. For a fresh deployment, put the actual URLs in a copy kept
on the VM outside the checkout:

```bash
install -d -m 700 "$HOME/.config/qnap-monitoring"
cp -n prometheus/prometheus.yml "$HOME/.config/qnap-monitoring/prometheus.yml"
chmod 644 "$HOME/.config/qnap-monitoring/prometheus.yml"
nano "$HOME/.config/qnap-monitoring/prometheus.yml"
```

Set `QNAP_PROMETHEUS_CONFIG` in the VM's SMTP environment file to the
**absolute path** of the copied YAML. Prometheus reads the file as its
container user, so the mounted file must be readable inside the container.
If your running stack already uses a working repository configuration, you can
leave this variable unset and keep those working URLs.

## Configure email

The Grafana provisioning override reads an environment file on the VM. If you
already configured Gmail for this stack, open that file and add
`QNAP_ALERT_EMAIL`. For a fresh setup, create a private file and open it:

```bash
install -d -m 700 "$HOME/.config/qnap-monitoring"
smtp_env="$HOME/.config/qnap-monitoring/grafana-smtp.env"
(umask 077 && touch "$smtp_env")
chmod 600 "$smtp_env"
nano "$smtp_env"
```

Use the following settings with your actual values.

```dotenv
GF_SMTP_HOST=smtp.gmail.com:465
GF_SMTP_USER=sender@example.com
GF_SMTP_PASSWORD=REPLACE_WITH_APP_PASSWORD
GF_SMTP_FROM_ADDRESS=sender@example.com
GF_SMTP_FROM_NAME=QNAP Grafana
QNAP_ALERT_EMAIL=recipient@example.com
# For live targets kept outside the checkout, uncomment and set the actual VM path.
# QNAP_PROMETHEUS_CONFIG=/home/operator/.config/qnap-monitoring/prometheus.yml
```

For Gmail, use the sender's full Gmail address and a Google App Password. The recipient can use the same address. Keep the SMTP environment file on the VM.

## Start with a clean Grafana database

The provisioning override adds the versioned Grafana dashboard, alert rules, and `qnap-email` contact point to a clean instance. If a Grafana database already contains these UI-created rules, use the isolated verification below before migrating. Grafana can report a provisioning conflict when rules with the same UIDs are already present.

```bash
compose_files=(-f compose/monitoring.compose.yml -f compose/grafana-provisioning.compose.yml)
smtp_env="$HOME/.config/qnap-monitoring/grafana-smtp.env"

sudo docker compose --env-file "$smtp_env" "${compose_files[@]}" config -q &&
sudo docker compose --env-file "$smtp_env" "${compose_files[@]}" up -d &&
sudo docker compose --env-file "$smtp_env" "${compose_files[@]}" ps
```

Grafana listens on port 3000 on the VM's loopback interface. From your workstation, open an SSH tunnel and browse to `http://127.0.0.1:3000`.

```bash
ssh -N -L 127.0.0.1:3000:127.0.0.1:3000 USER@VM_IP
```

## Verify on a separate Compose project

Use the variables from the previous section. The separate project creates its own Grafana database and Prometheus storage. Grafana uses VM port 3001 for this check.

```bash
sudo docker compose --env-file "$smtp_env" "${compose_files[@]}"   -p qnap-monitoring-v1-check up -d prometheus blackbox-exporter &&
sudo docker compose --env-file "$smtp_env" "${compose_files[@]}"   -p qnap-monitoring-v1-check run --rm --no-deps   --publish 127.0.0.1:3001:3000 grafana
```

Open a second SSH tunnel from your workstation.

```bash
ssh -N -L 127.0.0.1:3001:127.0.0.1:3001 USER@VM_IP
```

Browse to `http://127.0.0.1:3001`. On a fresh Grafana database, sign in with `admin` as both username and initial password, then change the password when prompted.

1. Open **Dashboards** and confirm that **QNAP - NextCloud and OnlyOffice** shows both service panels.
2. Open **Alerting → Alert rules** and confirm that the `qnap-services` group contains both availability rules. If both services are healthy, expect both rules to reach **Normal**.
3. Open **Alerting → Notification configuration → Contact points** and find `qnap-email`.
4. To test automatic notification without interrupting either service, create a temporary Grafana-managed rule named `TEST - QNAP email`. Select Prometheus and use the instant PromQL query `vector(0)` with the condition **IS BELOW 1**. Create a separate evaluation group named `qnap-email-test` with a one-minute interval. Set a two-minute pending period and select the `qnap-email` contact point.
5. Wait for the temporary rule to reach **Firing** and check for the email with the same rule name. Delete the temporary rule after the test.

Press **Ctrl+C** in the terminal running the verification Grafana container, then stop the verification project:

```bash
sudo docker compose --env-file "$smtp_env" "${compose_files[@]}"   -p qnap-monitoring-v1-check down
```

The verification volumes are retained. Run a future clean verification under a new project name if you need a blank database again.
