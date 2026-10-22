# AI Versioning

## Versioned Components
- system prompts
- task prompts
- model
- extraction schema
- embedding model
- chunking configuration
- retrieval configuration
- evaluation dataset

## AI Run Metadata

```text
prompt_version
model_version
schema_version
embedding_version
retrieval_version
evaluation_version
```

## Compatibility
A schema/model change must define:
- compatibility
- migration strategy
- evaluation result
- rollback strategy

## Reproducibility
A production answer should be traceable to the exact AI configuration used to generate it.
