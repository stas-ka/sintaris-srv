---
name: skill-espocrm
description: Interact with EspoCRM — the CRM system at crm.dev2null.de. List, create, update, and search CRM records (Contacts, Accounts, Leads, Tasks, etc.).
---

# EspoCRM Skill

## Endpoint

```
URL: https://crm.dev2null.de
API base: https://crm.dev2null.de/api/v1/
Admin: admin
```

## Authentication

EspoCRM uses a custom auth header (not standard Basic Auth):

```bash
# Build auth header: base64(username:password)
ESPO_AUTH=$(echo -n "admin:PASSWORD" | base64 -w 0)
curl -H "Espo-Authorization: $ESPO_AUTH" https://crm.dev2null.de/api/v1/Contact
```

Alternatively use API key (if configured in EspoCRM Admin → API Users):
```bash
curl -H "X-Api-Key: your-api-key" https://crm.dev2null.de/api/v1/Contact
```

## Common Operations

### List records
```bash
GET /api/v1/{EntityType}?maxSize=20&offset=0
# EntityTypes: Contact, Account, Lead, Opportunity, Task, Call, Meeting, Case
```

### Get single record
```bash
GET /api/v1/{EntityType}/{id}
```

### Search/filter
```bash
GET /api/v1/Contact?searchParams={"where":[{"type":"contains","attribute":"name","value":"Stas"}]}
# URL-encode searchParams in real requests
```

### Create record
```bash
POST /api/v1/Contact
Content-Type: application/json
Body: {"firstName": "Stas", "lastName": "Test", "emailAddress": "test@example.com"}
```

### Update record
```bash
PUT /api/v1/Contact/{id}
Body: {"phoneNumber": "+49123456789"}
```

### Delete record
```bash
DELETE /api/v1/Contact/{id}
```

## Entity Types Reference

Common entity types:
- `Contact` — Individual people
- `Account` — Companies/organizations
- `Lead` — Unqualified prospects
- `Opportunity` — Sales deals
- `Task` — To-do items
- `Call` / `Meeting` — Scheduled activities
- `Case` — Support tickets
- `Document` — Attached documents

## Notes

- EspoCRM runs in Docker on VPS: container proxied at `localhost:8888`
- API returns JSON; all lists have `total` and `list` keys
- Filter format: `where` array with `type`, `attribute`, `value`
- Use `select` param to limit returned fields: `?select=id,name,emailAddress`
