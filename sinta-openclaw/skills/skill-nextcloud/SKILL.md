---
name: skill-nextcloud
description: Interact with Nextcloud file storage. Upload, download, list, and share files via WebDAV and the Nextcloud OCS API.
---

# Nextcloud Skill

## Endpoint

```
URL:      https://cloud.dev2null.de
WebDAV:   https://cloud.dev2null.de/remote.php/dav/files/{username}/
OCS API:  https://cloud.dev2null.de/ocs/v2.php/
Version:  31.0.4
```

## Authentication

Use HTTP Basic Auth with Nextcloud credentials. Prefer **App Passwords** over the main account password:
1. Login to Nextcloud → Profile → Settings → Security → App Passwords → Create new

```bash
NC_USER="admin"
NC_PASS="app-password-here"
NC_URL="https://cloud.dev2null.de"
```

## Common Operations

### List files in a folder (WebDAV PROPFIND)
```bash
curl -s -u "$NC_USER:$NC_PASS" \
  -X PROPFIND \
  "$NC_URL/remote.php/dav/files/$NC_USER/Documents/" \
  -H "Depth: 1"
```

### Upload a file
```bash
curl -s -u "$NC_USER:$NC_PASS" \
  -T /local/path/file.txt \
  "$NC_URL/remote.php/dav/files/$NC_USER/Documents/file.txt"
```

### Download a file
```bash
curl -s -u "$NC_USER:$NC_PASS" \
  "$NC_URL/remote.php/dav/files/$NC_USER/Documents/file.txt" \
  -o /local/path/file.txt
```

### Create a folder
```bash
curl -s -u "$NC_USER:$NC_PASS" \
  -X MKCOL \
  "$NC_URL/remote.php/dav/files/$NC_USER/NewFolder/"
```

### Share a file (OCS API)
```bash
curl -s -u "$NC_USER:$NC_PASS" \
  -X POST \
  -H "OCS-APIRequest: true" \
  "$NC_URL/ocs/v2.php/apps/files_sharing/api/v1/shares?format=json" \
  -d "path=/Documents/file.txt&shareType=3"
# shareType 3 = public link
```

### User info (OCS)
```bash
curl -s -u "$NC_USER:$NC_PASS" \
  -H "OCS-APIRequest: true" \
  "$NC_URL/ocs/v1.php/cloud/users/$NC_USER?format=json"
```

## Notes

- Nextcloud status: `GET /status.php` returns version info (no auth needed)
- WebDAV paths are case-sensitive
- PROPFIND responses are XML — parse with `xmllint` or Python `xml.etree`
- For bulk operations use `rclone` with Nextcloud WebDAV remote
