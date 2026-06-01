# Phase 6 — Multi-Agent Research Framework (4-Agent MVP)

**Duration**: 5 weeks (Oct–Nov 2026)
**Dependencies**: Phase 5 (RAG), Phase 3 (ethics), Phase 4 (literature)
**Output**: Four-agent orchestration framework with structured communication, falsification, and NegativeResultRegistry

**Agents in MVP**: SupervisorAgent, LiteratureReviewAgent, FalsificationAgent, EthicsAgent
**Agents deferred to post-pilot**: NullHypothesisAgent, HypothesisCriticAgent, MethodologyAdvisorAgent, EvidenceValidatorAgent

---

### Task 6.1: Agent Communication Protocol

- [ ] 6.1.1: `AgentMessage` — typed Pydantic model: sender, recipient, message_type, payload (Pydantic model), timestamp, thread_id, provenance_parent_id
- [ ] 6.1.2: Message types — `Query`, `Response`, `Task`, `Result`, `Review`, `Flag`, `Escalate`, `Log`
- [ ] 6.1.3: `AgentBus` — message routing, subscription, delivery guarantees
- [ ] 6.1.4: Thread management — grouping messages by research context
- [ ] 6.1.5: Message persistence — all messages stored in provenance graph
- [ ] 6.1.6: Asynchronous message handling — agents process messages as they arrive (non-blocking)

### Task 6.2: SupervisorAgent

- [ ] 6.2.1: Orchestration state machine — idle → planning → executing → reviewing → completed → failed
- [ ] 6.2.2: Research plan generation — decompose research question into subtasks for specialist agents
- [ ] 6.2.3: Task queue management — prioritize, dispatch, track completion
- [ ] 6.2.4: Agent health monitoring — heartbeat, timeout detection, restart
- [ ] 6.2.5: Conflict resolution — when specialist agents disagree, manage adjudication workflow
- [ ] 6.2.6: Human handoff — detect when to pause for human input (Tier 1/2 ethical gates, resource constraints)
- [ ] 6.2.7: Session persistence — save/restore research session state

### Task 6.3: LiteratureReviewAgent

- [ ] 6.3.1: Query decomposition — break research question into search subqueries
- [ ] 6.3.2: Multi-source search dispatch (Phase 4 engines)
- [ ] 6.3.3: Result deduplication and relevance filtering
- [ ] 6.3.4: Literature synthesis — structured summary with citation support
- [ ] 6.3.5: Gap identification — find areas with insufficient literature coverage
- [ ] 6.3.6: Contradiction detection — identify conflicting findings across sources
- [ ] 6.3.7: Evidence quality assessment — rate sources by methodology, sample size, citation impact, retraction status

### Task 6.4: FalsificationAgent

- [ ] 6.4.1: Popperian falsification search — given a hypothesis, actively search for evidence that contradicts it
- [ ] 6.4.2: Counter-example generation — construct scenarios where hypothesis would fail
- [ ] 6.4.3: Experimental confound identification — find variables not controlled for in hypothesis design
- [ ] 6.4.4: Alternative explanation generation — propose competing hypotheses for same phenomenon
- [ ] 6.4.5: Methodology critique — evaluate whether proposed tests actually test the hypothesis
- [ ] 6.4.6: Falsification report — structured document: hypothesis, attempts to falsify, results, remaining uncertainty

### Task 6.5: EthicsAgent

- [ ] 6.5.1: Query EthicalFirewall (Phase 3.1) for all hypotheses and research directions
- [ ] 6.5.2: Tier classification (Phase 3.2) for research context
- [ ] 6.5.3: Dual-use flagging — scan for DURC patterns in research questions and proposed experiments
- [ ] 6.5.4: Data sovereignty check — verify data sources have appropriate consent/usage rights
- [ ] 6.5.5: Carbon budget check — estimate compute cost of proposed experiments
- [ ] 6.5.6: Ethics report — structured document: risks identified, tier classification, flags raised, recommendations
- [ ] 6.5.7: Escalation — for Tier 1/2 issues, pause workflow and notify human

### Task 6.6: NegativeResultRegistry

- [ ] 6.6.1: `NegativeResult` model — hypothesis tested, method used, data summary, result (null, contradictory, inconclusive), confidence, reason for failure, suggestion for future work
- [ ] 6.6.2: `RegistryStore` — persistent storage (SQLite local, PostgreSQL server)
- [ ] 6.6.3: Registry search — query by domain, hypothesis topic, method, date
- [ ] 6.6.4: Registry cross-link — connect negative results to related literature (show when someone tried and failed)
- [ ] 6.6.5: Registry visualization — "graveyard" browser with search and filter
- [ ] 6.6.6: Registry export — JSON, CSV, RO-Crate
- [ ] 6.6.7: Automated submission — when FalsificationAgent successfully falsifies a hypothesis, result is automatically registered

### Task 6.7: Workflow Orchestration

- [ ] 6.7.1: Predefined workflow templates:
  - Literature review → gap identification → hypothesis generation → falsification attempt → report
  - Hypothesis → experimental design → ethics review → falsification → negative result registration
  - Literature search → contradiction detection → alternative hypothesis proposal → review
- [ ] 6.7.2: Custom workflow builder — define agent chains programmatically
- [ ] 6.7.3: Workflow status tracking — progress, bottlenecks, estimated completion
- [ ] 6.7.4: Workflow provenance — full agent interaction trace stored

### Task 6.8: Agent Diversity Guarantee

- [ ] 6.8.1: Agent diversity config — SupervisorAgent assigns different model providers, temperatures, and objective functions per agent role at session start
- [ ] 6.8.2: Heterogeneous tournament validation — verify at session start that no two agents share identical configuration (model + temperature + objective)
- [ ] 6.8.3: ConfabulationDetector integration — all agent outputs pass through ConfabulationDetector (Phase 3.9) before acceptance into research context
- [ ] 6.8.4: Cross-agent citation validation — when one agent cites a source, another agent independently verifies the citation claims against the source text

### Task 6.9: Multi-Agent Tests

- [ ] 6.9.1: Unit tests for AgentMessage model and AgentBus routing
- [ ] 6.9.2: Unit tests for SupervisorAgent state machine and task queue
- [ ] 6.9.3: Unit tests for LiteratureReviewAgent — query decomposition, synthesis
- [ ] 6.9.4: Unit tests for FalsificationAgent — counter-example generation, confound identification
- [ ] 6.9.5: Unit tests for EthicsAgent — DURC flagging, tier classification
- [ ] 6.9.6: Unit tests for NegativeResultRegistry — create, search, cross-link, export
- [ ] 6.9.7: Unit tests for AgentDiversityConfig — diversity assignment, heterogeneous validation
- [ ] 6.9.8: Integration test: full research workflow (literature review → hypothesis → falsification → ethics → negative result registration)
- [ ] 6.9.9: Integration test: ethics escalation stops Tier 1 workflow
- [ ] 6.9.10: Integration test: agent diversity config prevents homogeneous agent assignment

---

**Phase 6 Exit Criteria**: All 4 agents operational. End-to-end workflow completes: research question → literature review → hypothesis → falsification attempt → ethics review → negative result (if falsified) or report (if not falsified). Provenance traces every interaction.
