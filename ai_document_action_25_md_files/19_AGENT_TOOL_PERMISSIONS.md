# Agent Tool Permissions

## Principle
Tool access is capability-based and least-privilege.

| Agent | Read DB | Write DB | R2 | LLM | Notify | Delete |
|---|---:|---:|---:|---:|---:|---:|
| Repository | No | No | No | No | No | No |
| Extraction | Scoped | Scoped | Read | Yes | No | No |
| RAG | Scoped | Chat | Read | Yes | No | No |
| Action | Scoped | Actions | No | Optional | Yes | No |
| Deletion | Scoped | Delete | Delete | No | No | Yes |
| QA | Test only | Test only | Test | Yes | No | No |

## Enforcement
Agent → Tool Gateway → Authorization → Tool.

Tool calls must carry:
- user ID
- request ID
- document scope
- agent identity
- audit context

## Forbidden
No agent receives production database superuser credentials or unrestricted storage credentials.
