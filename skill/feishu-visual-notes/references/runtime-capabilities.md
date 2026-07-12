# Runtime Capability Report

Read this reference during the first-use capability gate. Inspect the tools actually exposed by the host runtime; do not infer support from a connector, MCP server, or plugin name.

Write a temporary UTF-8 JSON file only when runtime capabilities can be verified:

```json
{
  "feishu_mcp": {
    "available": true,
    "capabilities": ["document-read", "document-write", "editable-whiteboard"]
  },
  "plugins": [
    {"name": "example", "installed": true, "verified": false}
  ]
}
```

Use only these Feishu capability labels:

- `document-read`: resolve wiki links and fetch complete document content.
- `document-write`: create documents and perform revision-aware block updates.
- `editable-whiteboard`: create, query, and update native editable whiteboards rather than image attachments.

An MCP backend is complete only when all three labels were verified from callable tools. If one is missing, keep the MCP status as partial and use the tested CLI backend after the user completes its setup. Delete the temporary report after preflight unless the user explicitly wants to keep diagnostic output.
