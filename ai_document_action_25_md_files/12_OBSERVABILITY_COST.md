# Observability & Cost

## AI Request Fields
- request_id
- user_id
- document_id
- agent
- provider
- model
- prompt_version
- input_tokens
- output_tokens
- latency
- success
- fallback_used
- estimated_cost

## Metrics
- API errors
- P95 latency
- queue lag
- processing failures
- AI failures
- cost/document
- cost/user
- storage
- notification failures

## Alerts
Initial examples:
- API 5xx > 5% for 5 minutes
- Q&A P95 > 8 seconds
- storage > 80%
- unexpected AI spend
- repeated uptime failures

Thresholds must be tuned using production baselines.
