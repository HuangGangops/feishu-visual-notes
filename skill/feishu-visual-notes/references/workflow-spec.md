# Workflow Audit Specification

Use these machine-readable records to prove that key points, diagram choices, and long-source coverage were checked before writing.

## Highlight Inventory

Create one JSON item for every distinct point that should be highlighted. `highlight` must match the exact phrase marked in the XML. Set `required` to `false` only for an explicitly optional point.

```json
{
  "key_points": [
    {
      "section": "评测流程",
      "source": "先明确评测目标，再构建评测集",
      "highlight": "明确评测目标",
      "required": true
    }
  ]
}
```

Audit it before writing:

```powershell
python scripts/audit_highlight_coverage.py --content notes.xml --inventory highlights.json --strict
```

The strict audit rejects missing required highlights, repeated highlights, duplicate inventory items, and highlighted phrases not listed in the inventory.

## Diagram Candidate Score

Describe the relationship with explicit semantic signals instead of selecting a diagram from isolated keywords.

```json
{
  "question": "业务方和评测方如何交接？",
  "signals": ["roles", "handoffs", "ordered_steps"]
}
```

Supported signals:

| Signal | Typical result |
|-|-|
| `ordered_steps` | flow |
| `iteration` | loop flow |
| `roles`, `handoffs` | swimlane |
| `progressive_narrowing` | funnel |
| `two_axes` | quadrant |
| `root_causes` | cause-effect |
| `conditional_paths` | decision |
| `comparison_dimensions` | matrix |
| `chronology` | timeline |
| `hierarchy`, `central_topic` | knowledge map |
| `text_sufficient` | reject diagram and use prose |
| `table_sufficient` | reject diagram and use a table |

```powershell
python scripts/score_diagram_candidates.py --input diagram-choice.json
```

Use the ranking as a decision check, then confirm the top result actually answers the documented comprehension question.

## Long-Source Batch Manifest

Use a batch manifest for sources with more than 40 pages/images, or whenever the full source cannot be reviewed reliably in one pass.

```json
{
  "total_pages": 100,
  "batches": [
    {"id": "001", "start": 1, "end": 20, "status": "complete", "output": "batch-001.json"},
    {"id": "002", "start": 21, "end": 40, "status": "complete", "output": "batch-002.json"}
  ],
  "uncertain_pages": [7],
  "important_visual_pages": [12, 35],
  "original_resolution_pages": [7, 12, 35],
  "duplicates": [
    {"pages": [18, 44], "canonical": 18}
  ]
}
```

Each batch output must preserve page numbers and contain OCR text, uncertainty markers, and important visual observations for its range. Do not merge batches or build the final framework until this command passes:

```powershell
python scripts/audit_batch_manifest.py --input manifest.json --strict
```

## Update Snapshot

`python scripts/invoke_feishu_update.py --commit` automatically saves the exact expected revision before writing. Windows may use the equivalent `invoke-feishu-update.ps1` entry. The default directory is `.feishu-backups`; override it with a relative backup directory when needed. A snapshot contains the document ID, revision, source URL, UTC timestamp, and complete XML.

Snapshots are evidence and recovery inputs. Do not automatically overwrite the current document from a snapshot; inspect the current revision and obtain user approval before any restore operation.
