<!-- keywords: node, nodejs, typescript, npm, pino, express, fastify, bun, vitest, ts-node, node project, type stripping -->
# Node.js + TypeScript Project Setup

Reference for Node.js projects using TypeScript with type stripping (Node 22.6+). Covers patterns that Claude Code gets wrong or that deviate from AI defaults. Sources: Matteo Collina's skill library (Node.js core team, Fastify author), Node.js documentation, production experience.

Design goal: no build step for development. TypeScript runs directly via type stripping. Build only for publishing distributable packages.

---

## Quick Nav

| Task | Section |
|------|---------|
| Start a new Node.js + TS project | 1. Project Bootstrap |
| Configure tsconfig for type stripping | 2. TypeScript Configuration |
| Set up testing | 3. Testing with node:test |
| Fix flaky tests | 4. Flaky Test Diagnosis |
| Handle errors properly | 5. Error Handling |
| Add graceful shutdown | 6. Graceful Shutdown |
| Configure logging | 7. Logging with Pino |
| Manage environment variables | 8. Environment Configuration |
| Work with streams | 9. Streams |
| Control async concurrency | 10. Async Patterns |
| Cache data | 11. Caching |
| Profile and benchmark | 12. Profiling |
| Optimize performance | 13. Performance |
| Explore node_modules | 14. node_modules Navigation |

---

## 1. Project Bootstrap

<details>
<summary>1. Project Bootstrap</summary>

### package.json

```json
{
  "type": "module",
  "main": "dist/index.js",
  "types": "dist/index.d.ts",
  "exports": {
    ".": {
      "types": "./dist/index.d.ts",
      "import": "./dist/index.js"
    }
  },
  "files": ["dist", "README.md", "LICENSE"],
  "scripts": {
    "build": "tsc -p tsconfig.build.json",
    "clean": "rm -rf dist",
    "prepublishOnly": "npm run clean && npm run build",
    "test": "node --test test/*.test.ts",
    "typecheck": "tsc --noEmit"
  },
  "engines": {
    "node": ">=22.6.0"
  }
}
```

### File structure

```
src/
  user/
    user.service.ts
    user.service.test.ts
    user.repository.ts
    user.repository.test.ts
  index.ts
test/
  integration/
```

Tests live next to source files for unit tests. Integration tests in `test/`.

### ESM rules

- Always `"type": "module"` in package.json
- Always include `.ts` extensions in imports
- Prefer named exports over default exports (better refactoring, tree-shaking)
- Use `import.meta.dirname` and `import.meta.filename` (Node 20.11+), not `__dirname`
- JSON imports: `import config from './config.json' with { type: 'json' }`

</details>

---

## 2. TypeScript Configuration

<details>
<summary>2. TypeScript Configuration</summary>

Type stripping removes type annotations at runtime without transpilation. No build step needed for development.

### Constraints (things that break type stripping)

These require code transformation and won't work:
- **Enums** - use `as const` objects instead
- **Namespaces** - use modules
- **Constructor parameter properties** (`constructor(public name: string)`) - declare properties explicitly
- **Legacy decorators** - use TC39 stage 3 syntax

### tsconfig.json (development)

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "noEmit": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "verbatimModuleSyntax": true,
    "allowImportingTsExtensions": true,
    "lib": ["ES2022"],
    "types": ["node"]
  },
  "include": ["src/**/*.ts", "test/**/*.ts"],
  "exclude": ["node_modules"]
}
```

Key options:
- `noEmit` - Node runs TS directly, no compilation
- `allowImportingTsExtensions` - allows `.ts` imports
- `verbatimModuleSyntax` - enforces `import type` for type-only imports
- `isolatedModules` - ensures compatibility with type stripping

### tsconfig.build.json (publishing only)

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "declaration": true,
    "declarationMap": true,
    "sourceMap": true,
    "outDir": "dist",
    "rootDir": "src",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "verbatimModuleSyntax": true,
    "allowImportingTsExtensions": true,
    "rewriteRelativeImportExtensions": true,
    "lib": ["ES2022"],
    "types": ["node"]
  },
  "include": ["src/**/*.ts"],
  "exclude": ["node_modules", "test"]
}
```

`rewriteRelativeImportExtensions` rewrites `.ts` to `.js` in output.

### Type-only imports

Always separate type imports from value imports:

```typescript
import type { User, Config } from './types.ts';
import { createUser, type UserOptions } from './user.ts';
```

### Enum replacement pattern

```typescript
const Status = {
  Active: 'active',
  Inactive: 'inactive',
} as const;

type Status = (typeof Status)[keyof typeof Status];
```

</details>

---

## 3. Testing with node:test

<details>
<summary>3. Testing with node:test</summary>

Use the built-in test runner (Node 22+). No Vitest/Jest needed for server-side code.

```bash
node --test test/*.test.ts
node --test --test-name-pattern="should create user" src/user.test.ts
```

### Core patterns

```typescript
import { describe, it, before, after, beforeEach, afterEach } from 'node:test';

describe('UserService', () => {
  let service: UserService;

  before(() => { service = new UserService(); });

  it('should create a user', async (t) => {
    const user = await service.create({ name: 'John' });
    t.assert.equal(user.name, 'John');
    t.assert.ok(user.id);
  });

  it('should throw on invalid input', async (t) => {
    await t.assert.rejects(
      () => service.create({ name: '' }),
      { message: 'Name is required' }
    );
  });
});
```

### Mocking via test context

```typescript
it('should send email via provider', async (t) => {
  const sendMock = t.mock.fn(async () => ({ success: true }));
  const provider = { send: sendMock };
  const service = new EmailService(provider);

  await service.sendWelcome('user@example.com');

  t.assert.equal(sendMock.mock.calls.length, 1);
  t.assert.deepEqual(sendMock.mock.calls[0].arguments, [
    'user@example.com',
    'Welcome!',
  ]);
});
```

### Method mocking and time mocking

```typescript
// Mock global fetch
t.mock.method(globalThis, 'fetch', async () => ({
  ok: true,
  json: async () => ({ id: '1', name: 'John' }),
}));

// Mock time
t.mock.timers.enable({ apis: ['Date'] });
t.mock.timers.setTime(new Date('2024-01-15T12:00:00Z').getTime());
```

### Per-test resource cleanup

Use `t.after()` instead of shared `afterEach` - colocated with resource creation, runs even on failure:

```typescript
it('should read file', async (t) => {
  const handle = await fs.open('test.txt');
  t.after(() => handle.close());

  const content = await handle.read();
  t.assert.ok(content);
});
```

### Database test isolation with transactions

```typescript
describe('database tests', () => {
  let db: Database;

  before(async () => { db = await Database.connect(testConfig); });
  after(async () => { await db.disconnect(); });

  beforeEach(async () => { await db.beginTransaction(); });
  afterEach(async () => { await db.rollback(); });

  it('should insert record', async (t) => {
    await db.insert({ name: 'test' });
    const records = await db.findAll();
    t.assert.equal(records.length, 1);
  });
});
```

### Snapshot testing

```typescript
it('should generate expected report', async (t) => {
  const report = await generateReport(sampleData);
  t.assert.snapshot(report);
});
```

### Dynamic ports (prevents EADDRINUSE in parallel tests)

```typescript
it('should start server', async (t) => {
  const server = await startServer({ port: 0 });
  const { port } = server.address();
  t.after(() => server.close());
  // ...
});
```

</details>

---

## 4. Flaky Test Diagnosis

<details>
<summary>4. Flaky Test Diagnosis</summary>

### Identification techniques

```bash
# Show which test hangs
node --test --test-timeout=5000

# Reproduce flakiness via repetition
for i in {1..50}; do node --test src/flaky.test.ts || echo "Failed on run $i"; done

# Expose race conditions with high concurrency
node --test --test-concurrency=10

# Find open handles keeping Node alive
```

```typescript
import wtfnode from 'wtfnode';

describe('Debug hanging tests', () => {
  after(() => { wtfnode.dump(); });
  it('might hang', async () => { /* ... */ });
});
```

### Common causes and fixes

**Race conditions**: Don't `setTimeout` and hope. Await the actual result.

```typescript
// Wrong: arbitrary delay
await new Promise(resolve => setTimeout(resolve, 100));
t.assert.equal(processed, true);

// Right: await the operation
const result = await processAsync();
t.assert.equal(result.processed, true);
```

**Time-dependent tests**: Use fixed dates or mock timers. Never assert against `new Date()`.

**Shared state between tests**: If tests pass alone but fail together, state is leaking. Use `beforeEach` to reset.

**Unhandled promise rejections**: Always `await` async operations in tests. Fire-and-forget calls may reject after the test ends.

**Port conflicts**: Use port 0 (see section 3).

**CI resource constraints**: CI has less CPU/memory. Set explicit timeouts:

```typescript
it('heavy computation', { timeout: 30000 }, async (t) => { /* ... */ });
```

</details>

---

## 5. Error Handling

<details>
<summary>5. Error Handling</summary>

### Custom errors with codes

Use `@fastify/create-error` or a minimal factory:

```typescript
import createError from '@fastify/create-error';

const NotFoundError = createError('NOT_FOUND', '%s not found', 404);
const ValidationError = createError('VALIDATION_ERROR', '%s', 400);

throw new NotFoundError('User');
```

### Minimal alternative (no dependency)

```typescript
interface AppErrorOptions {
  code: string;
  statusCode?: number;
  cause?: Error;
}

function createAppError(message: string, options: AppErrorOptions): Error {
  const error = new Error(message, { cause: options.cause });
  (error as any).code = options.code;
  (error as any).statusCode = options.statusCode ?? 500;
  Error.captureStackTrace(error, createAppError);
  return error;
}

function notFound(resource: string): Error {
  return createAppError(`${resource} not found`, { code: 'NOT_FOUND', statusCode: 404 });
}
```

### Check by code, not by class

```typescript
function isAppError(error: unknown): error is Error & { code: string; statusCode: number } {
  return error instanceof Error && 'code' in error && 'statusCode' in error;
}

if (isAppError(error) && error.code === 'NOT_FOUND') {
  return null;
}
```

### Unhandled rejections and exceptions

Don't handle `unhandledRejection` and `uncaughtException` manually. Use `close-with-grace` (see section 6) which handles these and triggers graceful shutdown.

</details>

---

## 6. Graceful Shutdown

<details>
<summary>6. Graceful Shutdown</summary>

Use [close-with-grace](https://github.com/fastify/close-with-grace). It handles SIGTERM, SIGINT, unhandled rejections, and uncaught exceptions.

```typescript
import closeWithGrace from 'close-with-grace';

closeWithGrace({ delay: 10000 }, async ({ signal, err }) => {
  if (err) console.error('Error triggered shutdown:', err);
  console.log(`Received ${signal}, shutting down...`);

  // Close in reverse order of initialization
  await server.close();
  await redis.quit();
  await db.end();
});
```

### Health checks that respect shutdown state

```typescript
let isShuttingDown = false;

function healthHandler(req: Request, res: Response) {
  if (isShuttingDown) return res.status(503).json({ status: 'shutting_down' });
  return res.json({ status: 'healthy' });
}

closeWithGrace({ delay: 10000 }, async ({ signal }) => {
  isShuttingDown = true;
  await new Promise((r) => setTimeout(r, 5000)); // let LB drain
  await cleanup();
});
```

### Kubernetes

Set delay slightly lower than `terminationGracePeriodSeconds` (default 30s):

```typescript
closeWithGrace({ delay: 25000 }, async ({ signal }) => {
  isShuttingDown = true;
  await new Promise((r) => setTimeout(r, 5000)); // k8s stops routing
  await server.close();
  await db.end();
});
```

</details>

---

## 7. Logging with Pino

<details>
<summary>7. Logging with Pino</summary>

Use [pino](https://github.com/pinojs/pino) for structured JSON logging.

```typescript
import pino from 'pino';

const logger = pino({ level: process.env.LOG_LEVEL || 'info' });

logger.info({ userId: user.id }, 'User created');
logger.error({ err, orderId: order.id }, 'Failed to process payment');
```

### Log levels

- `debug` - internal diagnostic detail
- `info` - operational events (user created, server started)
- `warn` - unexpected but handled (rate limit approaching)
- `error` - needs attention (payment failed)

### Pretty printing for development

```bash
node app.ts | pino-pretty
```

### Child loggers for request context

```typescript
const requestLogger = logger.child({ requestId: req.id, userId: req.user?.id });
requestLogger.info('Processing request');
```

### Redaction

```typescript
const logger = pino({
  redact: ['password', 'token', 'apiKey', 'req.headers.authorization'],
});
```

### debug module vs pino

- `pino` - application logging (structured, leveled, production)
- `debug` / `util.debuglog` - library/module tracing (diagnostic, toggled via `DEBUG=mymodule:*`)

</details>

---

## 8. Environment Configuration

<details>
<summary>8. Environment Configuration</summary>

### Loading env files

```bash
node --env-file=.env --env-file=.env.local app.ts
```

Or programmatically:

```typescript
import { loadEnvFile } from 'node:process';
loadEnvFile('.env.local');
```

### Validation with env-schema + TypeBox

```typescript
import { envSchema } from 'env-schema';
import { Type, Static } from '@sinclair/typebox';

const schema = Type.Object({
  PORT: Type.Number({ default: 3000 }),
  DATABASE_URL: Type.String(),
  API_KEY: Type.String({ minLength: 1 }),
  LOG_LEVEL: Type.Union([
    Type.Literal('debug'),
    Type.Literal('info'),
    Type.Literal('warn'),
    Type.Literal('error'),
  ], { default: 'info' }),
});

type Env = Static<typeof schema>;
export const env = envSchema<Env>({ schema });
```

### Avoid NODE_ENV

`NODE_ENV` conflates environment detection, behavior toggling, optimization, and security into one variable. Use explicit variables for each concern:

```typescript
const config = {
  logging: { level: process.env.LOG_LEVEL || 'info', pretty: process.env.LOG_PRETTY === 'true' },
  security: { rateLimitEnabled: process.env.RATE_LIMIT_ENABLED !== 'false' },
  database: { url: process.env.DATABASE_URL },
};
```

</details>

---

## 9. Streams

<details>
<summary>9. Streams</summary>

### Always use pipeline, never .pipe()

`.pipe()` swallows errors. `pipeline` propagates them properly.

```typescript
import { pipeline } from 'node:stream/promises';

await pipeline(
  createReadStream(input),
  createGzip(),
  createWriteStream(output)
);
```

### Async generators as transforms

```typescript
async function* parseLines(source: AsyncIterable<Buffer>): AsyncGenerator<string> {
  let buffer = '';
  for await (const chunk of source) {
    buffer += chunk.toString();
    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';
    for (const line of lines) yield line;
  }
  if (buffer) yield buffer;
}

await pipeline(createReadStream('input.txt'), parseLines, filterNonEmpty, createWriteStream('output.txt'));
```

### Stream consumers (Node 18+)

```typescript
import { text, json, buffer } from 'node:stream/consumers';

const data = await json(readableStream) as MyType;
const content = await text(readableStream);
```

### Backpressure

```typescript
import { once } from 'node:events';

for (const chunk of data) {
  const canContinue = writable.write(chunk);
  if (!canContinue) await once(writable, 'drain');
}
```

</details>

---

## 10. Async Patterns

<details>
<summary>10. Async Patterns</summary>

### Controlled concurrency

Unbounded `Promise.all` over large arrays exhausts memory and connections. Use p-limit or p-map:

```typescript
import pMap from 'p-map';

const results = await pMap(items, processItem, { concurrency: 5 });
```

### Promise.allSettled for partial failure tolerance

```typescript
const results = await Promise.allSettled(urls.map(url => fetch(url).then(r => r.text())));

for (const [i, result] of results.entries()) {
  if (result.status === 'fulfilled') handleSuccess(urls[i], result.value);
  else handleFailure(urls[i], result.reason);
}
```

### Factory functions instead of async constructors

Constructors can't be async. Use a static factory:

```typescript
class Database {
  private constructor(private connection: Connection) {}

  static async create(config: Config): Promise<Database> {
    const connection = await connect(config);
    return new Database(connection);
  }
}
```

### AbortController for cancellation

```typescript
async function fetchWithTimeout(url: string, timeoutMs: number): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { signal: controller.signal });
  } finally {
    clearTimeout(timeoutId);
  }
}
```

</details>

---

## 11. Caching

<details>
<summary>11. Caching</summary>

### async-cache-dedupe (preferred for async)

Deduplicates concurrent requests automatically - three simultaneous calls for the same key produce one DB query:

```typescript
import { createCache } from 'async-cache-dedupe';

const cache = createCache({ ttl: 60, stale: 5, storage: { type: 'memory' } });

cache.define('getUser', async (id: string) => {
  return await db.users.findById(id);
});

const user = await cache.getUser('123');
```

### Reference-based invalidation

```typescript
cache.define('getUser', {
  references: (args, key, result) => [`user:${result.id}`],
}, async (id: string) => db.users.findById(id));

cache.define('getUserPosts', {
  references: (args, key, result) => [`user:${args[0]}`],
}, async (userId: string) => db.posts.findByUserId(userId));

// Invalidates both getUser and getUserPosts for this user
await cache.invalidateAll('user:123');
```

### LRU for synchronous/bounded caching

```typescript
import { LRUCache } from 'lru-cache';

const cache = new LRUCache<string, User>({ max: 500, ttl: 1000 * 60 * 5 });
```

### Memory leak prevention

Unbounded `Map` as cache is a memory leak. Always use LRU or TTL-bounded cache. Always clean up event listeners (return a cleanup function from subscribe).

</details>

---

## 12. Profiling

<details>
<summary>12. Profiling</summary>

### Flame graphs

```bash
npx @platformatic/flame app.ts
npx @platformatic/flame --output markdown app.ts  # for AI-assisted analysis
```

### HTTP benchmarking

```bash
npx autocannon -c 100 -d 30 -p 10 http://localhost:3000
```

| Tool | Best for |
|------|----------|
| @platformatic/flame | CPU profiling, flame graphs, AI-assisted analysis |
| autocannon | Quick HTTP benchmarks, Node.js native |
| wrk | Maximum throughput testing |
| k6 | Complex scenarios, CI/CD integration, scripted tests |

### Workflow

1. Establish baseline with autocannon
2. Profile with @platformatic/flame to identify hotspots
3. Fix bottlenecks
4. Re-benchmark to verify improvement

### Built-in diagnostics

```bash
node --prof app.js && node --prof-process isolate-*.log > profile.txt
node --inspect app.js  # then Chrome DevTools at chrome://inspect
node --report-on-signal app.js  # SIGUSR2 triggers diagnostic report
```

</details>

---

## 13. Performance

<details>
<summary>13. Performance</summary>

### Don't block the event loop

CPU-intensive work goes to worker threads. Use [piscina](https://github.com/piscinajs/piscina):

```typescript
import Piscina from 'piscina';

const piscina = new Piscina({
  filename: new URL('./worker.ts', import.meta.url).href,
});

const result = await piscina.run({ input: 'data' });
```

### Connection pooling

Always pool database connections:

```typescript
const pool = new Pool({ max: 20, idleTimeoutMillis: 30000, connectionTimeoutMillis: 2000 });

async function query<T>(sql: string, params: unknown[]): Promise<T[]> {
  const client = await pool.connect();
  try {
    return (await client.query(sql, params)).rows;
  } finally {
    client.release();
  }
}
```

### Lazy loading

```typescript
let heavyModule: HeavyModule | null = null;

async function getHeavyModule(): Promise<HeavyModule> {
  if (!heavyModule) {
    const { HeavyModule } = await import('./heavy-module.js');
    heavyModule = new HeavyModule();
  }
  return heavyModule;
}
```

</details>

---

## 14. node_modules Navigation

<details>
<summary>14. node_modules Navigation</summary>

### Finding versions and entry points

```bash
cat node_modules/fastify/package.json | grep '"version"'
node -e "console.log(require.resolve('fastify'))"
```

### Finding READMEs

Don't use `find` or `grep`. Direct-read in order:
1. `node_modules/[package]/README.md`
2. `node_modules/[package]/readme.md`
3. List directory if neither exists

### pnpm vs npm layout

npm/yarn hoists dependencies flat. pnpm uses `.pnpm/` with symlinks - packages resolve only their declared dependencies.

### Dependency analysis

```bash
npm why lodash     # why is this installed?
npm ls --all       # full tree
npm ls --prod      # production only
```

</details>

---

## AI Anti-Patterns for Node.js

<details>
<summary>AI Anti-Patterns for Node.js</summary>

Patterns Claude Code tends to produce that are wrong or suboptimal:

1. **Installing ts-node or tsx** - Node 22.6+ runs .ts files directly. No runtime transpiler needed.
2. **Using enums** - breaks type stripping. Use `as const` objects.
3. **`__dirname` / `__filename`** - use `import.meta.dirname` / `import.meta.filename`.
4. **`.pipe()` for streams** - use `pipeline` from `node:stream/promises`.
5. **`process.on('uncaughtException')`** - use `close-with-grace`.
6. **Jest/Vitest for server-side tests** - `node:test` is built in and sufficient.
7. **Unbounded `Map` as cache** - use LRU or TTL-bounded cache.
8. **`NODE_ENV` checks** - use explicit env vars per concern.
9. **Missing file extensions in ESM imports** - always include `.ts`.
10. **Default exports** - use named exports.

</details>
