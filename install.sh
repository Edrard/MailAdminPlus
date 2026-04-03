#!/bin/bash
# iRedAdmin Custom Patch Installer
# Usage: bash install.sh /path/to/iRedAdmin

IREDADMIN_PATH="$1"

if [ -z "$IREDADMIN_PATH" ]; then
    echo "Usage: $0 /path/to/iRedAdmin"
    echo "Example: $0 /opt/www/iRedAdmin-2.6"
    exit 1
fi

if [ ! -d "$IREDADMIN_PATH" ]; then
    echo "Error: Directory $IREDADMIN_PATH does not exist."
    exit 1
fi

# Check version
VERSION_FILE="$IREDADMIN_PATH/libs/__init__.py"
if [ -f "$VERSION_FILE" ]; then
    VERSION=$(grep "__version__" "$VERSION_FILE" | cut -d'"' -f2)
    if [ "$VERSION" != "2.6" ]; then
        echo "Error: This patch is only for iRedAdmin 2.6. Found version: $VERSION"
        exit 1
    fi
    echo "Confirmed iRedAdmin version 2.6."
else
    echo "Warning: Could not find version file $VERSION_FILE. Proceeding with caution..."
fi

# Define backup dir
BACKUP_DIR="${IREDADMIN_PATH}_backup_$(date +%Y%m%d_%H%M%S)"
echo "Creating backup in $BACKUP_DIR..."
mkdir -p "$BACKUP_DIR"

# List of files to backup and replace
# format: local_file:remote_path
FILES_TO_REPLACE=(
    "controllers_sql_alias.py:controllers/sql/alias.py"
    "libs_sqllib_alias.py:libs/sqllib/alias.py"
    "alias_create.html:templates/default/sql/alias/create.html"
    "alias_list.html:templates/default/sql/alias/list.html"
    "alias_profile.html:templates/default/sql/alias/profile.html"
    "alias_autocomplete.js:static/js/alias_autocomplete.js"
    "user_list.html:templates/default/sql/user/list.html"
    "user_profile.html:templates/default/sql/user/profile.html"
)

# 1. Copy new files and backup originals
for entry in "${FILES_TO_REPLACE[@]}"; do
    src="${entry%%:*}"
    dest="${entry#*:}"
    
    full_dest="$IREDADMIN_PATH/$dest"
    
    # Backup
    if [ -f "$full_dest" ]; then
        dest_dir=$(dirname "$dest")
        mkdir -p "$BACKUP_DIR/$dest_dir"
        cp "$full_dest" "$BACKUP_DIR/$dest"
    fi
    
    # Ensure dest dir exists
    dest_path_dir=$(dirname "$full_dest")
    mkdir -p "$dest_path_dir"
    
    # Copy
    cp "files/$src" "$full_dest"
    echo "Installed $dest"
done

# 2. Patch urls.py
URLS_PY="$IREDADMIN_PATH/controllers/sql/urls.py"
if grep -q "from controllers.sql import alias" "$URLS_PY"; then
    echo "urls.py already patched."
else
    echo "Patching urls.py..."
    cp "$URLS_PY" "$BACKUP_DIR/controllers/sql/urls.py"
    
    # Add imports
    sed -i "/from controllers.sql import user/a from controllers.sql import alias" "$URLS_PY"
    
    # Add routes
    ROUTES_BLOCK="
    '/aliases/(.*)', 'controllers.sql.alias.List',
    '/aliases/(.*)/page/([0-9]+)', 'controllers.sql.alias.List',
    '/aliases/(.*)/disabled', 'controllers.sql.alias.ListDisabled',
    '/aliases/(.*)/disabled/page/([0-9]+)', 'controllers.sql.alias.ListDisabled',
    '/create/alias/(.*)', 'controllers.sql.alias.Create',
    '/profile/alias/(.*)/(.*)', 'controllers.sql.alias.Profile',
    '/profile/user/forwarding/(.*)', 'controllers.sql.user.Profile',
    '/api/search_destinations', 'controllers.sql.alias.SearchDestinations',
"
    # Insert after existing user routes
    sed -i "/'\/profile\/user\/(.*)\/(.*)', 'controllers.sql.user.Profile',/a $ROUTES_BLOCK" "$URLS_PY"
fi

# 3. Patch user.py (backend forwarding logic)
USER_PY="$IREDADMIN_PATH/libs/sqllib/user.py"
echo "Patching user.py..."
cp "$USER_PY" "$BACKUP_DIR/libs/sqllib/user.py"

# We use python to safely inject the code block to avoid escaping issues with sed
python3 - <<EOF
import os

path = "$USER_PY"
with open(path, 'r') as f:
    content = f.read()

# Forwarding profile fetch logic
profile_fwd_code = """
        # --- [START] Forwarding Logic ---
        qr_fwd = conn.select('forwardings',
                             vars={'mail': mail},
                             what='forwarding, active',
                             where='address=\$mail',
                             order='forwarding ASC')
        fwd_records = list(qr_fwd)
        
        # Split into self-copy and external
        user_profile['enable_forwarding'] = False
        user_profile['save_a_copy'] = False
        user_profile['forwardings'] = []
        
        for f in fwd_records:
            if f['forwarding'] == mail:
                if f['active'] == 1:
                    user_profile['save_a_copy'] = True
            else:
                user_profile['forwardings'].append(f['forwarding'])
                if f['active'] == 1:
                    user_profile['enable_forwarding'] = True
        # --- [END] Forwarding Logic ---
"""

if '# --- [START] Forwarding Logic ---' not in content:
    if 'return (True, user_profile)' in content:
        content = content.replace('return (True, user_profile)', profile_fwd_code + '\n        return (True, user_profile)')

# Forwarding update logic
update_fwd_code = """
        elif profile_type == 'forwarding':
            enable_forwarding = (form.get('enable_forwarding') == 'yes')
            save_copy = (form.get('save_copy') == 'yes')
            addresses_str = form.get('forward_addresses', '').strip()
            
            # Parse addresses
            raw_addresses = [x.strip().lower() for x in addresses_str.replace('\n', ',').replace(' ', ',').split(',') if x.strip()]
            from libs import iredutils
            valid_addresses = [x for x in raw_addresses if iredutils.is_email(x)]
            
            try:
                # 1. Handle Self-Forwarding (Save a copy)
                existing_self = conn.select('forwardings', vars={'m': mail}, where='address=\$m AND forwarding=\$m')
                if existing_self:
                    conn.update('forwardings', vars={'m': mail}, where='address=\$m AND forwarding=\$m', active=(1 if save_copy else 0))
                elif save_copy:
                    conn.insert('forwardings', address=mail, forwarding=mail, domain=domain, dest_domain=domain, is_forwarding=1, active=1)
                
                # 2. Handle External Forwarding
                # Deactivate all existing external forwardings for this user
                conn.update('forwardings', vars={'m': mail}, where='address=\$m AND forwarding!=\$m', active=0)
                
                if enable_forwarding:
                    for addr in valid_addresses:
                        dest_domain = addr.split('@', 1)[-1]
                        # Check if exists
                        existing = conn.select('forwardings', vars={'m': mail, 'f': addr}, where='address=\$m AND forwarding=\$f')
                        if existing:
                            conn.update('forwardings', vars={'m': mail, 'f': addr}, where='address=\$m AND forwarding=\$f', active=1)
                        else:
                            conn.insert('forwardings', address=mail, forwarding=addr, domain=domain, dest_domain=dest_domain, is_forwarding=1, active=1)
                
                log_activity(msg="Update forwarding for %s" % mail, domain=domain, event='update')
                return (True, {})
            except Exception as e:
                return (False, repr(e))
"""

if "elif profile_type == 'forwarding':" not in content:
    content = content.replace("elif profile_type == 'password':", update_fwd_code + "\n        " + "elif profile_type == 'password':")

with open(path, 'w') as f:
    f.write(content)
EOF

# 4. Add settings
SETTINGS_DIR="/opt/iredapd"
if [ -f "$SETTINGS_DIR/settings.py" ]; then
    echo "Updating settings.py in $SETTINGS_DIR..."
    if ! grep -q "round_cube_inbox" "$SETTINGS_DIR/settings.py"; then
        echo -e "\n# Roundcube SSO Integration\nround_cube_inbox = False\nround_cube_url = 'https://mail.example.com/roundcube/'\nround_cube_token = 'SECRET_TOKEN_HERE'" >> "$SETTINGS_DIR/settings.py"
    fi
fi

echo "Patch applied successfully. Please restart iredadmin Service."
