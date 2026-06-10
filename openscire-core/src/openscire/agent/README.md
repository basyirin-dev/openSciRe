# openSciRe — Agent Orchestration

Purpose: Multi-agent research system with pub/sub communication (AgentBus), supervisor
orchestration, typed task/result models, health monitoring, conflict resolution, human handoff,
session persistence, workflow templating, and agent diversity guarantees.

Status: Stable

Public API:

- `AgentBus` — Singleton pub/sub message bus with typed messages, thread management, and provenance
  persistence
- `SupervisorAgent` — Central orchestrator: state machine
  (idle→planning→executing→reviewing→completed/failed), task queue with dependency resolution,
  health monitoring, conflict resolution, human handoff, session persistence, diversity assignment,
  confabulation detection, and citation validation
- `LiteratureReviewAgent` — Structured evidence-gathering agent: query decomposition, multi-source
  search (OpenAlex, PubMed), dedup, quality scoring, synthesis, gap analysis, contradiction
  detection
- `FalsificationAgent` — Popperian falsification agent: searches counter-examples, identifies
  confounds, generates alternative explanations, critiques methodology, auto-submits negative
  results
- `EthicsAgent` — Ethical review agent: scans via EthicalFirewall, classifies risk tier, flags
  dual-use, checks data sovereignty, estimates carbon cost, escalates high-risk findings
- `WorkflowOrchestrator` — Template-driven workflow execution: builds ResearchPlan from
  WorkflowDefinition, spawns SupervisorAgent, tracks progress with CPM bottleneck detection
- `DiversityManager` — Assigns unique (provider, model, temperature, objective) tuples per agent
  role
- `ConflictResolver` — Detects contradictory conclusions across agents, requests evidence, escalates
  if unresolved
- `HumanHandoff` — Manages pending/resolved handoffs requiring human intervention
- `AgentHealthMonitor` — Tracks heartbeat failures, restarts unresponsive agents, escalates after
  max failures
- `SessionManager` — JSON-serialized session persistence with save/restore/delete
- `SupervisorStateMachine` — Validates all state transitions
- `WorkflowTemplate` — Predefined templates: LITERATURE_TO_FALSIFICATION (6 steps),
  HYPOTHESIS_FULL_CYCLE (5 steps), CONTRADICTION_DETECTION (4 steps)
