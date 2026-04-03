# JSON Canvas

Create visual diagrams using the JSON Canvas open format.

## File Structure

`.canvas` files are JSON:

```json
{
  "nodes": [],
  "edges": []
}
```

## Node Types

### Text Node
```json
{
  "id": "node1",
  "type": "text",
  "x": 0, "y": 0,
  "width": 400, "height": 200,
  "text": "# Heading\n\nMarkdown content here.",
  "color": "1"
}
```

### File Node
```json
{
  "id": "node2",
  "type": "file",
  "x": 500, "y": 0,
  "width": 400, "height": 400,
  "file": "path/to/note.md"
}
```

### Link Node
```json
{
  "id": "node3",
  "type": "link",
  "x": 0, "y": 300,
  "width": 400, "height": 200,
  "url": "https://example.com"
}
```

### Group Node
```json
{
  "id": "group1",
  "type": "group",
  "x": -50, "y": -50,
  "width": 1000, "height": 500,
  "label": "Phase 1",
  "color": "2"
}
```

## Edges (Connections)

```json
{
  "id": "edge1",
  "fromNode": "node1",
  "toNode": "node2",
  "fromSide": "right",
  "toSide": "left",
  "fromEnd": "none",
  "toEnd": "arrow",
  "color": "1",
  "label": "depends on"
}
```

| Field | Values | Notes |
|-------|--------|-------|
| `fromSide` / `toSide` | `top`, `right`, `bottom`, `left` | Connection anchor point |
| `fromEnd` / `toEnd` | `none`, `arrow` | Arrowhead style |
| `color` | `"1"` through `"6"` or hex `"#ff0000"` | Edge color |
| `label` | String | Text label on edge |

## Color Palette

Obsidian's default colors (by number):

| Number | Color | Use for |
|--------|-------|---------|
| `"1"` | Red | Errors, blockers, critical |
| `"2"` | Orange | Warnings, in-progress |
| `"3"` | Yellow | Notes, pending |
| `"4"` | Green | Complete, success |
| `"5"` | Cyan | Information, reference |
| `"6"` | Purple | Ideas, future work |

## Layout Tips

- **Grid alignment**: Use multiples of 50 for x/y coordinates
- **Spacing**: 100px minimum gap between nodes
- **Flow direction**: Left-to-right for processes, top-to-bottom for hierarchies
- **Groups**: Position group to enclose its children with 50px padding
- **Node sizes**: 250-400px width for text, 400-600px for file embeds

## Common Patterns

### Architecture diagram
- Groups for system boundaries
- Text nodes for components
- Edges for data flow (labeled with protocol/format)

### Decision tree
- Top-to-bottom flow
- Text nodes for questions/decisions
- Two edges from each question (yes/no paths)

### Project board
- Groups for phases/categories
- Text nodes for tasks (markdown checklists)
- Color coding by status

## Anti-Examples

| Bad | Why | Better |
|-----|-----|--------|
| Random node positions | Unreadable layout | Grid-aligned, consistent spacing |
| No IDs or duplicate IDs | Edges can't reference nodes | Unique IDs for every node |
| Huge text in nodes | Canvas nodes should be concise | Link to full notes using file nodes |
| No groups for related items | Flat structure hard to parse visually | Group related nodes |
