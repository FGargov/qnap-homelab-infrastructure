# Deploy monitoring with Ansible

Run Ansible from your Ubuntu workstation. It connects over SSH to the Rocky
Linux VM and applies the monitoring Compose project on the VM. The operator
chooses the Git revision and prepares the VM's Docker installation and local
SMTP file. The playbook uses the existing Grafana and Prometheus volumes when
it adopts a project with the same Compose name.

| Machine | Requirements |
| --- | --- |
| Ubuntu workstation | Python 3.12–3.14, SSH access to the VM, Ansible Core 2.20, and the collection in `ansible/requirements.yml` |
| Rocky Linux monitoring VM | Python 3.9–3.14, Docker Engine running, Compose plugin 2.18 or newer, a working checkout, and an SSH account with sudo access |
| QNAP applications | Nextcloud and ONLYOFFICE health endpoints reachable from the VM and its Docker network |

The [reviewer demo](reviewer-demo.md) uses a Compose override that requires
Compose 2.24.4 or newer.

## 1. Prepare the Rocky Linux VM

SSH to the VM from your workstation using your actual account and address.

```bash
ssh operator@rocky-vm.example.test
```

Confirm Docker and Python work on the VM and identify any existing Compose
project before deploying.

```bash
python3 --version
sudo docker version
sudo docker compose version
sudo docker compose ls
sudo docker volume ls --filter label=com.docker.compose.project=qnap-monitoring
```

Update the existing checkout to the intended Git revision after reviewing
`git status --short`. Continue to use the same live checkout and Compose
project name when adopting an existing stack. A different project name creates
a different set of named volumes. If Grafana has UI-managed rules with the same
UIDs as the provisioned rules, use the
[isolated verification procedure](monitoring.md#verify-on-a-separate-compose-project)
before applying provisioning to that database.

Configure the two live probe URLs and the VM's local SMTP file using the
[monitoring setup guide](monitoring.md). Retain any existing working URLs and
credentials. Note the absolute paths to the checkout and SMTP file for the
inventory. Use `chmod 600` on the SMTP file.

## 2. Install Ansible on Ubuntu

Run from your workstation's repository root. If Ubuntu is missing the Python
venv package, install it with `sudo apt install python3-venv`.

```bash
python3 --version
python3 -m venv "$HOME/.venvs/qnap-ansible"
source "$HOME/.venvs/qnap-ansible/bin/activate"
python -m pip install 'ansible-core>=2.20,<2.21'
ansible-galaxy collection install -r ansible/requirements.yml
ansible-playbook --version
```

## 3. Create your inventory

Keep your real inventory outside the project checkout.

```bash
install -d -m 700 "$HOME/.config/qnap-monitoring"
inventory="$HOME/.config/qnap-monitoring/inventory.yml"
cp -n ansible/inventory.example.yml "$inventory"
chmod 600 "$inventory"
nano "$inventory"
```

| Field | Value to enter |
| --- | --- |
| `ansible_host` | The Rocky VM's IP or DNS name |
| `ansible_user` | Your SSH account on Rocky |
| `ansible_python_interpreter` | The VM's Python path, normally `/usr/bin/python3` |
| `monitoring_project_dir` | Absolute path to the repository on Rocky |
| `monitoring_smtp_env_file` | Absolute path to the private SMTP file on Rocky |
| `monitoring_project_name` | Optional. Set it if your existing Compose project uses a name other than `qnap-monitoring`. |

## 4. Check and apply

From the Ubuntu checkout, with the virtual environment active, run these in
order. Stop at a failing command. Omit `-K` if the Rocky SSH user has
passwordless sudo.

```bash
inventory="$HOME/.config/qnap-monitoring/inventory.yml"
ansible-playbook -i "$inventory" ansible/playbook.yml --syntax-check
ansible -i "$inventory" monitoring -m ansible.builtin.ping
ansible-playbook -i "$inventory" ansible/playbook.yml --tags preflight -K
ansible-playbook -i "$inventory" ansible/playbook.yml --check -K
ansible-playbook -i "$inventory" ansible/playbook.yml -K
```

| Step | Expected result |
| --- | --- |
| Syntax and ping | Ansible loads the playbook and the VM returns `pong`. |
| Preflight | Ansible checks the files and their permissions, Docker access, and the merged Compose configuration. |
| Check | Compose previews the changes. |
| Apply | Compose starts or reconciles the services. Ansible waits for Grafana to report `database: ok`. |

To diagnose a Compose validation failure, run the following from the Rocky
checkout with the same SMTP file and project name used in inventory. The
`--quiet` option avoids printing the resolved configuration.

```bash
smtp_env="$HOME/.config/qnap-monitoring/grafana-smtp.env"
sudo docker compose -p qnap-monitoring --env-file "$smtp_env" \
  -f compose/monitoring.compose.yml -f compose/grafana-provisioning.compose.yml \
  config --quiet
```

## 5. Verify the deployment

On the VM, use the project name from inventory.

```bash
sudo docker ps --filter label=com.docker.compose.project=qnap-monitoring
curl -fsS http://127.0.0.1:3000/api/health
```

Expect Grafana, Prometheus, and Blackbox Exporter to be running. From the
Ubuntu workstation open the [SSH tunnel](monitoring.md#start-with-a-clean-grafana-database).
In Grafana **Explore**, select **Prometheus** and run this as an instant query.

```promql
probe_success{job=~"nextcloud|onlyoffice"}
```

Expect a result of `1` for each healthy service. The playbook checks Grafana
startup even when an application is unavailable. Check both probe results
and the alert rules to confirm the monitoring targets separately.

## Reapply changes or roll back

Run the same playbook after updating the checkout or SMTP environment. Compose
reconciles changes to the service definitions and container environment. After
changing the contents of a bind-mounted Prometheus, Blackbox, or provisioning
file, recreate the monitoring containers once to reload the mounted config.
Expect a brief monitoring interruption.

```bash
ansible-playbook -i "$inventory" ansible/playbook.yml -K -e monitoring_recreate=true
```

For a configuration rollback, return the VM checkout and any edited local
configuration to the last known-good revision or copy, then run the same
recreation command. Keep the existing Compose project name and volumes. Use
the [monitoring runbook](monitoring-runbook.md) for diagnosis and follow the
[recovery runbook](disaster-recovery.md) for Nextcloud or MariaDB data recovery.

[Ansible Python support matrix](https://docs.ansible.com/projects/ansible/latest/reference_appendices/release_and_maintenance.html)
· [Compose module reference](https://docs.ansible.com/projects/ansible/latest/collections/community/docker/docker_compose_v2_module.html)
