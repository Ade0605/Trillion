"""
Security hardening for Trillion.

Modules:
- log_redact:    mask secret-shaped strings before they reach the audit log.
- injection_gate: wrap untrusted external text so the LLM treats it as data.
- kill_switch:   a single env-var flag that halts all tool calls mid-incident.
- http_guard:    bearer-token check + per-IP auth rate-limit for the web server.

Threats addressed are named in each module. See docs/incident-runbook.md for
what to do when something is already on fire.
"""
