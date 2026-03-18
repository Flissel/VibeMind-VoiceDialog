# Software Design.Space

**Requirements analysis and architectural design engine for intelligent system planning.**

## Overview

Software Design.Space is the architectural and requirements management layer of Vibemind, operating as the bridge between user intent and implementation. It handles requirements mining from existing systems, reverse engineering of software design patterns, technology stack preparation, and sophisticated requirements evaluation.

> **Hinweis:** Software Design ist als Submodul innerhalb des Shuttles-Space implementiert (`python/spaces/shuttles/swe_desgine/`). Es hat keinen eigenen dedizierten Backend-Agent — Shuttle-Events (`bubble.evaluate`, `bubble.promote`) werden vom BubblesAgent verarbeitet.

The space empowers users to understand their existing systems deeply, extract requirements from real-world applications, and make informed architectural decisions before development begins.

## Key Features

- **Requirements Mining**: Automatically extracts requirements from existing files, codebases, and documentation
- **Reverse Engineering**: Analyzes existing software to understand design patterns and architectures
- **Technology Stack Preparation**: Evaluates and recommends appropriate technology stacks for requirements
- **Autonomous Architecture Design**: Generates architectural proposals based on requirements and constraints
- **Billing Service Specifications**: Specialized templates for complex service design (e.g., billing systems)
- **Requirements Evaluation**: Validates requirements completeness and identifies gaps
- **Architecture Documentation**: Auto-generates design documents and decision records
- **Coding.Space Integration**: Passes validated designs to Coding.Space for implementation

## Technology Stack

- **Analysis Engine**: LLM-powered code and requirements analysis
- **Pattern Recognition**: Identifies design patterns from existing codebases
- **Knowledge Graph Tools**: LLM-powered knowledge graph for architectural decisions (kg_tools.py, rag_tools.py)
- **Requirements Framework**: Structured templates for various application types
- **Tech Stack Evaluator**: Comparative analysis of technology options
- **Documentation Generator**: Auto-generation of architecture documents
- **Reverse Engineering Tools**: LLM-based code and requirements analysis
- **Integration with Rowboat.Space**: Access to business requirements and context

## Shuttle-Wizard (wizard_handler.py)

Der Wizard orchestriert 4 Schritte für Requirements-Engineering:

| Schritt | Phase | Agent-Team |
|---------|-------|-----------|
| 1 | Mining → Project Context | ContextEnricher |
| 2 | Requirements → Stakeholders | StakeholderTeam, RequirementGapTeam |
| 3 | Knowledge Graph → Constraints | ConstraintTeam |
| 4 | TechStack → Finalize | Send to SWE Design |

Agent-Teams werden lazy aus `swe_desgine.requirements_engineer.wizard.wizard_agents` geladen.

## Submodul-Inhalt

Das SWE-Design-Submodul (`python/spaces/shuttles/swe_desgine/`) enthält:
- `ai_scientist/` — AI-Scientist System (Ideation, Writing, Plotting, VLM Review)
- `requirements_engineer/` — RE Config + Wizard Agents
- `external/arch_team/` — AutoGen-basierte Architektur-Validierung mit KG-Tools

## Current Status

- Requirements mining from existing files is operational
- Basic reverse engineering of design patterns is implemented
- Tech stack evaluation and recommendation is working
- Shuttle-Wizard mit 4 Schritten implementiert (`wizard_handler.py`)
- Agent-Teams (Context, Stakeholder, RequirementGap, Constraint) verfügbar
- AI-Scientist Subsystem vorhanden (Ideation, Writing, Plotting)
- Requirements evaluation framework is partially implemented
- Architecture design templates are in development
- Integration with Coding.Space is in progress

## Roadmap

- Complete requirements mining for multiple file types (Q2 2026)
- Implement advanced reverse engineering for complex architectures
- Add comparative tech stack analysis with trade-off matrices
- Develop specialized templates for common domains (e-commerce, SaaS, etc.)
- Build requirements validation with stakeholder collaboration features
- Create architecture decision record (ADR) system
- Implement cost estimation based on chosen architecture
- Add compliance and security requirement integration
- Enable architecture visualization and interactive design refinement

## How This Space Fits in the Vibemind Ecosystem

Software Design.Space is the thinking layer before code generation. Ideas.Space articulates what users want, and Software Design.Space figures out how to architect it properly. It analyzes Rowboat.Space business data to extract actual requirements. It works with Desktop.Space to understand existing systems. Its validated designs flow to Coding.Space for implementation. The Brain.Space can provide insights about similar projects and design patterns. Software Design.Space ensures Vibemind builds systems that are well-architected, maintainable, and aligned with organizational context.

