# Security Policy

## Reporting a Vulnerability

openSciRe takes security and trust seriously. If you discover a security
vulnerability, **please do not file a public issue**.

### Disclosure Process

1. **Report via email**: `security@openscire.dev`
   - Encrypt sensitive details using our PGP key (key ID: TBD — will be published
     when infrastructure is established).
2. **Acknowledgment**: We will acknowledge receipt within **72 hours**.
3. **Fix target**: We aim to release a fix within **14 days** of confirmation.
4. **Disclosure**: We will coordinate disclosure with you after a fix is released.

## Scope

In-scope:
- Code execution vulnerabilities in `openscire-core`, `openscire-sandbox-core`,
  and official packages
- Data integrity compromises in the provenance system (Ed25519 signing)
- Prompt injection or model jailbreaks that bypass the Ethical Firewall
- Unauthorized access to user-managed API keys (BYOK infrastructure)

Out-of-scope:
- Vulnerabilities in third-party LLM providers (OpenAI, Anthropic, etc.)
- Vulnerabilities in locally-hosted model backends (Ollama, vLLM, llama.cpp)
- Social engineering of project maintainers

## Responsible Disclosure

We ask that researchers follow coordinated disclosure practices. Please give us
a reasonable window to address issues before publication.

## Recognition

We maintain a security contributors list for verified, qualifying disclosures.
