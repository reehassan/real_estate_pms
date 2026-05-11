#!/bin/bash
# =============================================================================
# setup_crons.sh — Royal Land PMS
# Run once on the VPS to:
#   1. Install and configure rclone (Google Drive)
#   2. Write the backup script (pg_dump → gzip → Google Drive)
#   3. Wire up cron jobs (mark_overdue + backup)
#
# Usage: bash setup_crons.sh
# =============================================================================

set -e

# ── Config ────────────────────────────────────────────────────────────────────
APP_CONTAINER="docker-app-1"
DB_CONTAINER="docker-db-1"
BACKUP_DIR="/opt/royal-land/backups"
BACKUP_SCRIPT="/opt/royal-land/backup_db.sh"
LOG_DIR="/opt/royal-land/logs"
GDRIVE_REMOTE="gdrive"                  # rclone remote name
GDRIVE_FOLDER="RoyalLandPMS/backups"   # folder inside your Google Drive

# ── Colours ───────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo ""
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}   Royal Land PMS — Cron & Backup Setup    ${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# ── Step 1: Install rclone ────────────────────────────────────────────────────
echo -e "${YELLOW}==> [1/5] Installing rclone...${NC}"

if command -v rclone &> /dev/null; then
    echo -e "${GREEN}    rclone already installed: $(rclone --version | head -1)${NC}"
else
    curl https://rclone.org/install.sh | sudo bash
    echo -e "${GREEN}    rclone installed.${NC}"
fi

# ── Step 2: Configure rclone Google Drive ─────────────────────────────────────
echo ""
echo -e "${YELLOW}==> [2/5] Configuring Google Drive remote...${NC}"

if rclone listremotes | grep -q "^${GDRIVE_REMOTE}:"; then
    echo -e "${GREEN}    Remote '${GDRIVE_REMOTE}' already configured — skipping.${NC}"
else
    echo ""
    echo -e "${BLUE}────────────────────────────────────────────────────────────${NC}"
    echo -e "${BLUE}  rclone needs to connect to your Google Drive.             ${NC}"
    echo -e "${BLUE}  Follow the steps below carefully:                         ${NC}"
    echo -e "${BLUE}────────────────────────────────────────────────────────────${NC}"
    echo ""
    echo -e "  1.  Type: ${GREEN}n${NC}  (new remote)"
    echo -e "  2.  Name: ${GREEN}gdrive${NC}"
    echo -e "  3.  Storage type: choose ${GREEN}Google Drive${NC} (type the number)"
    echo -e "  4.  Client ID: ${GREEN}leave blank, press Enter${NC}"
    echo -e "  5.  Client Secret: ${GREEN}leave blank, press Enter${NC}"
    echo -e "  6.  Scope: choose ${GREEN}1${NC} (full access)"
    echo -e "  7.  Root folder ID: ${GREEN}leave blank, press Enter${NC}"
    echo -e "  8.  Service account: ${GREEN}leave blank, press Enter${NC}"
    echo -e "  9.  Edit advanced config: ${GREEN}n${NC}"
    echo -e "  10. Use auto config: ${GREEN}n${NC}  (we are on a remote server)"
    echo ""
    echo -e "  ${YELLOW}A long URL will appear.${NC}"
    echo -e "  ${YELLOW}Open it on your LOCAL machine, log into Google,${NC}"
    echo -e "  ${YELLOW}allow access, then paste the verification code back here.${NC}"
    echo ""
    echo -e "  11. Configure as Shared Drive: ${GREEN}n${NC}"
    echo -e "  12. Confirm the remote looks correct: ${GREEN}y${NC}"
    echo -e "  13. Quit rclone config: ${GREEN}q${NC}"
    echo ""
    echo -e "${BLUE}────────────────────────────────────────────────────────────${NC}"
    echo ""
    read -p "Press ENTER when ready to start rclone config..."
    echo ""

    rclone config

    # Verify it worked
    if rclone listremotes | grep -q "^${GDRIVE_REMOTE}:"; then
        echo ""
        echo -e "${GREEN}    Google Drive remote configured successfully.${NC}"
    else
        echo ""
        echo -e "${RED}    Remote '${GDRIVE_REMOTE}' not found after config.${NC}"
        echo -e "${RED}    Run 'rclone config' manually and name the remote 'gdrive'.${NC}"
        exit 1
    fi
fi

# ── Step 3: Create directories + test Drive connection ────────────────────────
echo ""
echo -e "${YELLOW}==> [3/5] Creating directories...${NC}"
mkdir -p "$BACKUP_DIR"
mkdir -p "$LOG_DIR"
echo -e "${GREEN}    $BACKUP_DIR${NC}"
echo -e "${GREEN}    $LOG_DIR${NC}"

echo -e "${YELLOW}    Testing Google Drive connection...${NC}"
if rclone mkdir "${GDRIVE_REMOTE}:${GDRIVE_FOLDER}" 2>/dev/null; then
    echo -e "${GREEN}    Google Drive folder ready: ${GDRIVE_FOLDER}${NC}"
else
    echo -e "${RED}    Could not connect to Google Drive. Check rclone config.${NC}"
    exit 1
fi

# ── Step 4: Write backup script ───────────────────────────────────────────────
echo ""
echo -e "${YELLOW}==> [4/5] Writing backup script to ${BACKUP_SCRIPT}...${NC}"

cat > "$BACKUP_SCRIPT" << 'BACKUP_EOF'
#!/bin/bash
# =============================================================================
# backup_db.sh — Royal Land PMS
# pg_dump → gzip → upload to Google Drive → delete local copy
# Keeps last 30 backups in Google Drive, deletes older ones automatically.
# Runs daily at 2am via cron.
# =============================================================================

set -e

BACKUP_DIR="/opt/royal-land/backups"
DB_CONTAINER="docker-db-1"
GDRIVE_REMOTE="gdrive"
GDRIVE_FOLDER="RoyalLandPMS/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
FILENAME="royal_land_${TIMESTAMP}.sql.gz"
LOCAL_PATH="${BACKUP_DIR}/${FILENAME}"

# Load DB credentials from .env.prod
source <(grep -E '^DB_' /opt/royal-land/docker/.env.prod)

echo "[backup] =============================="
echo "[backup] Starting at ${TIMESTAMP}"

# 1. Dump and compress
echo "[backup] Dumping database..."
docker exec "${DB_CONTAINER}" pg_dump -U "${DB_USER}" "${DB_NAME}" | gzip > "${LOCAL_PATH}"
echo "[backup] Saved locally: ${LOCAL_PATH}"

# 2. Upload to Google Drive
echo "[backup] Uploading to Google Drive..."
rclone copy "${LOCAL_PATH}" "${GDRIVE_REMOTE}:${GDRIVE_FOLDER}"
echo "[backup] Uploaded: ${GDRIVE_FOLDER}/${FILENAME}"

# 3. Delete local file — it is safe in Drive now
rm -f "${LOCAL_PATH}"
echo "[backup] Local copy deleted."

# 4. Keep only last 30 backups in Drive — delete older ones
echo "[backup] Pruning old backups (keeping last 30)..."
rclone ls "${GDRIVE_REMOTE}:${GDRIVE_FOLDER}" \
    | sort \
    | head -n -30 \
    | awk '{print $2}' \
    | while read -r old_file; do
        rclone deletefile "${GDRIVE_REMOTE}:${GDRIVE_FOLDER}/${old_file}"
        echo "[backup] Deleted old backup: ${old_file}"
      done

echo "[backup] Done."
echo "[backup] =============================="
BACKUP_EOF

chmod +x "$BACKUP_SCRIPT"
echo -e "${GREEN}    Written: $BACKUP_SCRIPT${NC}"

# ── Step 5: Wire cron jobs ────────────────────────────────────────────────────
echo ""
echo -e "${YELLOW}==> [5/5] Adding cron jobs...${NC}"

EXISTING_CRON=$(crontab -l 2>/dev/null || true)
NEW_CRON="$EXISTING_CRON"

MARK_OVERDUE_JOB="0 1 * * * docker exec ${APP_CONTAINER} python manage.py mark_overdue >> ${LOG_DIR}/mark_overdue.log 2>&1"
BACKUP_JOB="0 2 * * * bash ${BACKUP_SCRIPT} >> ${LOG_DIR}/backup.log 2>&1"

if echo "$EXISTING_CRON" | grep -q "mark_overdue"; then
    echo -e "${GREEN}    mark_overdue cron already exists — skipping${NC}"
else
    NEW_CRON="${NEW_CRON}
${MARK_OVERDUE_JOB}"
    echo -e "${GREEN}    Added: mark_overdue daily at 1am${NC}"
fi

if echo "$EXISTING_CRON" | grep -q "backup"; then
    echo -e "${GREEN}    backup cron already exists — skipping${NC}"
else
    NEW_CRON="${NEW_CRON}
${BACKUP_JOB}"
    echo -e "${GREEN}    Added: pg_dump + Google Drive upload daily at 2am${NC}"
fi

echo "$NEW_CRON" | crontab -

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}============================================${NC}"
echo -e "${GREEN}   Setup complete!                         ${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
echo "Active crontab:"
crontab -l
echo ""
echo -e "${YELLOW}Test manually:${NC}"
echo "  mark_overdue : docker exec ${APP_CONTAINER} python manage.py mark_overdue"
echo "  backup       : bash ${BACKUP_SCRIPT}"
echo ""
echo -e "${YELLOW}Logs:${NC}"
echo "  mark_overdue : ${LOG_DIR}/mark_overdue.log"
echo "  backup       : ${LOG_DIR}/backup.log"
echo ""
echo -e "${YELLOW}Backups land in Google Drive at:${NC}"
echo "  ${GDRIVE_FOLDER}/"