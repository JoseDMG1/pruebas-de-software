#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
python3 dev/moodle/prepare.py
docker compose -f compose.moodle.yaml up --build -d
docker compose -f compose.moodle.yaml exec -T moodle sh -lc \
  'mkdir -p /var/moodledata /var/moodletestdata && chown www-data:www-data /var/moodledata /var/moodletestdata'
if ! docker compose -f compose.moodle.yaml exec -T -u www-data moodle php -r \
  'define("CLI_SCRIPT", true); require("config.php"); exit($DB->get_manager()->table_exists("config") && $DB->get_field("config", "value", ["name" => "version"]) ? 0 : 1);'; then
  docker compose -f compose.moodle.yaml exec -T -u www-data moodle sh -lc \
    'php admin/cli/install_database.php --agree-license --adminuser=admin_udv --adminpass="$MOODLE_DEMO_PASSWORD" --adminemail=admin@udv.edu.pe --fullname="Universidad del Valle" --shortname="UDV" --lang=en'
fi
docker compose -f compose.moodle.yaml exec -T -u www-data moodle php admin/cli/upgrade.php --non-interactive --allow-unstable
docker compose -f compose.moodle.yaml exec -T -u www-data moodle php /opt/moodle-dev/seed.php > .local/moodle-fixtures.json
docker compose -f compose.moodle.yaml exec -T -u www-data moodle php public/local/acadassistant/cli/export_course_catalog.php > .local/course-catalog.json
(cd rag-service && docker compose up -d db && .venv/bin/rag prepare-demo && docker compose up --build -d api)
rag-service/.venv/bin/python dev/moodle/documents.py
rag-service/.venv/bin/python dev/moodle/guides.py
echo 'Moodle: http://127.0.0.1:8088/local/acadassistant/index.php'
echo 'Credentials: .local/sprint2-credentials.md'
