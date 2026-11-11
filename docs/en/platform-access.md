# Platform login and access for AI and scripts

This guide covers the platform hierarchy changes dated 2026-10-11. Lab requires platform login by default. Core dynamics and standalone local Runtime execution require no platform account. Credentials never enter individual configuration, model packages or checkpoints.

## Initial setup and browser sessions

When no enabled superadministrator can log in, the local WebUI offers initial setup: a username and a password of at least 12 characters. Setup adds login credentials to the existing local account and retains ownership of projects, individuals and research records. It does not recreate data. Otherwise, use the existing account.

Lab requires login both on a workstation and on a server. The unauthenticated `authentication=local` mode is no longer available; `THREEMIND_AUTHENTICATION` must be `session`. Standalone local Runtime execution still requires no platform login.

Normal sessions last 12 hours; remembered sessions last 30 days. Closing or refreshing a page does not pause an individual. Logout revokes that session without stopping background tasks or logging out other browser/CLI sessions. Superadministrators can access all personal records; other users require the appropriate action, data scope and project membership.

## CLI login and protected profiles

Run these commands from the repository root with the actual Python environment:

```powershell
$env:PYTHONPATH = "$PWD\src"
.\.work\kernel-venv\Scripts\python.exe -m threemind_lab.cli auth login --username local --interactive --remember
.\.work\kernel-venv\Scripts\python.exe -m threemind_lab.cli auth status
.\.work\kernel-venv\Scripts\python.exe -m threemind_lab.cli records list
.\.work\kernel-venv\Scripts\python.exe -m threemind_lab.cli ops list
```

If initial setup changed the username, replace `--username local` with the actual username. A single user can log in once as superadministrator and reuse the profile; limited delegation is optional when AI or script access should be narrower, not mandatory for each experiment.

`--interactive` prompts only in an interactive terminal. AI and scripts are noninteractive by default: missing credentials produce an immediate error, not a password prompt. Login saves a reusable session across commands and processes. Closing an ordinary client does not log out. The client refreshes a session near expiration; `auth refresh` explicitly rotates it. An expired session requires login again.

The default profile is `default`; use `--auth-profile research` for another. Profiles are bound to the API origin and never sent to another service. Windows stores profiles under the current user's `%LOCALAPPDATA%\ThreeMind\auth`, encrypted with that user's DPAPI. POSIX uses a user-owned private directory and restrictive file permissions. Passwords are not saved. `--auth-dir` or `THREEMIND_AUTH_DIR` selects the protected directory; credentials are host control data, not experimental originals. Do not commit, export with experiments or disclose them to AI.

```powershell
.\.work\kernel-venv\Scripts\python.exe -m threemind_lab.cli auth logout --auth-profile default
```

Account logout requests server revocation and clears the local profile. Logging out a delegation removes only the local credential; its issuer must use `auth revoke` for server revocation. Ordinary client shutdown does not revoke persistent sessions.

## Limited delegation for AI

Conversation authorization describes what may be done; credentials establish who performs it. Neither substitutes for the other. Delegated AI acts as the original issuer with a distinct execution source and delegation identity, without inheriting superadministrator status.

Choose explicit resources, actions and expiration. This example permits reading, stimulation and recording in one project. Replace the project placeholder with its real UUID and remove actions that the task does not need:

```powershell
$delegation = @{
  name = 'AI research session'; source = 'ai'
  actions = @(
    @{ action = 'runs.read'; scope = 'member_projects' }
    @{ action = 'runs.stimulate'; scope = 'member_projects' }
    @{ action = 'research.read'; scope = 'member_projects' }
    @{ action = 'research.write'; scope = 'member_projects' }
  )
  resources = @(@{ kind = 'project'; id = '<actual project UUID>' })
  expires_at = [DateTimeOffset]::UtcNow.AddHours(8).ToString('o')
}
$delegation | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath .work\ai-delegation.json -Encoding utf8
.\.work\kernel-venv\Scripts\python.exe -m threemind_lab.cli auth delegate --json .work\ai-delegation.json --delegate-profile ai-research
```

The definition contains no secret. The command saves the one-time token directly into a separate protected profile without printing it; existing destination profiles cannot be overwritten. Delegations require at least one resource, expire within 30 days, cannot exceed the issuer's fresh permissions, and cannot administer accounts/roles or issue further delegations. Resources can be `project`, `run`, `experiment` or AI `service`; a child resource does not permit project-wide listings.

```powershell
$env:THREEMIND_AUTH_PROFILE = 'ai-research'
$env:THREEMIND_EXECUTION_SOURCE = 'ai'
.\.work\kernel-venv\Scripts\python.exe -m threemind_lab.cli records list --project '<actual project UUID>'
# Use the issuer's account profile to inspect and revoke:
.\.work\kernel-venv\Scripts\python.exe -m threemind_lab.cli auth delegations --auth-profile default
.\.work\kernel-venv\Scripts\python.exe -m threemind_lab.cli auth revoke --auth-profile default --id '<delegation UUID>'
```

Expiration, revocation, account disablement and narrower issuer permissions take effect. Delegations cannot refresh themselves. Missing permissions require a suitable delegation or issuer action, never an implicit local superadministrator. Reading, managing and using external AI services are separate actions; management permission does not authorize paid calls.

Automatic AI environments, interpretations and ecology observations save the original account and delegation with their configuration. Scheduling and sending check current authority again; an expired or revoked delegation never falls back to the account's full permissions. Enabling automatic calls requires service-use permission and the specific target operation. Renewal requires a new delegation and an explicit configuration save. Logging out of an ordinary session does not pause background work, while a revoked or expired delegation prevents its later authorized operations. Already sent requests with unknown outcomes remain uncertain and are never resent automatically.

## Noninteractive credentials, REST, MCP and Python

All clients use the following host environment variables without reading browser cookies:

| Variable | Purpose |
|---|---|
| `THREEMIND_API_URL` | API origin; default `http://127.0.0.1:8877` |
| `THREEMIND_AUTH_PROFILE` / `THREEMIND_AUTH_DIR` | Protected profile and directory |
| `THREEMIND_API_TOKEN` | Explicit host-supplied Bearer token, overriding profiles; never automatically persisted |
| `THREEMIND_API_USERNAME` / `THREEMIND_API_PASSWORD` | Compatible host credentials for issuing a reusable session; passwords never enter profiles |
| `THREEMIND_EXECUTION_SOURCE` | `human`, `ai` or `script`; metadata, not authority |

Remote API origins require HTTPS. Loopback HTTP is supported; workstation mode still accepts only loopback requests. MCP runs through `python -m threemind_lab.mcp_server` using stdio and the same profile, with `ai` as its default source. Ordinary experiments need no human login at each step. Explicitly sensitive operations retain their human confirmation workflows.

REST provides `POST /api/v2/auth/token`, session rotation through `POST /api/v2/auth/refresh`, and identity through `GET /api/v2/me`. `/api/v2/account/delegations` lists/issues delegations and its item endpoint revokes them. Cookie mutations require CSRF; Bearer requests do not require browser cookies. Credentials never enter protocols, reports, receipts or experimental records.

Python uses `OperationsClient.from_environment(source='script')` or `ResearchRecorder.from_environment(directory, project, source='script')`. AI can select `ai` and a delegated profile. The recorder persists registration, stages, originals, reports and finalization without invoking Core dynamics. A service outage preserves pending records; if original bytes cannot be saved reliably, the experimental host must stop further advancement.

After an ambiguous response, query the original request receipt before retrying; do not invent another identifier and repeat stimulation. The client never automatically logs in and replays a mutation after 401. Resuming a recording journal does not restore an individual; that requires its complete system checkpoint.

## Standalone Runtime boundary

Local standalone Python/Rust Runtime libraries and commands remain independent of platform login. Current command-line entry points do not expose a network management service. If a host exposes network interfaces, listening scope, authentication or a trusted proxy belong to deployment settings. Core contains no account/password/permission dynamics, and model originals contain no platform session.
