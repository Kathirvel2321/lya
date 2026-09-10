# LYA product direction

Recorded from the owner's discussion on 2026-09-10. This is a requirements record, not a claim that the features already work. Architecture suggestions below remain proposals.

## Purpose

LYA is an ambitious personal assistant inspired by Jarvis: conversational, context-aware, able to research, plan and carry out useful tasks across the owner's connected devices. Face recognition is one supporting subsystem, not the project purpose. Build within the owner's existing hardware and zero-subscription budget using suitable open-source components.

## Required experience

- A native desktop presence, not a separate website or browser dashboard as the primary interface.
- "Hey LYA" / "wake up LYA" reveals a small circular assistant similar in interaction to Siri.
- Requested files, answers and task results appear in focused floating panels.
- Clicking/touching or saying "LYA zoom" / "open full screen" expands the workspace; shrinking returns to the orb.
- Mature, precise, clean futuristic styling. Avoid childish decoration, crowded HUDs and invented telemetry.
- Fast response, smooth motion, low idle resource consumption and graceful recovery are core requirements. Actual CPU, RAM, latency and stability must be measured; perfection is an aspiration, not a guarantee.
- Laptop and phone access, useful offline operation, and remote access to paired devices when connectivity permits.

## Identity and permission requirements

- Everyday low-risk interactions use lightweight approximate laptop recognition for personalization. Uncertainty must not grant private access.
- With the present laptop camera/microphone, secure or confidential laptop actions require stronger verification through the paired phone, followed by execution on the laptop. A better desktop camera may change this later.
- Basic: general queries for unknown people.
- Intermediate: explicitly permitted tasks for recognized friends/family.
- Confidential delegated access: secret phrase plus explicit owner approval for the particular action.
- Highest sensitivity: primary admin only with strict fresh verification; cannot be delegated by merely knowing a phrase.
- Returning visitors can be recognized by name. Owner is asked about unfamiliar visitors and separately asked whether to add them. Person-specific conversations and learned facts must remain separated.
- Make camera use and biometric retention understandable and consensual.
- Structured admin enrollment is deferred. Do not enroll faces/voices or choose real credentials as part of development without a later enrollment request.

## Research candidates provided by the owner

- MiniMind: https://github.com/jingyaogong/minimind
- Recordly: https://github.com/webadderallorg/recordly
- DeerFlow: https://github.com/bytedance/deer-flow
- FreeLLMAPI: https://github.com/tashfeenahmed/freellmapi
- OmniRoute: https://github.com/diegosouzapw/OmniRoute
- OpenClaude: owner confirmed the name; exact repository remains unconfirmed.
- Oracle Cloud free-tier account: owner reports opening one; VM provisioning, shape, resources and applicable allowance remain unverified.

Evaluate each component for a specific capability, licensing, supported platforms, maintenance, real resource use, provider limits and integration cost. These projects are not all language models, and none has been approved for installation merely by appearing here.

## Proposed engineering direction

- Keep the desktop UI responsive independently of inference and long tasks. Stop decorative rendering when hidden and activate costly perception only when needed.
- Maintain one shared authorization path for every interface and tool. Phone approval should identify the exact pending operation and expire after use.
- Use cloud resources for optional heavier work while keeping essential local functions available during outages.
- Research evidence should inform important decisions. A council may review evidence and disagreements; agreement among models is not proof and cannot authorize actions.
- Use a fast single-model path for ordinary conversation and a bounded council for selected difficult decisions. Avoid installing multiple overlapping model gateways without demonstrated need.
- Establish measured performance budgets after confirming laptop and server specifications.

## Open details

- Phone is confirmed as iPhone; supported background behavior and approval UX need device testing.
- Laptop CPU/RAM/GPU (system information query was denied in this session).
- Whether an Oracle VM exists; its architecture, region, CPU/RAM and account limits.
- Exact OpenClaude repository.

## Further owner clarification

- Accessibility is a central motivation: people unable to use their hands should be able to operate supported device functions through LYA. Navigation, selection, scrolling, approvals and cancellation need hands-free paths.
- Available capabilities do not imply permission to act. LYA acts only following the owner's request or an explicitly authorized scheduled task; merely seeing something must not trigger changes.
- The owner wants goal-level instructions with conditional steps. LYA should inspect relevant state, choose steps within the authorized scope, execute and verify outcomes, and stop when uncertain or outside that scope.
- The requested example is opening Clash of Clans, checking free builders and resources, then choosing an affordable upgrade. This is a capability illustration, not authorization to operate the game now. Current LYA does not implement it. Automated gameplay also conflicts with Supercell's published rules; do not treat it as a suitable first integration.
- Folder browsing should appear as a smooth floating view connected to the orb, with navigation into folders, voice selection, scrolling and back navigation. Show permitted locations progressively rather than recursively loading the entire disk.
- User-directed visual customization should offer pattern/style previews, apply the owner's choice and support undo. Theme changes should use settings rather than rewriting executable code.
- Learning should retain useful preferences and validated workflows, with correction and forgetting. Do not promise human-level thought, universal device access, perfect reliability or automatic safe self-rewriting.
- For important decisions, provide evidence, alternatives, tradeoffs and disagreement when warranted instead of automatically agreeing with the owner.

## Learning and security clarification

The owner authorized implementing the plan in stages. LYA should distinguish temporary conversation from deliberately saved knowledge, organize retained information, and support admin-directed appearance changes from references. New behavior must not execute merely because a model generated it. The owner wants strong defensive protection, including for sensitive investigative use; no claim of being unhackable or suitable for police production use is justified by the current prototype or its tests.
