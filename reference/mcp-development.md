<!-- keywords: mcp, model context protocol, mcp server, tool registration, resource registration, mcp tool, mcp transport, mcp app -->
# MCP Development Reference

Reference for building MCP (Model Context Protocol) servers and apps.

**Source**: Official spec (version 2025-06-18), TypeScript SDK docs, workshop patterns.

## Quick Nav

| Section | Jump to | When |
|---------|---------|------|
| Architecture | [Architecture](#architecture) | Understanding host/client/server model |
| Primitives | [Three Primitives](#the-three-primitives) | Choosing tools vs resources vs prompts |
| TypeScript Server | [Server Setup](#typescript-server-setup) | Starting a new MCP server |
| Tools | [Tool Registration](#tool-registration) | Adding callable actions |
| Resources | [Resource Registration](#resource-registration) | Exposing data for context |
| Prompts | [Prompt Registration](#prompt-registration) | Creating reusable templates |
| MCP Apps | [MCP Apps](#mcp-apps) | Building interactive HTML UIs in chat |
| Transports | [Transport Types](#transport-types) | stdio vs HTTP, when to use which |
| Claude Desktop | [Claude Desktop Config](#claude-desktop-config) | Connecting server to Claude Desktop |
| Testing | [Testing & Inspector](#testing--inspector) | Debugging MCP servers |
| Security | [Security Model](#security-model) | Trust boundaries, auth, gotchas |
| Ecosystem | [SDKs & Hosts](#sdks--hosts) | Available SDKs and supporting clients |
| Gotchas | [Common Gotchas](#common-gotchas) | Things that will bite you |

---

## Architecture

<details>
<summary>Architecture</summary>

```
Host (Claude Desktop)  -->  Client (built-in)  -->  Server (your code)
```

- **Host**: AI application (Claude Desktop, Cursor, VS Code, etc.). Trust anchor. Controls what servers connect, what they can do.
- **Client**: Component inside the host. One client per server connection. Manages the JSON-RPC session.
- **Server**: Your code. Exposes tools/resources/prompts. Local (stdio subprocess) or remote (HTTP).

**Connection lifecycle**:
1. Client sends `initialize` with `protocolVersion` + `capabilities`
2. Server responds with its capabilities
3. Client sends `notifications/initialized`
4. Normal operation (JSON-RPC 2.0 messages)
5. Terminated by closing stdin (stdio) or HTTP DELETE (Streamable HTTP)

**Wire format**: JSON-RPC 2.0, UTF-8 encoded. Three message types: requests (have `id`), responses (match `id`), notifications (no `id`, fire-and-forget).

</details>

## The Three Primitives

<details>
<summary>The Three Primitives</summary>

| Primitive | Controlled by | Direction | Analogy | Use when |
|-----------|--------------|-----------|---------|----------|
| **Tools** | LLM | Client -> Server | POST endpoint | LLM should take an action (write, query, call API) |
| **Resources** | Application | Client -> Server | GET endpoint | Provide data/context for LLM to reason about |
| **Prompts** | User | User-initiated | Saved template | Pre-built conversation starter or workflow |

**Tools** = actions with side effects. LLM discovers them and decides when to call.
**Resources** = read-only data. Host/app decides what to include as context. Identified by URI.
**Prompts** = reusable message templates. User explicitly selects (typically via slash command UI).

### Decision matrix

- LLM decides when to use it -> **Tool**
- User explicitly selects it -> **Prompt**
- App automatically includes context -> **Resource**
- Has side effects -> **Tool**
- Read-only data -> **Resource**
- Returns pre-built messages -> **Prompt**

</details>

## TypeScript Server Setup

<details>
<summary>TypeScript Server Setup</summary>

### Dependencies

```bash
npm install @modelcontextprotocol/sdk zod
npm install -D typescript @types/node
# For MCP Apps (Step 5):
npm install @modelcontextprotocol/ext-apps express cors
npm install -D @types/express @types/cors vite vite-plugin-singlefile
```

### Minimal server

```typescript
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const server = new McpServer({
  name: "my-server",
  version: "1.0.0",
});

// Register tools, resources, prompts here...

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("Server running on stdio");
}

main().catch(console.error);
```

### tsconfig.json

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "Node16",
    "moduleResolution": "Node16",
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true
  },
  "include": ["src/**/*"]
}
```

### package.json essentials

```json
{
  "type": "module",
  "scripts": {
    "build": "tsc",
    "start": "node dist/index.js"
  }
}
```

</details>

## Tool Registration

<details>
<summary>Tool Registration</summary>

### API

```typescript
// Short form (deprecated but works)
server.tool(name, description, zodSchema, handler);

// Preferred form
server.registerTool(name, config, handler);
```

### Examples

```typescript
// Simple tool
server.tool(
  "hello",
  "Say hello to someone",
  { name: z.string() },
  async ({ name }) => ({
    content: [{ type: "text", text: `Hello, ${name}!` }],
  })
);

// Tool with multiple params
server.tool(
  "add_todo",
  "Add a new todo item",
  { title: z.string().describe("The title of the todo item") },
  async ({ title }) => {
    const todo = createTodo(title);
    return {
      content: [{ type: "text", text: `Added todo #${todo.id}: "${todo.title}"` }],
    };
  }
);

// No-parameter tool
server.tool("list_todos", "List all todo items", {}, async () => ({
  content: [{ type: "text", text: formatTodos() }],
}));
```

### Return format

Always return `{ content: ContentItem[] }`. Content types:
- `{ type: "text", text: "..." }` - most common
- `{ type: "image", data: "base64...", mimeType: "image/png" }`
- `{ type: "resource_link", uri: "...", name: "...", mimeType: "..." }`

### Error handling

Return error as text content, don't throw:

```typescript
const todo = todos.find(t => t.id === id);
if (!todo) {
  return { content: [{ type: "text", text: `Todo #${id} not found.` }] };
}
```

### Schema notes

- Pass plain Zod object `{ key: z.string() }`, NOT `z.object({ ... })`
- Use `.describe()` on fields - the LLM sees this text to understand parameters
- The registered tool object has `.enable()`, `.disable()`, `.update()`, `.remove()` for runtime changes

</details>

## Resource Registration

<details>
<summary>Resource Registration</summary>

### API

```typescript
server.resource(name, uri, metadata, handler);
server.resource(name, resourceTemplate, metadata, handler);
```

### Static resource

```typescript
server.resource(
  "todo-list",
  "todo://list",
  { description: "A JSON list of all current todos" },
  async (uri) => ({
    contents: [{
      uri: uri.href,
      mimeType: "application/json",
      text: JSON.stringify(todos, null, 2),
    }],
  })
);
```

### Dynamic resource with URI template

```typescript
import { ResourceTemplate } from "@modelcontextprotocol/sdk/server/mcp.js";

server.resource(
  "items",
  new ResourceTemplate("items://{id}", {
    list: async () => ({
      resources: [{ uri: "items://1", name: "Item 1" }],
    }),
    complete: {
      id: (value) => ["1", "2", "3"].filter(v => v.startsWith(value)),
    },
  }),
  { mimeType: "application/json" },
  async (uri, { id }) => ({
    contents: [{ uri: uri.href, text: JSON.stringify(getItem(id)) }],
  })
);
```

### Key details

- URI schemes are arbitrary (`todo://`, `ui://`, custom)
- Handler returns `{ contents: [{ uri, text, mimeType }] }`
- Binary content uses `blob` field (base64) instead of `text`
- Resources support subscriptions for change notifications (if server declares `subscribe: true`)

</details>

## Prompt Registration

<details>
<summary>Prompt Registration</summary>

### API

```typescript
server.prompt(name, description, zodSchema, handler);
```

### Example

```typescript
server.prompt(
  "plan-tasks",
  "Create an action plan based on a goal and current todos",
  { goal: z.string().describe("The goal you want to achieve") },
  async ({ goal }) => {
    const todoSummary = todos.length === 0
      ? "No todos yet."
      : todos.map(t => `- ${t.completed ? "[done]" : "[pending]"} #${t.id}: ${t.title}`).join("\n");

    return {
      messages: [
        {
          role: "user" as const,
          content: {
            type: "text" as const,
            text: `Current todos:\n\n${todoSummary}\n\nGoal: ${goal}\n\nCreate an action plan.`,
          },
        },
      ],
    };
  }
);
```

### Key details

- Returns `{ messages: PromptMessage[] }` - an array of role/content pairs
- `role`: `"user"` or `"assistant"` (both valid, for few-shot patterns)
- `as const` on `role` and `type` required for TypeScript literal type checks
- Prompts can include dynamic context (current data state) + structured instructions
- Users select prompts in Claude UI and fill in parameters

</details>

## MCP Apps

<details>
<summary>MCP Apps</summary>

MCP Apps render interactive HTML UIs inside the chat. Extension to core MCP, supported by Claude Desktop, claude.ai, VS Code GitHub Copilot, and others.

### How it works

1. A tool declares `_meta.ui.resourceUri` pointing to a `ui://` resource
2. Host fetches the UI resource (bundled HTML file)
3. Host renders it in a sandboxed iframe
4. App and host communicate via JSON-RPC over `postMessage`

### Communication flow

```
User clicks UI
  -> app.callServerTool()
  -> postMessage to Host
  -> Host calls server MCP tool (HTTP POST /mcp)
  -> Server processes, returns result
  -> Host sends back via postMessage
  -> App receives, updates DOM
```

### Server side

```typescript
import { registerAppTool, registerAppResource, RESOURCE_MIME_TYPE }
  from "@modelcontextprotocol/ext-apps/server";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const resourceUri = "ui://todo-app/todo-app.html";

// Register the tool that launches the UI
registerAppTool(server, "show_todos", {
  title: "Show Todos",
  description: "Interactive todo list dashboard",
  inputSchema: {},
  _meta: { ui: { resourceUri } },
}, async () => ({
  content: [{ type: "text", text: JSON.stringify(todos) }],
}));

// Register the UI resource (serves the bundled HTML)
registerAppResource(server, resourceUri, resourceUri,
  { mimeType: RESOURCE_MIME_TYPE },
  async () => {
    const html = await fs.readFile(path.join(__dirname, "ui", "todo-app.html"), "utf-8");
    return { contents: [{ uri: resourceUri, mimeType: RESOURCE_MIME_TYPE, text: html }] };
  }
);
```

### UI side (bundled into single HTML)

```typescript
import { App } from "@modelcontextprotocol/ext-apps";

const app = new App({ name: "Todo App", version: "1.0.0" });
app.connect();

// Receive initial tool result when UI renders
app.ontoolresult = (result) => {
  const text = result.content?.find((c: any) => c.type === "text")?.text;
  if (text) renderTodos(JSON.parse(text));
};

// Call server tools from UI interactions
async function addTodo(title: string) {
  await app.callServerTool({ name: "add_todo", arguments: { title } });
  await refreshTodos();
}

async function refreshTodos() {
  const result = await app.callServerTool({ name: "show_todos", arguments: {} });
  const text = result.content?.find((c: any) => c.type === "text")?.text;
  if (text) renderTodos(JSON.parse(text));
}
```

### Build setup

MCP Apps require Vite + `vite-plugin-singlefile` to bundle HTML/CSS/JS into one file (iframe CSP blocks external asset loads).

```typescript
// vite.config.ts
import { defineConfig } from "vite";
import { viteSingleFile } from "vite-plugin-singlefile";

export default defineConfig({
  plugins: [viteSingleFile()],
  build: {
    outDir: "dist",
    emptyOutDir: false,
    rollupOptions: { input: process.env.INPUT },
  },
});
```

```json
// package.json scripts
{
  "build:ui": "INPUT=ui/todo-app.html vite build",
  "build:app": "tsc && INPUT=ui/todo-app.html vite build"
}
```

### When to use Apps vs plain tools

- **Apps**: complex data exploration, multi-option forms, rich media, real-time dashboards, multi-step workflows
- **Plain tools**: LLM just needs text/structured result to reason about

</details>

## Transport Types

<details>
<summary>Transport Types</summary>

### stdio (local)

```typescript
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
const transport = new StdioServerTransport();
await server.connect(transport);
```

- Client launches server as subprocess
- JSON-RPC over stdin/stdout, logs on stderr
- No network overhead, single-client only
- Used by Claude Desktop for local servers
- **stdout is sacred** - only MCP messages, never `console.log()`

### Streamable HTTP (remote, current standard)

```typescript
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import express from "express";
import cors from "cors";

const app = express();
app.use(cors());
app.use(express.json());

app.post("/mcp", async (req, res) => {
  const transport = new StreamableHTTPServerTransport({
    sessionIdGenerator: undefined,  // stateless (new transport per request)
    enableJsonResponse: true,
  });
  res.on("close", () => transport.close());
  await server.connect(transport);
  await transport.handleRequest(req, res, req.body);
});

app.listen(3001);
```

- Required for MCP Apps (host needs to fetch `ui://` resources over HTTP)
- Supports JSON responses or SSE streams
- Stateless (`sessionIdGenerator: undefined`) or stateful (pass UUID generator)
- Multi-client capable
- Replaces deprecated HTTP+SSE transport

### Comparison

| Aspect | stdio | Streamable HTTP |
|--------|-------|-----------------|
| Process model | Subprocess | Long-running HTTP server |
| Clients | Single | Multiple |
| MCP Apps | No | Yes (required) |
| Network | None | HTTP |
| Auth | Env vars | OAuth 2.1 (optional) |
| Config | `claude_desktop_config.json` | Custom connector URL |

</details>

## Claude Desktop Config

<details>
<summary>Claude Desktop Config</summary>

**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "my-server": {
      "command": "node",
      "args": ["C:/absolute/path/to/dist/index.js"],
      "env": { "API_KEY": "value" }
    }
  }
}
```

- Path must be absolute
- JSON does not allow trailing commas
- Fully quit and restart Claude Desktop after changes (tray icon -> Quit)
- Check Settings > Developer for server status
- `env` is optional, passes environment variables to the subprocess

</details>

## Testing & Inspector

<details>
<summary>Testing & Inspector</summary>

### MCP Inspector

```bash
# Test compiled server
npx @modelcontextprotocol/inspector node dist/index.js

# Test without compiling (via tsx)
npx @modelcontextprotocol/inspector npx tsx src/index.ts

# Test HTTP server
# Start server first, then connect via Inspector UI at http://localhost:6274
```

Inspector UI at `http://localhost:6274` (proxy at 6277). Lets you:
- Browse registered tools, resources, prompts
- Execute tools with custom inputs
- Test resource reads
- Preview prompt message generation
- View raw JSON-RPC messages

### Manual testing in Claude Desktop

1. Build: `npm run build`
2. Restart Claude Desktop
3. Check Settings > Developer for server status
4. Ask Claude to use a tool by name

</details>

## Security Model

<details>
<summary>Security Model</summary>

### Trust hierarchy

Host is the trust anchor. Servers are untrusted third parties.

- Tool annotations from servers are untrusted unless server itself is trusted
- Host must show users which tools are exposed
- Host should show tool inputs before calling (prevents data exfiltration)
- Human-in-the-loop strongly recommended for tool invocations

### HTTP auth (when implemented)

OAuth 2.1 with PKCE (mandatory) + resource parameter (RFC 8707, audience binding).

Critical requirements:
- PKCE mandatory (prevents auth code interception)
- `resource` parameter required (binds token to specific server)
- Token passthrough forbidden (server must NOT relay client tokens upstream)
- Validate `Origin` header on Streamable HTTP (prevents DNS rebinding)
- Local servers bind to `127.0.0.1`, not `0.0.0.0`

### stdio auth

Credentials via environment variables in the config, not OAuth.

</details>

## SDKs & Hosts

<details>
<summary>SDKs & Hosts</summary>

### Official SDKs

| SDK | Tier | Notes |
|-----|------|-------|
| TypeScript | 1 | Full support |
| Python | 1 | Full support |
| C# | 1 | Full support |
| Go | 1 | Full support |
| Java | 2 | Substantial |
| Rust | 2 | Substantial |
| Swift | 3 | Community |
| Ruby | 3 | Community |
| PHP | 3 | Community |

### Major hosts

| Host | Key primitives |
|------|---------------|
| Claude.ai | Resources, Prompts, Tools, Apps |
| Claude Desktop | Resources, Prompts, Tools, Roots, Apps |
| Claude Code | Resources, Prompts, Tools, Roots, Elicitation |
| ChatGPT | Tools, Apps |
| Cursor | Prompts, Tools, Roots, Elicitation |
| VS Code Copilot | Apps |
| Gemini CLI | Prompts, Tools |
| Codex (OpenAI) | Resources, Tools, Elicitation |

</details>

## Common Gotchas

<details>
<summary>Common Gotchas</summary>

1. **`console.log` kills stdio servers.** Stdout is the MCP wire. Use `console.error()` for all logging.

2. **`.js` extensions in imports.** SDK uses ES modules with `"module": "Node16"`. Import paths must use `.js`:
   ```typescript
   import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
   ```

3. **Zod shape format.** Pass plain object `{ key: z.string() }`, NOT `z.object({ ... })`. SDK wraps internally.

4. **`__dirname` in ESM.** Not available. Use:
   ```typescript
   const __dirname = path.dirname(fileURLToPath(import.meta.url));
   ```

5. **`tool()` is deprecated.** Still works, but `registerTool()` is preferred. Same for `resource()` and `prompt()`.

6. **`as const` on prompt returns.** TypeScript needs literal types:
   ```typescript
   role: "user" as const,
   type: "text" as const,
   ```

7. **MCP Apps need HTTP transport.** stdio servers can't serve `ui://` resources. Switch to `StreamableHTTPServerTransport` + Express.

8. **Single-file bundling for Apps.** Iframe CSP blocks external loads. Use `vite-plugin-singlefile`.

9. **Stateless HTTP by default.** `sessionIdGenerator: undefined` creates new transport per request. Only add sessions if you need server-push SSE.

10. **Claude Desktop restart.** Config changes require full quit + reopen (not just close window).

</details>

## Server-to-Client Capabilities

<details>
<summary>Server-to-Client Capabilities</summary>

Servers can also request things from the client:

- **Sampling**: Ask client to run an LLM completion (`sampling/complete`). Stay model-agnostic without bundling an SDK.
- **Elicitation**: Request info from user (`elicitation/request`). Confirmation prompts, additional inputs.
- **Roots**: Client exposes filesystem boundary hints (which directories server can access).
- **Logging**: Server sends log messages to client for debugging.

</details>
