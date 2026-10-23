# Documentation

## Start here

- [Project overview and setup](../README.md)
- [Teacher pilot: bài học Java đầu tiên](architecture/teacher-pilot-vi.md)
- [Nguồn bài giảng và thiết kế học qua trò chuyện](architecture/user-grounded-learning-vi.md)
- [Phase reports and evidence](roadmap/README.md)
- [Java discovery contract audit](roadmap/phases/RUNTIME_JAVA_DISCOVERY_CONTRACT_1/README.md)
- [Validation and execution safety](VALIDATION_EXECUTION_SAFETY.md)
- [Technical debt](TECHNICAL_DEBT.md)

## Documentation areas

| Area | Contents |
|---|---|
| [Phase roadmap](roadmap/README.md) | One folder per phase, including reports, attempts, JSON evidence and validation logs. |
| [Designs](designs/) | Dated implementation and contract designs. |
| [Audits](audits/) | Repository reviews, findings and follow-up records. |
| [Governance](governance/) | Project governance guidance. |
| [Benchmarks](benchmarks/) | Benchmark documentation. |
| [Examples](examples/) | Worked examples. |
| [Planning history](superpowers/) | Historical specifications and implementation plans. |

## Operating guides

- [Debug workflow](debug_workflow_map.md)
- [Demo flow](demo_flow.md)
- [Read-only MCP](MCP_READONLY.md)
- [Project evolution mode](project_evolution_mode.md)
- [Web UI information architecture](web_ui_information_architecture.md)
- [Background reporter](README_BACKGROUND_REPORTER.md)
- [Windows background scheduling](WINDOWS_TASK_SCHEDULER_BACKGROUND.md)

## Broader roadmap and review history

- [Operating roadmap: June 2026 and next](AI_Coding_Agent_Mentor_Operating_Roadmap_2026-06-Next.md)
- [Operating roadmap: 2026-06-07](AI_Coding_Agent_Mentor_Operating_Roadmap_2026-06-07.md)
- [Roadmap refresh: 2026-05-16](AI_Coding_Mentor_Roadmap_Refresh_2026-05-16.md)
- [Architecture audit: 2026-06-11](CATTUS_ARCHITECTURE_AUDIT_2026-06-11.md)
- [Repository audit: 2026-06-22](audit-2026-06-22.md)
- [Phase 13 audit](phase13_ultracode_audit.md)
- [Roadmap truth audit](ROADMAP_TRUTH_AUDIT_2026-05-20.md)
- [Project map upgrade plan](project_map_upgrade_plan.md)

These established guides retain their existing paths for references from code and planning history.

## Adding phase documentation

Use `docs/roadmap/phases/<PHASE_NAME>/`, with the phase name matching the report
filename stem. Keep the Markdown report and its JSON/text companions together.
Keep retries and other attempts in their parent phase folder. Add a link to the
[phase index](roadmap/README.md).

Historical evidence retains its recorded values and hashes. The
[documentation relocation record](roadmap/organization/README.md) maps former
paths to their current locations and explains the few files that must stay at
stable paths.
