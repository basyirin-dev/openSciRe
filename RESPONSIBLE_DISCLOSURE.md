# Responsible Disclosure & Ethical Use Policy

## Dual-Use Research Policy

Project Skepsis builds tools for scientific reasoning, hypothesis generation,
and literature analysis. These tools can accelerate legitimate research — and
can, in the wrong context, lower barriers to harmful applications.

### Prohibited Use Cases

Use of Project Skepsis software (including all modules, APIs, and derivatives) is
**strictly prohibited** for:

1. **Weapons development**: Any application related to chemical, biological,
   radiological, or nuclear weapons design, delivery systems, or materials.
2. **Human subjects research without IRB approval**: Generating hypotheses or
   experimental designs involving human subjects without valid institutional
   review board approval.
3. **Surveillance**: Targeted surveillance, profiling, or monitoring of
   individuals without their informed consent and applicable legal authorization.
4. **Generating misinformation**: Creating fraudulent research, paper mills,
   fake datasets, or knowingly misleading scientific claims.
5. **Circumventing safety measures**: Using the tool to design experiments that
   bypass existing biosafety, chemical safety, or radiation safety protocols.

### Reporting Ethical Concerns

If you encounter:
- A use case you believe violates this policy
- A potential dual-use concern in the tool's design
- An unintended capability that raises ethical questions

Please report to: `ethics@skepsis-research.dev`

Reports are reviewed by the project maintainers within 7 days. Sensitive reports
can be encrypted using the PGP key published in `SECURITY.md`.

## Mitigations Built Into the Tool

- **Ethical Firewall** (Phase 3): Risk-tiered filtering of generated content
- **Provenance tracking** (Phase 1): All outputs cryptographically signed
- **Epistemic uncertainty quantification**: Confidence scores on all claims
- **Source grounding requirements**: Claims must cite verifiable sources

These are layered defenses, not guarantees. **No AI tool can fully prevent
misuse.** This policy reflects our commitment to try.

## Contributor Responsibility

By contributing code to Project Skepsis, you affirm that your contribution does
not weaken any of these safeguards, and that you have considered the dual-use
implications of your work.

---

*This document will be reviewed and updated quarterly, or after any identified
ethical incident.*
