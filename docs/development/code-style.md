# Code Style

## Python

### General
- **Python 3.11+** — use modern syntax (match/case, type unions with `|`)
- **Imports**: stdlib → third-party → local, separated by blank lines
- **Line length**: 120 characters max
- **Naming**: `snake_case` for functions/variables, `PascalCase` for classes, `UPPER_CASE` for constants

### Docstrings (Google format)

```python
def create_bubble(title: str, parent_id: str = None) -> Dict[str, Any]:
    """Create a new bubble in the workspace.

    Args:
        title: Name of the bubble to create.
        parent_id: Optional parent bubble ID for nesting.

    Returns:
        Dict with 'success' (bool), 'message' (str), and 'bubble' data.

    Raises:
        ValueError: If title is empty.
    """
```

### Type Hints

```python
from typing import Dict, List, Optional, Any

def find_ideas(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    ...
```

### Tool Function Pattern

```python
def my_tool(param1: str, param2: int = 0) -> Dict[str, Any]:
    """Short description.

    Args:
        param1: What this is.
        param2: What this is (default: 0).

    Returns:
        Standard tool result dict.
    """
    try:
        # Do work
        result = ...

        # Broadcast to UI if needed
        _broadcast_to_electron({"type": "node_added", "node": {...}})

        return {"success": True, "message": "Done", "data": result}
    except Exception as e:
        return {"success": False, "message": f"Error: {str(e)}"}
```

## JavaScript

### General
- **ES6+** syntax — `const`/`let`, arrow functions, template literals
- **No TypeScript** — plain JS throughout
- Use JSDoc for exported functions

### JSDoc

```javascript
/**
 * Add a bubble node to the 3D scene.
 * @param {Object} nodeData - Node data from Python backend
 * @param {string} nodeData.id - Unique node identifier
 * @param {string} nodeData.title - Display title
 * @param {number} nodeData.x - X position
 * @param {number} nodeData.y - Y position
 */
function addBubbleNode(nodeData) {
    // ...
}
```

## Commit Messages

```
<type>: <short description>

<optional body explaining why>
```

Types: `add`, `fix`, `update`, `refactor`, `docs`, `test`, `build`
