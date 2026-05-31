# Phase 0.5 — User Research

**Duration**: 2 weeks (Jun 2026)
**Dependencies**: Phase 0 (bare repo exists)
**Output**: Validated value proposition or pivot decision

---

### Task 0.5.1: Define Interview Protocol

- [ ] 0.5.1.1: Draft interview guide — current workflow (literature review, hypothesis generation, experimental design, AI tool use); pain points in existing tools; feature prioritization (local-first, BYOK, provenance, falsification); willingness-sensitivity-to-price (Van Westendorp or similar)
- [ ] 0.5.1.2: Define target segments — molecular biology (wet lab), computational biology (dry lab), ecology/field science, clinical research, computational chemistry
- [ ] 0.5.1.3: Create informed consent form for interview recording and anonymized quotes
- [ ] 0.5.1.4: Create interview scoring rubric — enthusiasm level (1-5), pain point severity, fit with Skepsis architecture, likelihood of pilot participation

### Task 0.5.2: Recruit Participants

- [ ] 0.5.2.1: Identify 20+ potential participants across all 5 segments
- [ ] 0.5.2.2: Reach out via email, Twitter/DM, academic mailing lists, institutional contacts
- [ ] 0.5.2.3: Schedule 30-45 minute video interviews
- [ ] 0.5.2.4: Target: 12+ completed interviews (minimum 2 per segment, bonus for overlapping segments)

### Task 0.5.3: Conduct Interviews

- [ ] 0.5.3.1: Record with consent (audio/video for internal synthesis only)
- [ ] 0.5.3.2: Follow structured protocol but allow open-ended follow-up
- [ ] 0.5.3.3: Score each interview on rubric
- [ ] 0.5.3.4: Collect specific quotes for future use (with attribution permission)
- [ ] 0.5.3.5: Ask for referrals at end of each interview (snowball sampling)

### Task 0.5.4: Synthesize Findings

- [ ] 0.5.4.1: Transcribe or summarize each interview
- [ ] 0.5.4.2: Compile feature prioritization matrix (what scientists actually want vs. what roadmap assumes)
- [ ] 0.5.4.3: Identify top 3-5 pain points with frequency and intensity scores
- [ ] 0.5.4.4: Identify willingness-to-pay range per segment
- [ ] 0.5.4.5: Produce user personas (2-3 archetypal researchers)
- [ ] 0.5.4.6: Identify competing tools currently used and dissatisfaction levels
- [ ] 0.5.4.7: Document "jobs to be done" for each segment

### Task 0.5.5: Go/No-Go Decision

- [ ] 0.5.5.1: Compile synthesis document at `docs/user-research-synthesis.md`
- [ ] 0.5.5.2: Decision criteria:
  - At least 8 out of 12 interviewees rate "local-first scientific AI with provenance" as high priority (4+ on 5-point scale)
  - At least 3 interviewees express willingness to participate in a pilot program
  - No more than 2 interviewees identify a critical flaw that the roadmap cannot address
- [ ] 0.5.5.3: If all criteria met → proceed to Phase 1
- [ ] 0.5.5.4: If criteria partially met → adjust roadmap scope and re-interview 3-5 more scientists
- [ ] 0.5.5.5: If criteria not met → convene decision meeting to evaluate pivot or project restart
- [ ] 0.5.5.6: Commit synthesis document to repo (with PII removed)

---

**Phase 0.5 Exit Criteria**: Written go/no-go decision in `docs/user-research-synthesis.md`. If go, the roadmap is validated with real scientist input. If no-go, a pivot plan exists.
