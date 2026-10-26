import json
import re
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("ai_gateway")
settings = get_settings()

# Comprehensive PII patterns for Indian financial & identity tokens (ISSUE-009)
PII_PATTERNS: list[tuple[str, str, str]] = [
    (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b", "[EMAIL_REDACTED]", "EMAIL"),
    (r"(?:\+91[\-\s]?|\b)[6-9]\d{9}\b", "[PHONE_REDACTED]", "PHONE"),
    (r"\b[2-9]\d{3}[\s\-]\d{4}[\s\-]\d{4}\b", "[AADHAAR_REDACTED]", "AADHAAR"),
    (r"\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b", "[PAN_REDACTED]", "PAN"),
    (r"\b\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1}\b", "[GSTIN_REDACTED]", "GSTIN"),
    (r"\b[A-Za-z][1-9]\d{6}\b", "[PASSPORT_REDACTED]", "PASSPORT"),
    (
        r"\b[A-Z]{2}[-\s]?\d{2}[-\s]?(?:19|20)\d{2}\d{7}\b",
        "[DRIVING_LICENSE_REDACTED]",
        "DRIVING_LICENSE",
    ),
    (r"\b[A-Z]{4}0[A-Z0-9]{6}\b", "[IFSC_REDACTED]", "IFSC"),
    (r"\b[a-zA-Z0-9.\-_]{2,64}@[a-zA-Z]{2,32}\b", "[UPI_REDACTED]", "UPI_VPA"),
    (
        r"(?i)\b(?:dob|date\s+of\s+birth|birth\s+date)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b",
        "[DOB_REDACTED]",
        "DOB",
    ),
    (
        r"\b[A-Z]{2}[-\s]?\d{1,2}[-\s]?[A-Z]{1,3}[-\s]?\d{4}\b",
        "[VEHICLE_NO_REDACTED]",
        "VEHICLE_REGISTRATION",
    ),
    (
        r"(?i)\b(?:a/c|acct|account(?:\s*no)?[:\s]*)(\d{9,18})\b",
        "[ACCOUNT_NUMBER_REDACTED]",
        "BANK_ACCOUNT",
    ),
]


def redact_pii_with_details(text: str) -> tuple[str, dict[str, int]]:
    """Redacts PII tokens from text and returns the redacted string along with
    a counts dictionary of masked entities (ISSUE-009)."""
    counts: dict[str, int] = {}
    redacted = text

    for pattern, replacement, entity_name in PII_PATTERNS:
        matches = len(re.findall(pattern, redacted))
        if matches > 0:
            counts[entity_name] = counts.get(entity_name, 0) + matches
            redacted = re.sub(pattern, replacement, redacted)

    if counts:
        logger.info("PII redaction performed", total_masked=sum(counts.values()), entities=counts)

    return redacted, counts


def redact_pii(text: str) -> str:
    redacted, _ = redact_pii_with_details(text)
    return redacted


class AIGatewayService:
    def __init__(self):
        self.portkey_api_key = settings.PORTKEY_API_KEY
        self.gemini_api_key = settings.GEMINI_API_KEY
        self.openai_api_key = settings.OPENAI_API_KEY
        self.portkey_client = None

        if self.portkey_api_key:
            try:
                from portkey_ai import Portkey

                self.portkey_client = Portkey(
                    api_key=self.portkey_api_key,
                    virtual_key=settings.PORTKEY_VIRTUAL_KEY or None,
                )
            except Exception as e:
                logger.warning(
                    "Failed to initialize Portkey client, will use mock or direct provider",
                    error=str(e),
                )

    async def generate_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        model: str | None = None,
    ) -> str:
        safe_user_prompt = redact_pii(user_prompt)
        target_model = model or settings.DEFAULT_PRIMARY_MODEL

        # If Portkey client is initialized
        if self.portkey_client:
            try:
                response = self.portkey_client.chat.completions.create(
                    model=target_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": safe_user_prompt},
                    ],
                    temperature=temperature,
                )
                return response.choices[0].message.content or ""
            except Exception as e:
                logger.warning(
                    "Primary AI call via Portkey failed, attempting fallback model",
                    error=str(e),
                    primary_model=target_model,
                )
                try:
                    fallback_response = self.portkey_client.chat.completions.create(
                        model=settings.DEFAULT_FALLBACK_MODEL,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": safe_user_prompt},
                        ],
                        temperature=temperature,
                    )
                    return fallback_response.choices[0].message.content or ""
                except Exception as fallback_err:
                    logger.error(
                        "Both primary and fallback AI calls failed", error=str(fallback_err)
                    )
                    raise

        # Direct OpenAI, Google Gemini, or OpenAI-compatible local model (Ollama, LM Studio, vLLM, LocalAI)
        if self.openai_api_key or self.gemini_api_key or settings.OPENAI_BASE_URL:
            try:
                from openai import AsyncOpenAI

                if self.gemini_api_key and not self.openai_api_key:
                    api_key = self.gemini_api_key
                    base_url = settings.OPENAI_BASE_URL or "https://generativelanguage.googleapis.com/v1beta/openai/"
                else:
                    api_key = self.openai_api_key or "local-model"
                    base_url = settings.OPENAI_BASE_URL or "https://api.openai.com/v1"

                client = AsyncOpenAI(
                    api_key=api_key,
                    base_url=base_url,
                )
                response = await client.chat.completions.create(
                    model=target_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": safe_user_prompt},
                    ],
                    temperature=temperature,
                )
                return response.choices[0].message.content or ""
            except Exception as e:
                logger.warning(
                    "Primary AI call via OpenAI/Gemini/local endpoint failed, attempting fallback model",
                    error=str(e),
                    primary_model=target_model,
                )
                if (
                    settings.DEFAULT_FALLBACK_MODEL
                    and settings.DEFAULT_FALLBACK_MODEL != target_model
                ):
                    try:
                        fallback_response = await client.chat.completions.create(
                            model=settings.DEFAULT_FALLBACK_MODEL,
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": safe_user_prompt},
                            ],
                            temperature=temperature,
                        )
                        return fallback_response.choices[0].message.content or ""
                    except Exception as fallback_err:
                        logger.error(
                            "Both primary and fallback AI calls failed",
                            error=str(fallback_err),
                        )
                        raise
                raise

        # Fallback deterministic extractor for development / offline tests
        logger.info("Using mock/offline AI completion response")
        return self._generate_mock_completion(user_prompt)

    def _generate_mock_completion(self, user_prompt: str) -> str:
        """Deterministic mock response for local testing and CI"""
        if user_prompt.startswith("Question:"):
            # Check if there is retrieved context in the prompt
            context_section = user_prompt.split("Context:\n", 1)[-1] if "Context:\n" in user_prompt else ""
            quote = "Document terms and specifications as outlined."
            if "Monthly Base Rent" in context_section:
                answer = "The monthly base rent is $12,500.00 USD, payable on the first of each month, with a security deposit of $25,000.00 USD."
                quote = "Monthly Base Rent: Tenant covenants and agrees to pay Landlord base rent in the amount of $12,500.00 USD"
                heading = "SECTION 2: RENT AND SECURITY DEPOSIT"
                page = 1
            elif "Early Termination" in context_section:
                answer = "Early termination is permitted after 24 months with 90 days written notice and an early termination fee equal to two months rent ($25,000.00)."
                quote = "Tenant may terminate this Lease after twenty-four (24) months by providing at least ninety (90) days written notice"
                heading = "SECTION 3: MAINTENANCE, UTILITIES & TERMINATION"
                page = 2
            elif "100 Innovation Way" in context_section:
                answer = "The property is located at Suite 400, 100 Innovation Way, San Jose, CA 95134."
                quote = "The property located at Suite 400, 100 Innovation Way, San Jose, CA 95134"
                heading = "SECTION 1: PREMISES & TERM"
                page = 1
            else:
                answer = "Based on the document context, the specified terms are covered in the retrieved sections."
                heading = "General Terms"
                page = 1

            return json.dumps(
                {
                    "answer": answer,
                    "confidence": "HIGH",
                    "suggestedFollowUps": [
                        "What are the renewal terms?",
                        "What insurance coverage is required?",
                    ],
                    "citations": [
                        {
                            "pageNumber": page,
                            "sectionHeading": heading,
                            "exactQuote": quote,
                        }
                    ],
                }
            )

        return json.dumps(
            {
                "documentType": "INSURANCE_POLICY",
                "confidenceScore": 0.95,
                "title": "Comprehensive Health Insurance Policy",
                "summaryBullets": [
                    "Total sum insured of ₹10,00,000 for the policy year.",
                    "Policy coverage period active through March 31, 2027.",
                    "Co-pay clause of 10% applies to non-network hospital claims.",
                ],
                "importantAlerts": [
                    "Renewal deadline in 30 days.",
                    "Pre-existing diseases covered after 24 months waiting period.",
                ],
                "suggestedQuestions": [
                    "What is my room rent capping limit?",
                    "Are maternity expenses covered under this policy?",
                    "What is the procedure for cashless claims?",
                ],
                "recommendedActions": [
                    {
                        "actionType": "RENEWAL_REMINDER",
                        "title": "Renew Insurance Policy",
                        "dueDate": "2027-03-31T00:00:00Z",
                    }
                ],
                "payload": {
                    "policyNumber": "POL-987654321",
                    "sumInsured": 1000000,
                    "premiumAmount": 18500,
                    "insurerName": "Star Health & Allied Insurance",
                    "policyholderName": "Jane Doe",
                },
                "citations": [
                    {
                        "pageNumber": 1,
                        "sectionHeading": "Policy Schedule",
                        "exactQuote": "Sum Insured: Rs. 10,00,000/-",
                    },
                    {
                        "pageNumber": 3,
                        "sectionHeading": "Waiting Periods (Section 4.1)",
                        "exactQuote": "Pre-existing diseases covered after 24 consecutive months.",
                    },
                ],
            }
        )

    async def _embed_via_api(self, texts: list[str]) -> list[list[float]]:
        """Call a real embeddings endpoint (OpenAI-compatible).

        Prefers Portkey (unified gateway w/ fallbacks); falls back to direct
        OpenAI when only OPENAI_API_KEY is configured. Raises on failure so
        callers can decide whether embedding is optional or required.
        """
        api_key = None
        base_url = None
        embedding_model = settings.DEFAULT_EMBEDDING_MODEL
        client_kwargs: dict[str, Any] = {}

        if self.portkey_client is not None:
            api_key = self.portkey_api_key
            base_url = "https://api.portkey.ai/v1"
        elif self.gemini_api_key and not self.openai_api_key:
            api_key = self.gemini_api_key
            base_url = settings.OPENAI_BASE_URL or "https://generativelanguage.googleapis.com/v1beta/openai/"
            if embedding_model == "text-embedding-3-small":
                embedding_model = "text-embedding-004"
        elif self.openai_api_key or settings.OPENAI_BASE_URL:
            api_key = self.openai_api_key or "local-model"
            base_url = settings.OPENAI_BASE_URL or "https://api.openai.com/v1"

        if not api_key:
            raise RuntimeError("No embeddings provider configured")

        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=api_key, base_url=base_url, **client_kwargs)
        response = await client.embeddings.create(
            model=embedding_model,
            input=texts,
        )
        # Preserve request order defensively
        ordered = sorted(response.data, key=lambda d: d.index)
        vectors: list[list[float]] = []
        target_dim = settings.EMBEDDING_DIMENSION
        for item in ordered:
            raw_vec = list(item.embedding)
            if len(raw_vec) < target_dim:
                # Pad to schema dimension (e.g. 768 -> 1536) preserving unit norm
                raw_vec = raw_vec + [0.0] * (target_dim - len(raw_vec))
            elif len(raw_vec) > target_dim:
                # Truncate and re-normalize if model output is larger
                raw_vec = raw_vec[:target_dim]
                norm = sum(x * x for x in raw_vec) ** 0.5
                if norm > 0:
                    raw_vec = [x / norm for x in raw_vec]
            vectors.append(raw_vec)

        if len(vectors) != len(texts):
            raise RuntimeError(
                f"Embeddings count mismatch: got {len(vectors)} for {len(texts)} inputs"
            )
        return vectors

    async def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        # FIX (ISSUE-004): use a real embeddings API when credentials exist so
        # semantic retrieval actually ranks by meaning. Offline/dev mode keeps
        # a deterministic pseudo-vector fallback so CI needs no secrets — but
        # note those vectors carry NO semantic signal; hybrid search therefore
        # also runs a lexical leg which works in every environment.
        if (
            self.portkey_api_key
            or self.openai_api_key
            or self.gemini_api_key
            or settings.OPENAI_BASE_URL
        ):
            try:
                return await self._embed_via_api(texts)
            except Exception as e:
                logger.error(
                    "Real embeddings call failed; falling back to offline vectors",
                    error=str(e),
                )

        embeddings = []
        for text in texts:
            import hashlib

            seed = int(hashlib.sha256(text.encode()).hexdigest(), 16) % (10**8)
            import random

            rng = random.Random(seed)
            vec = [rng.uniform(-0.1, 0.1) for _ in range(settings.EMBEDDING_DIMENSION)]
            # normalize
            norm = sum(x * x for x in vec) ** 0.5
            norm_vec = [x / norm for x in vec]
            embeddings.append(norm_vec)
        return embeddings


ai_gateway_service = AIGatewayService()
