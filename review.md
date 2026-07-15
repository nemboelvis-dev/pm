# Self-Review Improvements

The current code is appropriate for its stated local MVP scope. If the project were moving toward production, these are the five improvements I would prioritize.

## Remediation status

- Database-backed password verification is now implemented; the broader production identity and cookie hardening remains intentionally deferred for the local MVP.
- A migration framework remains deferred until the schema has a real version-two change; adding it now would conflict with the project's simplicity requirement.
- Bounded OpenRouter retry, `Retry-After`, and a 50-message prompt cap are implemented. Deeper metrics and history summarization remain future work.
- Server-issued user-message IDs and automatic chat scrolling are implemented. The mobile drawer, cancellation, and virtualization remain out of MVP scope.
- CI now runs backend, frontend, browser, audit, and Docker checks, and Compose has a health check. Broader Python typing, coverage, accessibility, and cross-browser gates remain future work.

1. **Replace MVP authentication with production identity and session security.** Store real users with verified password hashes, require a strong `SESSION_SECRET`, set `Secure` cookies under HTTPS, add CSRF protection where appropriate, rate-limit login, and use a mature authentication/session library. The current hardcoded credentials and fallback secret are intentionally local-only.

2. **Add formal database migrations and a clearer data-access layer.** The current schema is created with `CREATE TABLE IF NOT EXISTS` and a single `user_version`. A growing application should use ordered migrations, test upgrades from old versions, and separate SQL repositories or services from HTTP route functions. This would make schema evolution and a future move from SQLite to PostgreSQL safer.

3. **Improve AI reliability, cost control, and observability.** Add bounded retry and backoff for retryable OpenRouter responses, honor `Retry-After`, record request IDs and token usage without logging prompts or secrets, cap or summarize old chat history, and expose clear operational metrics. A transient upstream 502 was observed during final live verification, so this is the most concrete external reliability improvement.

4. **Polish chat and responsive board user experience.** Return both newly saved messages from the API instead of constructing a temporary user-message ID in the browser, auto-scroll to new messages, add a compact mobile chat drawer, improve focus management, allow request cancellation, and consider virtualization if boards or histories become large.

5. **Add continuous integration and broader quality gates.** Run pytest, frontend lint, unit tests, production build, Playwright, dependency audits, and Docker smoke tests automatically on every change. Add Python formatting, linting, static type checking, coverage thresholds, cross-browser tests, automated accessibility checks, and a container health check. Keep paid live AI tests in a separate manually approved workflow.
