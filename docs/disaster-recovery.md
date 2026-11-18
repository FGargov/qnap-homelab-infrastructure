# QNAP Nextcloud Disaster Recovery Runbook

Use this runbook to restore a Nextcloud application volume and MariaDB SQL
dump into isolated Docker containers on a QNAP TS-473A. The exercise verifies
the database, application startup, local HTTP response, and user-file
checksums. Production cutover requires a separate procedure.

## Recorded exercise

| Check | Observed result |
| --- | --- |
| HBS 3 integrity check | Good |
| HBS 3 restore | 44,792 files, approximately 2.16 GB, zero skipped |
| MariaDB 11.4 import | Exit code 0 and 211 tables |
| SQL row counts | 2,242 file-cache entries, 1 user, 281 app configuration entries |
| Nextcloud | Version 34.0.5, installed, maintenance disabled, no DB upgrade required |
| HTTP | The restored container returned JSON from /status.php |
| User files | 82 regular files and no itemized rsync differences. The rsync exit status was not recorded separately. |
| Test shutdown | Both restore containers reported Exited (0). |

The HBS 3 backup was on the same NAS. The exercise left ONLYOFFICE Docs,
Cloudflare Tunnel, external NAS datasets, and recovery after loss of the entire
NAS for separate tests. Full recovery time was not measured.

## 1. Restore the backup into a separate directory

In HBS 3, select a completed backup version and restore it to an empty
directory dedicated to this exercise. The backup should include hidden files
such as .ncdata and .htaccess. Check the job result for errors and skipped files.
HBS 3 may recreate source directories under the selected destination. Set
RESTORE to the directory that contains nextcloud.sql and nextcloud_volume.

Run the shell steps on the Docker host. Replace these example paths with the
actual HBS restore and separate test workspace paths. Use a fresh test workspace
for a new exercise. If the named test containers or volume already exist,
preserve them and select new names consistently throughout the commands.

~~~bash
RESTORE='/replace/with/hbs-restore/Completed/current'
TEST_ROOT='/replace/with/new/isolated-restore-workspace'
WORK="$TEST_ROOT/working/nextcloud"
SECRETS="$TEST_ROOT/secrets"

sudo test -f "$RESTORE/BACKUP_COMPLETE.txt" &&
sudo test -s "$RESTORE/nextcloud.sql" &&
sudo test -f "$RESTORE/nextcloud_volume/data/.ncdata" &&
sudo test -f "$RESTORE/nextcloud_volume/config/config.php" &&
printf 'Expected backup files found\n'
~~~

Proceed once all checks succeed. Use the same Nextcloud image version as
the backup. For the existing stopped test container, the following command
recovers the image ID used in the exercise.

~~~bash
docker inspect --format '{{.Image}}' nc-restore-app
~~~

For a new restore, set NEXTCLOUD_IMAGE to the matching image ID present on
the host. The test used a locally available image tagged
nextcloud:stable-apache at the time.

## 2. Start an isolated MariaDB instance

Create an internal Docker network and a fresh volume. Generate secrets once
for this volume. The secret generation uses noclobber to protect existing files.

~~~bash
docker network create --driver bridge --internal nc-restore-net
docker volume create nc-restore-dbdata
docker network inspect --format 'Internal={{.Internal}}' nc-restore-net

sudo mkdir -p "$SECRETS"
sudo chmod 700 "$SECRETS"
sudo sh -c '
  set -C
  umask 077
  openssl rand -hex 32 > "$1/db-root-password" &&
  openssl rand -hex 32 > "$1/db-user-password"
' sh "$SECRETS"
~~~

Confirm that the network reports Internal=true and both secrets were created.
Keep the test database port inside the Docker network.

~~~bash
docker run -d --name nc-restore-db --network nc-restore-net --restart no \
  -v nc-restore-dbdata:/var/lib/mysql \
  -v "$SECRETS:/run/secrets:ro" \
  -e MARIADB_ROOT_PASSWORD_FILE=/run/secrets/db-root-password \
  -e MARIADB_DATABASE=nextcloud \
  -e MARIADB_USER=nextcloud \
  -e MARIADB_PASSWORD_FILE=/run/secrets/db-user-password \
  mariadb:11.4

docker exec nc-restore-db sh -ec '
  MYSQL_PWD="$(cat /run/secrets/db-user-password)" \
    mariadb --protocol=tcp -h 127.0.0.1 -u nextcloud nextcloud -e "SELECT 1;"
'
~~~

Wait for the readiness query to succeed. Import once into the empty test
database. This block uses Bash pipefail so a failed read of the dump also
reports a failure.

~~~bash
(
  set -o pipefail
  sudo cat "$RESTORE/nextcloud.sql" |
    docker exec -i nc-restore-db sh -ec '
      export MYSQL_PWD="$(cat /run/secrets/db-root-password)"
      exec mariadb -u root nextcloud
    '
)
printf 'Import exit code: %s\n' "$?"
~~~

Continue after exit code 0. Compare table and row counts with expectations
for the selected backup version. The values above apply to the recorded test.

~~~bash
docker exec nc-restore-db sh -ec '
  MYSQL_PWD="$(cat /run/secrets/db-root-password)" \
    mariadb -u root nextcloud -e "
      SELECT COUNT(*) AS tables_restored FROM information_schema.tables
        WHERE table_schema = DATABASE();
      SELECT COUNT(*) AS file_cache_rows FROM oc_filecache;
      SELECT COUNT(*) AS users FROM oc_users;
      SELECT COUNT(*) AS app_settings FROM oc_appconfig;"
'
~~~

## 3. Prepare the Nextcloud working copy

Check that WORK is inside the separate test workspace. Copy the restored
volume and keep a protected copy of its original config.php.

~~~bash
sudo mkdir -p "$WORK"
sudo rsync -a "$RESTORE/nextcloud_volume/" "$WORK/"
sudo cp -p "$WORK/config/config.php" "$SECRETS/config.php.original" &&
sudo chmod 600 "$SECRETS/config.php.original"
~~~

Set NEXTCLOUD_IMAGE to the verified matching local image ID before running
the next block. Run the PHP edit on the working copy with networking disabled.
It reads the test DB password from a file and prints no configuration values.

~~~bash
docker run --rm --pull never --network none --read-only \
  -v "$WORK/config:/work-config:rw" \
  -v "$SECRETS:/run/secrets:ro" \
  --entrypoint php "$NEXTCLOUD_IMAGE" -r '
    $CONFIG = [];
    require "/work-config/config.php";
    $password = trim(file_get_contents("/run/secrets/db-user-password") ?: "");
    if ($password === "") {
        fwrite(STDERR, "Missing test DB password\n");
        exit(1);
    }
    $CONFIG["dbhost"] = "nc-restore-db:3306";
    $CONFIG["dbname"] = "nextcloud";
    $CONFIG["dbuser"] = "nextcloud";
    $CONFIG["dbpassword"] = $password;
    $CONFIG["maintenance"] = false;
    $CONFIG["trusted_domains"] = ["localhost", "127.0.0.1"];
    $CONFIG["overwrite.cli.url"] = "http://localhost";
    $CONFIG["datadirectory"] = "/var/www/html/data";
    unset($CONFIG["redis"], $CONFIG["memcache.local"],
          $CONFIG["memcache.distributed"], $CONFIG["memcache.locking"],
          $CONFIG["trusted_proxies"], $CONFIG["overwritehost"],
          $CONFIG["overwriteprotocol"], $CONFIG["overwritewebroot"],
          $CONFIG["overwritecondaddr"]);
    $content = "<?php\n" . chr(36) . "CONFIG = " . var_export($CONFIG, true) . ";\n";
    if (file_put_contents("/work-config/config.php", $content, LOCK_EX) === false) {
        fwrite(STDERR, "Cannot write test config.php\n");
        exit(1);
    }
'

docker run --rm --pull never --network none --read-only \
  -v "$WORK/config/config.php:/tmp/config.php:ro" \
  --entrypoint php "$NEXTCLOUD_IMAGE" -l /tmp/config.php
~~~

Start the restore app on the internal network after the PHP lint passes.
The command publishes no ports and mounts only the test working copy.

~~~bash
docker run -d --name nc-restore-app --network nc-restore-net \
  --restart no --pull never \
  --mount "type=bind,source=$WORK,target=/var/www/html" \
  "$NEXTCLOUD_IMAGE"
~~~

## 4. Validate the application and files

~~~bash
docker exec -u www-data nc-restore-app php /var/www/html/occ status
docker exec -u www-data nc-restore-app php /var/www/html/occ user:list

docker exec nc-restore-app php -r '
  $response = @file_get_contents("http://127.0.0.1/status.php");
  if ($response === false) {
      fwrite(STDERR, "HTTP check failed\n");
      exit(1);
  }
  echo $response, PHP_EOL;
'
~~~

Confirm the application version matches the restored volume and that
installed is true, maintenance is false, and needsDbUpgrade is false. Compare the
user list with the expected accounts from the selected backup. If startup fails,
review the test containers' logs before retrying.

The exercise used the test account nextcloud. Substitute the actual restored
Nextcloud user ID in both file checks. Run the file count as the web-service user.

~~~bash
RESTORE_USER='nextcloud'

(
  set -o pipefail
  docker exec -u www-data nc-restore-app sh -ec '
    user_files="/var/www/html/data/$1/files"
    test -f /var/www/html/data/.ncdata
    test -d "$user_files"
    find "$user_files" -type f -print0
  ' sh "$RESTORE_USER" | tr -cd '\000' | wc -c
)
printf 'User-file count exit code: %s\n' "$?"

sudo rsync -rcn --delete --itemize-changes \
  "$RESTORE/nextcloud_volume/data/$RESTORE_USER/files/" \
  "$WORK/data/$RESTORE_USER/files/"
printf 'Checksum comparison exit code: %s\n' "$?"
~~~

Compare the file count with the expected backup count after exit code 0. A
successful checksum comparison returns exit code 0 and prints no itemized differences. The -n flag
makes the rsync command a dry run, including the --delete comparison.

## 5. Shut down the test environment

Record the HBS version, import and checksum exit codes, SQL counts, and
application health. Save only sanitized evidence in Git. Keep SQL dumps,
Nextcloud configuration files, and secrets in protected storage.

~~~bash
docker stop nc-restore-app nc-restore-db
docker ps -a --filter name=nc-restore-
~~~

Confirm both containers report Exited (0). The restored files, test
database volume, and internal network remain available for review.
