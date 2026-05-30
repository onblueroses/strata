# Next.js Security Rules

Rule-ID-based checklist for Next.js applications. Each rule has a severity, what to check, a detection pattern, and a fix. Load this reference during step 1 (Plan Review) and step 4 (Attack Emulation) when the target is a Next.js app.

## Authentication & Authorization

### NEXT-AUTH-001: Server Actions are state-changing endpoints
**Severity:** Critical
**What:** Server Actions (`"use server"`) are POST endpoints. They need the same auth/authz checks as any API route. `useActionState` does not provide CSRF protection - Server Actions handle CSRF via origin checking, but authorization is your responsibility.
**Detect:** Grep for `"use server"` in files. Check each exported async function for auth checks before any state mutation.
**Fix:** Add session/token verification at the top of every Server Action that mutates data. Treat them as route handlers, not internal functions.

### NEXT-AUTH-002: Middleware auth is bypassable
**Severity:** High
**What:** Next.js middleware runs on the Edge Runtime and can be bypassed by direct API calls, rewrite tricks, or middleware matcher misconfigurations. Middleware is a convenience layer, not a security boundary.
**Detect:** Check if auth is ONLY in `middleware.ts` with no per-route verification. Look at `matcher` config for gaps (e.g., missing API routes, static paths that serve dynamic content).
**Fix:** Verify auth at the route handler / Server Component / Server Action level too. Middleware can reject early, but the route must re-verify.

## Environment & Secrets

### NEXT-ENV-001: `NEXT_PUBLIC_*` exposes secrets
**Severity:** Critical
**What:** Any env var prefixed `NEXT_PUBLIC_` is inlined into the client bundle at build time. It appears in the browser's JS source. This is by design but frequently misunderstood.
**Detect:** `grep -r "NEXT_PUBLIC_" .env*` - review every match. Check for API keys, tokens, database URLs, or anything that grants access.
**Fix:** Remove the `NEXT_PUBLIC_` prefix from any secret. Access it only in server-side code (Server Components, Route Handlers, Server Actions). If the client needs to call an API, proxy through a Next.js API route.

## Type Safety

### NEXT-TYPE-001: TypeScript types are not security boundaries
**Severity:** High
**What:** TypeScript types are erased at runtime. A `type SafeInput = { id: number }` does not prevent `{ id: "'; DROP TABLE users--" }` from reaching your server. Form data, URL params, and JSON bodies arrive as untyped values.
**Detect:** Check route handlers and Server Actions for raw `params`, `searchParams`, `formData`, or `request.json()` used without runtime validation.
**Fix:** Validate with Zod (or equivalent) at every server entry point. Parse incoming data into typed values - don't cast or assert.

## Caching & Data Leaks

### NEXT-CACHE-001: Static rendering leaks user data across requests
**Severity:** Critical
**What:** Static rendering (`"use cache"`, `generateStaticParams`, default caching) serves the same HTML to all users. If a Server Component fetches user-specific data during static generation, that data is baked into the page and served to everyone.
**Detect:** Look for `cookies()`, `headers()`, session reads, or user-specific DB queries inside statically rendered routes. Check for `"use cache"` on components that access per-user data.
**Fix:** Use `dynamic = "force-dynamic"` or `noStore()` for user-specific pages. Move personalized content to Client Components that fetch after hydration, or use `connection()` to opt out of static rendering.

## Redirects & URLs

### NEXT-REDIR-001: Open redirect via `redirect()`
**Severity:** High
**What:** `redirect(userInput)` or `redirect(searchParams.get('next'))` lets an attacker craft a URL that redirects to a malicious site after authentication, stealing credentials or session tokens.
**Detect:** Grep for `redirect(` and `permanentRedirect(`. Check if any argument comes from user input (params, searchParams, form data, headers).
**Fix:** Validate redirect targets against an allowlist of paths or domains. At minimum, ensure the URL starts with `/` and does not contain `//` (which browsers interpret as protocol-relative).

### NEXT-SSRF-001: Server-side fetch with user-controlled URLs
**Severity:** High
**What:** Server Components and Route Handlers run on the server. A `fetch(userProvidedUrl)` can reach internal services, cloud metadata endpoints (169.254.169.254), or localhost services invisible from the public internet.
**Detect:** Grep for `fetch(` in server-side code. Check if any URL component (host, path, query) comes from user input.
**Fix:** Validate URLs against an allowlist of permitted hosts. Block RFC1918 ranges, link-local addresses, and localhost. Use a URL parser - don't regex match.

## Content Security

### NEXT-CSP-001: CSP configuration gaps
**Severity:** Medium
**What:** Next.js supports CSP via middleware (dynamic nonce per request) or `next.config.js` headers (static). Static CSP cannot use nonces for inline scripts, forcing `unsafe-inline` which defeats XSS protection. Middleware-based CSP is stronger but requires careful configuration.
**Detect:** Check for CSP in `middleware.ts` (preferred) and `next.config.js` `headers()`. Look for `unsafe-inline`, `unsafe-eval`, or overly broad `connect-src` / `script-src` directives.
**Fix:** Use middleware-based CSP with per-request nonces. Avoid `unsafe-inline` and `unsafe-eval`. Scope `connect-src` to known API domains.

## File Handling

### NEXT-UPLOAD-001: Path traversal in file uploads
**Severity:** Critical
**What:** Route Handlers that accept file uploads and write to disk using the user-provided filename are vulnerable to path traversal (`../../etc/passwd`). Even reading files by user-provided path (e.g., serving uploads) can leak arbitrary files.
**Detect:** Check Route Handlers for `formData()` + file write operations. Look for user-controlled values in `fs.writeFile`, `createWriteStream`, or path construction.
**Fix:** Never use user-provided filenames directly. Generate a random filename (UUID/nanoid), store the original name in metadata only. Validate and sanitize paths with `path.basename()` at minimum, but random names are safer.

## Quick Reference

| Rule | Severity | One-liner |
|------|----------|-----------|
| NEXT-AUTH-001 | Critical | Auth-check every Server Action |
| NEXT-AUTH-002 | High | Don't rely on middleware alone for auth |
| NEXT-ENV-001 | Critical | No secrets in `NEXT_PUBLIC_*` |
| NEXT-TYPE-001 | High | Runtime-validate all server inputs |
| NEXT-CACHE-001 | Critical | No user data in static/cached pages |
| NEXT-REDIR-001 | High | Allowlist redirect targets |
| NEXT-SSRF-001 | High | Block internal URLs in server fetch |
| NEXT-CSP-001 | Medium | Middleware nonce CSP, no unsafe-inline |
| NEXT-UPLOAD-001 | Critical | Random filenames, never user-provided paths |
