# HARIKA Engineering Instructions

## Mission

HARIKA is being developed as a natural, human-like AI operating system.

The goal is NOT to create a huge collection of hardcoded commands, aliases, keywords, or if/else rules.

The goal is to build a reusable cognitive architecture where natural language is understood semantically and mapped to existing capabilities.

## Current Architecture

HARIKA already contains:

- Cognitive Core
- Router / Classifier / Resolver
- Tool Manager
- Tool Planner
- Desktop application tools
- Website tools
- Memory system
- Planning system
- Agent system
- Vision system
- Voice system
- Presence / communication layer
- Verification system
- React frontend
- Persistent history and state

Preserve working functionality.

## Core Engineering Principle

Separate:

1. Language understanding
2. Intent / goal interpretation
3. Capability selection
4. Deterministic execution
5. Verification
6. Natural response generation

LLMs may be used for semantic interpretation and reasoning.

LLMs must NOT directly execute arbitrary OS actions.

Execution must remain deterministic, permission-aware, and verifiable.

## Avoid Hardcoding

DO NOT solve natural-language variation by continuously adding:

- aliases
- keyword lists
- phrase lists
- large if/else chains
- one-off regex rules
- individual handlers for every wording

For example, do NOT keep adding rules such as:

"calci" -> calculator
"calc" -> calculator
"bring calculator" -> calculator
"start calculator" -> calculator

Instead, build reusable semantic interpretation that can understand these variations and resolve them to the existing Calculator capability.

The same mechanism should work for future capabilities such as:

- Spotify
- YouTube
- browser actions
- files
- applications
- media
- communication
- system controls
- productivity tools

## Existing Capability Reuse

Before creating a new tool:

1. Search the repository for an existing capability.
2. Understand its interface.
3. Reuse it if possible.
4. Extend the abstraction only when necessary.

Do not duplicate existing functionality.

## Cognitive Core

The Cognitive Core should become the central semantic boundary.

It should eventually be capable of determining:

- what the user means
- what goal they are trying to accomplish
- relevant entities
- required capability
- required parameters
- whether clarification is necessary
- whether the request is actionable
- whether the requested capability is unsupported

Do not turn Cognitive Core into another hardcoded classifier.

## Context

Use available:

- conversation history
- short-term context
- memory
- current system state
- capability information

when relevant.

A natural follow-up such as:

"open calculator"

followed by:

"now close it"

should be interpreted using context rather than requiring every possible phrase to be hardcoded.

## Execution Safety

Never allow an LLM response to directly become an arbitrary shell command or OS operation.

The pipeline should remain conceptually:

User language
→ semantic interpretation
→ structured capability/action
→ policy validation
→ deterministic tool execution
→ verification
→ response

## Testing

Do NOT run the entire test suite repeatedly unless explicitly necessary.

Prefer focused tests.

Every test command must have a reasonable timeout.

If a test hangs:

1. Stop it.
2. Determine why it hangs.
3. Do not repeatedly rerun the same hanging command.

Never claim a test passed unless the command actually returned a successful exit code.

## Development Workflow

For every meaningful task:

1. Inspect the relevant architecture first.
2. Identify the actual root cause.
3. State the implementation plan.
4. Make coherent changes rather than scattered patches.
5. Run focused verification.
6. Run `git diff --check`.
7. Review the resulting diff.
8. Stop when the requested objective is satisfied.

Do not continue inventing unrelated work.

## Scope Control

Do not modify unrelated systems.

Do not rewrite stable functionality simply because it could be redesigned better.

Do not change conversational/presence behavior unless the current task requires it.

Do not modify working tools unnecessarily.

## Important

HARIKA is approaching a presentation-ready milestone.

Prioritize:

- reliability
- natural interaction
- architectural scalability
- predictable execution
- clear responses
- demonstrable capabilities

over adding dozens of superficial features.

The objective is a strong reusable foundation, not a giant list of hardcoded commands.

## Completion Rule

When a task is complete:

- stop
- report exactly what changed
- report tests actually executed
- report failures honestly
- report any remaining limitations

Do not continue running speculative tests or making additional changes without a new objective.