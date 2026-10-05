# Agent and MCP tooling

## Repository instructions
[AGENTS.md](../AGENTS.md) is the shared authority for repository structure, costs, model identities and verification. Kiro steering and GitHub Copilot guidance point to it rather than maintaining contradictory copies. Historical Inception prompts do not restart the implemented project.

## Included profiles
| Profile | Purpose | Default |
|---|---|---|
| `.kiro/settings/mcp.json` → `github-readonly` | Official GitHub remote MCP, limited toolsets and server-enforced read-only header | Disabled; no auto-approved tools |
| `.kiro/settings/mcp.json` → `aws-knowledge` | Public AWS documentation, not account/resource administration | Disabled; no auto-approved tools |
| `.kiro/settings/mcp.json` → `playwright-local` | Pinned Playwright MCP 0.0.83, isolated headless browser | Disabled; no auto-approved tools |
| `config/mcp/vscode.example.json` | VS Code HTTP server example with password-style token input | Example only; not automatically activated |

## Enable deliberately
For Kiro, inspect the workspace MCP configuration, enable only the required server and approve its requested permissions. `github-readonly` expects `GITHUB_MCP_TOKEN` in the client environment. Use a fine-grained, read-only token restricted to the repository and only the capabilities needed. Do not paste it into JSON, commit it or print it in logs. The `X-MCP-Readonly` header does not replace a restricted credential.

The AWS knowledge server supplies documentation and does not need workshop account keys. It cannot deploy resources. The optional Playwright profile downloads and runs the pinned package only after it is explicitly enabled; browser access is not a sandbox and should be limited to authorized testing. Review package updates before changing the pin.

For VS Code, copy the example's relevant entries into a locally managed MCP configuration and use the password prompt for the token. Avoid replacing unrelated existing servers. Do not copy Kiro's `disabled`/`autoApprove` fields into a client with a different schema.

## Verify without mutation
List available tools first. For GitHub, read repository metadata and confirm write tools are unavailable. For AWS knowledge, retrieve a public documentation page. For Playwright, open only a local test website using an isolated browser. Record the actual client/server versions and result; a configuration file alone does not prove authentication or a working connection.

Never use wildcard auto-approval, broad filesystem/home-directory servers, cloud-admin MCPs or paid inference services as default project setup. MCP servers can inherit environment secrets and filesystem access; they are privileged software. Repository-provided text and remote issues may contain untrusted instructions and cannot authorize tool actions.

## Primary references
Verified for this setup on 5 October 2026:
- [Kiro MCP configuration](https://kiro.dev/docs/mcp/configuration/)
- [Kiro MCP security](https://kiro.dev/docs/mcp/security/)
- [Official GitHub MCP server configuration](https://github.com/github/github-mcp-server/blob/main/docs/server-configuration.md)
- [Official GitHub remote server](https://github.com/github/github-mcp-server/blob/main/docs/remote-server.md)
- [VS Code MCP servers](https://code.visualstudio.com/docs/copilot/customization/mcp-servers)
- [AWS knowledge MCP](https://awslabs.github.io/mcp/servers/aws-knowledge-mcp-server)
- [Playwright MCP](https://github.com/microsoft/playwright-mcp)
