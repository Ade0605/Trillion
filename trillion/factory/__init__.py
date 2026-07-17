"""
Agent Factory — a meta-agent that mints other sub-agents on demand.

Ask Trillion to "spawn a sub-agent that does X": the Factory researches the role,
drafts a system prompt, picks a tool allowlist, stages a proposed manifest for
your approval, and — on approval — registers a `dispatch_to_<slug>` tool live,
with no restart. Spawned agents are pure configuration (one ConfigDrivenAgent
runtime), never bespoke classes. See docs/agent-factory.md.
"""
