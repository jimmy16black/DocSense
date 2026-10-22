# Agentic Workflow Architecture

## Principle
Use agents for reasoning-heavy work; use deterministic services for predictable operations.

## Deterministic Pipeline
Validation, authentication, authorization, file handling, schema validation, citation verification, quota enforcement and persistence should not depend on autonomous agent decisions.

## Agentic Pipeline
Agents may perform:
- classification reasoning
- complex extraction interpretation
- question routing
- comparison
- action recommendation
- controlled tool selection

## Workflow

```text
Request
 ↓
Policy/Authorization
 ↓
Router
 ├─ deterministic path
 └─ agentic path
       ↓
   allowed tools
       ↓
   validated result
       ↓
   policy checks
       ↓
   response/action
```

## No Free-Form Autonomy
An agent cannot arbitrarily call tools, access unrelated users, modify schemas, deploy production or delete data.

## Consequential Actions
Recommendation → explicit user confirmation → deterministic action execution → audit event.
