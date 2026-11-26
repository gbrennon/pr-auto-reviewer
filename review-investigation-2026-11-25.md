# Review Investigation: PR #247

Date: 2026-11-25

## Finding

The daemon is not failing to decrypt its encrypted stores. It starts successfully
and reaches review execution, but review attempts fail because no LLM model is
configured.

The effective configuration reports:

```text
llm.model = ""
```

The service journal shows the failure before any LLM or platform request:

```text
review_pull_request_service._run_multi_phase_review
llm_agent_adapter._resolve_model
ValueError: A configured LLM model is required.
```

Observed at approximately 22:39 and again at 23:00 local service time. The HTTP
request summary for the failed review reports no HTTP requests.

## Encryption verification

The installed CLI can validate the encrypted store successfully with exit status
0, and the service restarted and remained active without encryption or decryption
errors. Secret values were not recorded.

The running systemd process does not define `PR_AUTO_REVIEWER_ENCRYPTION_KEY`;
the application is using the configured user-file fallback instead.

## Impact

Before the resolution below, no current-head review could complete until a
valid LLM model was configured. PR #247 was not treated as reviewed based on
the stale approval for an earlier commit.

## Resolution

The OpenAI-compatible client now permits an empty model identity and omits the
`model` field from the request payload. `ReviewPullRequestService`,
`AgentConversationService`, and the multi-phase orchestrator forward the empty
identity. This supports single-model llama.cpp servers while retaining
configured model identities when they are available.

The installed package and service must be refreshed before the daemon can retry
the review.
