# iRedAdmin Custom Patch

Extends iRedAdmin (open-source, SQL backend) with:

- **Mail Aliases** — create, list, edit, delete mail aliases with autocomplete
- **Roundcube SSO Inbox** — one-click webmail access from the user list
- **Mail Forwarding** — per-user forwarding tab with Enable/Save a copy controls

## Installation

```bash
cd /opt/iredadmin-patch
bash install.sh /opt/www/iRedAdmin-2.6
systemctl restart iredadmin
```

The script automatically:
1. Backs up all original files before overwriting
2. Copies new controllers, templates, and JS
3. Patches `libs/sqllib/user.py` (forwarding logic) via sed/python
4. Patches `layout.html` (Alias menu item) via sed
5. Adds default settings to `/opt/iredapd/settings.py`

## Settings

In `/opt/iredapd/settings.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `round_cube_inbox` | `False` | Enable "Inbox" button on user list |
| `round_cube_token` | `""` | Shared secret for SSO token |
| `round_cube_url` | `""` | Roundcube base URL |

## Files

| File | Type | Description |
|------|------|-------------|
| `controllers_sql_alias.py` | NEW | Alias web controllers |
| `libs_sqllib_alias.py` | NEW | Alias database operations |
| `alias_create.html` | NEW | Create alias form |
| `alias_list.html` | NEW | Alias listing page |
| `alias_profile.html` | NEW | Edit alias profile |
| `alias_autocomplete.js` | NEW | Autocomplete for destinations |
| `user_list.html` | MODIFIED | Adds Aliases tab + Inbox button |
| `user_profile.html` | MODIFIED | Adds Forwarding tab |
