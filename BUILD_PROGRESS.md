# Build progress — 2026-09-10

## Implemented and locally checked

1. Explicit capability policy: unknown roles and unknown actions deny; private
   native actions require admin identity and phone approval. Legacy browser skill
   execution, token-only enrollment and legacy cloud POST actions are disabled.
2. Private model context is omitted for guests. Chat history is bounded, isolated
   by recognized session and verification state, and not stored durably.
3. Face float32 decoding fixed. Missing anti-spoof support denies verification.
4. Memory transactions work in RAM with atomic encrypted commits and process locks.
5. Native orb, answer panels, paged read-only folder view, expand/shrink and three
   validated theme previews with persisted owner changes and undo.
6. One microphone reader forwards actual commands. One task worker keeps network
   and approval waits outside the Tk event loop. Stop cancels pending work.
7. Explicit saved facts/protected facts; temporary lesson drafts; named saved
   lessons; exact-key forgetting. A lesson is not automatically a new capability.
8. Advisory council calls execute concurrently with a bounded number of workers.
9. iPhone approval protocol displays a task and checks HTTPS, nonce, phrase and
   owner face/liveness; enrollment and real phone integration remain deferred.

## Verification

- `python -B test_foundations.py`: 14 offline regression checks, fake credentials
  and temporary stores only. Includes deny rules, private context, template dtype,
  memory write concurrency/corruption, folder scope, theme undo, cancellation,
  disabled generated-code activation, task-bound single-use grants and HTTP denial.
- `python -B test_native_ui.py`: native widget and worker/event-loop smoke test.
- Python syntax parsed without importing biometric, cloud or credential modules.
- Native screenshot capture failed in this environment. Visual appearance has
  not been approved by on-screen inspection. No sustained hardware performance
  benchmark or real microphone/biometric accuracy test has been completed.

## Still required before claiming the larger vision is complete

- Structured enrollment and iPhone-trusted HTTPS/pairing setup. The user asked
  to defer enrollment; no real face, voice, phrase or credential was changed.
- Hands-free iPhone approval and device testing; hardware-backed authentication
  should be evaluated. Current face matching is not Apple's Face ID.
- Durable per-person relationships, visitor naming and granular delegated access.
- Real web research with source tracking, references converted to validated theme
  proposals, isolated skill execution tests, versioning and rollback.
- Broader supported app workflows, outcome verification, startup scheduling and
  reminder delivery when LYA is not running.
- Local voice/model installation, latency/resource measurement and cloud routing
  chosen against the actual laptop and Oracle VM specifications.
- Independent security review before any sensitive investigative deployment.

The existing legacy skills remain in the repository. They are not automatically
exposed as executable native commands. This intentionally prevents an unchecked
skill from bypassing the new permissions; supported actions must be integrated
and tested explicitly. A local process running as the same Windows user remains
outside the app-level identity boundary and can potentially access its secrets.
