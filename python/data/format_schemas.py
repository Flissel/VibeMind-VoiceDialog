"""
JSON Schema definitions for structured idea formatting.

These schemas define the allowed structure for LLM-generated content
that gets stored in the content_json field of canvas_nodes.
"""

from typing import Dict, Any

# =============================================================================
# NOTE SCHEMA (DEFAULT)
# =============================================================================

NOTE_SCHEMA = {
    "type": "object",
    "description": "Simple plain text note - the default format for ideas",
    "properties": {
        "type": {"const": "note"},
        "title": {"type": "string", "description": "Note title"},
        "text": {"type": "string", "description": "Plain text content"},
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Optional tags for categorization"
        },
        "metadata": {
            "type": "object",
            "properties": {
                "source": {"enum": ["voice", "text", "converted"], "description": "How the note was created"},
                "original_format": {"type": "string", "description": "Previous format if converted"},
                "created_at": {"type": "string", "format": "date-time"},
                "formatted_by": {"type": "string", "description": "Agent that created/formatted this"}
            }
        }
    },
    "required": ["type", "text"]
}

# =============================================================================
# ACTION LIST SCHEMA
# =============================================================================

ACTION_LIST_SCHEMA = {
    "type": "object",
    "properties": {
        "type": {"const": "action_list"},
        "title": {"type": "string", "description": "Title of the action list"},
        "description": {"type": "string", "description": "Optional description"},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "Task description"},
                    "status": {
                        "enum": ["pending", "in_progress", "completed", "blocked"],
                        "default": "pending"
                    },
                    "priority": {
                        "enum": ["low", "medium", "high", "critical"],
                        "default": "medium"
                    },
                    "assignee": {"enum": ["Rachel"], "description": "VibeMind Agent (currently IDEAS only)"},
                    "space": {"const": "IDEAS", "description": "Target space"},
                    "action_type": {"enum": [
                        "bubble.create", "bubble.enter", "idea.create",
                        "idea.expand", "idea.connect", "idea.auto_link"
                    ], "description": "VibeMind action type"},
                    "due_date": {"type": "string", "format": "date", "description": "ISO date string"},
                    "notes": {"type": "string", "description": "Additional notes"}
                },
                "required": ["task"]
            }
        },
        "metadata": {
            "type": "object",
            "properties": {
                "created_by": {"type": "string"},
                "last_updated": {"type": "string", "format": "date-time"},
                "version": {"type": "integer", "default": 1}
            }
        }
    },
    "required": ["type", "items"]
}

# =============================================================================
# PROS AND CONS TABLE SCHEMA
# =============================================================================

PROS_CONS_TABLE_SCHEMA = {
    "type": "object",
    "properties": {
        "type": {"const": "pros_cons_table"},
        "title": {"type": "string", "description": "Title of the analysis"},
        "topic": {"type": "string", "description": "What is being analyzed"},
        "pros": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "point": {"type": "string", "description": "Advantage point"},
                    "weight": {"type": "integer", "minimum": 1, "maximum": 5, "default": 3},
                    "evidence": {"type": "string", "description": "Supporting evidence"}
                },
                "required": ["point"]
            }
        },
        "cons": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "point": {"type": "string", "description": "Disadvantage point"},
                    "weight": {"type": "integer", "minimum": 1, "maximum": 5, "default": 3},
                    "evidence": {"type": "string", "description": "Supporting evidence"},
                    "mitigation": {"type": "string", "description": "How to address this concern"}
                },
                "required": ["point"]
            }
        },
        "summary": {
            "type": "object",
            "properties": {
                "overall_rating": {"type": "integer", "minimum": 1, "maximum": 10},
                "recommendation": {"type": "string"},
                "key_decision_factors": {"type": "array", "items": {"type": "string"}}
            }
        }
    },
    "required": ["type", "pros", "cons"]
}

# =============================================================================
# TECHNICAL SPECIFICATIONS SCHEMA
# =============================================================================

TECHNICAL_SPECS_SCHEMA = {
    "type": "object",
    "properties": {
        "type": {"const": "technical_specs"},
        "title": {"type": "string", "description": "Title of the technical specification"},
        "component": {"type": "string", "description": "What component/system is being specified"},
        "specifications": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "e.g., Performance, Security, Scalability"},
                    "requirement": {"type": "string", "description": "Specific requirement"},
                    "priority": {"enum": ["must_have", "should_have", "nice_to_have"]},
                    "acceptance_criteria": {"type": "string", "description": "How to verify requirement"},
                    "estimated_effort": {"enum": ["low", "medium", "high", "unknown"]},
                    "dependencies": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["category", "requirement"]
            }
        },
        "architecture_decisions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "decision": {"type": "string"},
                    "alternatives": {"type": "array", "items": {"type": "string"}},
                    "rationale": {"type": "string"},
                    "consequences": {"type": "string"}
                }
            }
        },
        "implementation_notes": {"type": "string"}
    },
    "required": ["type", "specifications"]
}

# =============================================================================
# HIERARCHY SCHEMA
# =============================================================================

HIERARCHY_SCHEMA = {
    "type": "object",
    "properties": {
        "type": {"const": "hierarchy"},
        "title": {"type": "string", "description": "Title of the hierarchical structure"},
        "root_concept": {"type": "string", "description": "The main concept at the top"},
        "levels": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "level": {"type": "integer", "minimum": 1},
                    "name": {"type": "string", "description": "Name of this level"},
                    "description": {"type": "string"},
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "description": {"type": "string"},
                                "parent": {"type": "string", "description": "Reference to parent item"},
                                "children": {"type": "array", "items": {"type": "string"}}
                            },
                            "required": ["name"]
                        }
                    }
                },
                "required": ["level", "items"]
            }
        },
        "relationships": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "from": {"type": "string"},
                    "to": {"type": "string"},
                    "type": {"enum": ["parent_child", "related", "depends_on", "conflicts_with"]},
                    "strength": {"type": "integer", "minimum": 1, "maximum": 5}
                }
            }
        }
    },
    "required": ["type", "levels"]
}

# =============================================================================
# COMPARISON TABLE SCHEMA
# =============================================================================

COMPARISON_TABLE_SCHEMA = {
    "type": "object",
    "properties": {
        "type": {"const": "comparison_table"},
        "title": {"type": "string", "description": "Title of the comparison"},
        "criteria": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "weight": {"type": "integer", "minimum": 1, "maximum": 5, "default": 3},
                    "type": {"enum": ["qualitative", "quantitative", "boolean"]}
                },
                "required": ["name"]
            }
        },
        "options": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "scores": {
                        "type": "object",
                        "description": "Key-value pairs where key is criterion name, value is score"
                    },
                    "notes": {"type": "string"}
                },
                "required": ["name"]
            }
        },
        "recommendation": {
            "type": "object",
            "properties": {
                "best_option": {"type": "string"},
                "reasoning": {"type": "string"},
                "trade_offs": {"type": "array", "items": {"type": "string"}}
            }
        }
    },
    "required": ["type", "criteria", "options"]
}

# =============================================================================
# SIMPLE TABLE SCHEMA (Flexible columns)
# =============================================================================

SIMPLE_TABLE_SCHEMA = {
    "type": "object",
    "description": "A flexible table format that can have any column headers",
    "properties": {
        "type": {"const": "table"},
        "title": {"type": "string", "description": "Title of the table"},
        "headers": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Column headers (e.g., ['Calls ID', 'Requirement', 'Content'])",
            "minItems": 1
        },
        "rows": {
            "type": "array",
            "items": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Each row is an array of cell values"
            },
            "description": "Table data rows"
        },
        "metadata": {
            "type": "object",
            "properties": {
                "source_idea": {"type": "string", "description": "Original idea this was formatted from"},
                "created_at": {"type": "string", "format": "date-time"},
                "format_prompt": {"type": "string", "description": "User's formatting instruction"}
            }
        }
    },
    "required": ["type", "headers", "rows"]
}

# =============================================================================
# KANBAN SCHEMA (Figma-inspired)
# =============================================================================

KANBAN_SCHEMA = {
    "type": "object",
    "description": "Kanban board with columns and cards",
    "properties": {
        "type": {"const": "kanban"},
        "title": {"type": "string", "description": "Board title"},
        "columns": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Column name (e.g., Backlog, In Progress, Done)"},
                    "color": {"type": "string", "description": "Hex color for column header"},
                    "cards": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "description": {"type": "string"},
                                "priority": {"enum": ["low", "medium", "high", "critical"]},
                                "labels": {"type": "array", "items": {"type": "string"}}
                            },
                            "required": ["title"]
                        }
                    }
                },
                "required": ["name", "cards"]
            }
        },
        "metadata": {"type": "object"}
    },
    "required": ["type", "columns"]
}

# =============================================================================
# MINDMAP SCHEMA (Figma-inspired)
# =============================================================================

MINDMAP_SCHEMA = {
    "type": "object",
    "description": "Mind map with central concept and branches",
    "properties": {
        "type": {"const": "mindmap"},
        "title": {"type": "string", "description": "Mind map title"},
        "center": {
            "type": "object",
            "properties": {
                "label": {"type": "string", "description": "Central concept"},
                "description": {"type": "string"}
            },
            "required": ["label"]
        },
        "branches": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "color": {"type": "string", "description": "Hex color for branch"},
                    "children": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "label": {"type": "string"},
                                "description": {"type": "string"},
                                "children": {"type": "array", "items": {"type": "object"}}
                            },
                            "required": ["label"]
                        }
                    }
                },
                "required": ["label"]
            }
        },
        "metadata": {"type": "object"}
    },
    "required": ["type", "center", "branches"]
}

# =============================================================================
# SWOT SCHEMA (Figma-inspired)
# =============================================================================

SWOT_SCHEMA = {
    "type": "object",
    "description": "SWOT analysis (Strengths, Weaknesses, Opportunities, Threats)",
    "properties": {
        "type": {"const": "swot"},
        "title": {"type": "string"},
        "subject": {"type": "string", "description": "What is being analyzed"},
        "strengths": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "point": {"type": "string"},
                    "impact": {"enum": ["low", "medium", "high"]},
                    "evidence": {"type": "string"}
                },
                "required": ["point"]
            }
        },
        "weaknesses": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "point": {"type": "string"},
                    "impact": {"enum": ["low", "medium", "high"]},
                    "mitigation": {"type": "string"}
                },
                "required": ["point"]
            }
        },
        "opportunities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "point": {"type": "string"},
                    "likelihood": {"enum": ["low", "medium", "high"]},
                    "action": {"type": "string"}
                },
                "required": ["point"]
            }
        },
        "threats": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "point": {"type": "string"},
                    "likelihood": {"enum": ["low", "medium", "high"]},
                    "contingency": {"type": "string"}
                },
                "required": ["point"]
            }
        },
        "summary": {
            "type": "object",
            "properties": {
                "strategic_position": {"type": "string"},
                "key_actions": {"type": "array", "items": {"type": "string"}}
            }
        },
        "metadata": {"type": "object"}
    },
    "required": ["type", "strengths", "weaknesses", "opportunities", "threats"]
}

# =============================================================================
# USER STORY SCHEMA (Figma-inspired)
# =============================================================================

USER_STORY_SCHEMA = {
    "type": "object",
    "description": "User stories in agile format",
    "properties": {
        "type": {"const": "user_story"},
        "title": {"type": "string"},
        "epic": {"type": "string", "description": "Overarching theme"},
        "stories": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "e.g., US-001"},
                    "role": {"type": "string", "description": "Als [Rolle]"},
                    "want": {"type": "string", "description": "moechte ich [Feature]"},
                    "benefit": {"type": "string", "description": "damit [Nutzen]"},
                    "acceptance_criteria": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "priority": {"enum": ["must_have", "should_have", "could_have", "wont_have"]},
                    "story_points": {"type": "integer", "enum": [1, 2, 3, 5, 8, 13]}
                },
                "required": ["role", "want", "benefit"]
            }
        },
        "personas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "role": {"type": "string"},
                    "goals": {"type": "array", "items": {"type": "string"}}
                }
            }
        },
        "metadata": {"type": "object"}
    },
    "required": ["type", "stories"]
}

# =============================================================================
# FLOWCHART SCHEMA (Figma-inspired)
# =============================================================================

FLOWCHART_SCHEMA = {
    "type": "object",
    "description": "Flowchart with process steps and decisions",
    "properties": {
        "type": {"const": "flowchart"},
        "title": {"type": "string"},
        "description": {"type": "string"},
        "nodes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "type": {"enum": ["start", "end", "process", "decision", "subprocess"]},
                    "label": {"type": "string"},
                    "description": {"type": "string"},
                    "condition": {"type": "string", "description": "For decision nodes"}
                },
                "required": ["id", "type", "label"]
            }
        },
        "edges": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "from": {"type": "string", "description": "Source node ID"},
                    "to": {"type": "string", "description": "Target node ID"},
                    "label": {"type": "string", "description": "Edge label (e.g., Yes/No)"}
                },
                "required": ["from", "to"]
            }
        },
        "metadata": {"type": "object"}
    },
    "required": ["type", "nodes", "edges"]
}

# =============================================================================
# SCHEMA REGISTRY
# =============================================================================

# All available format schemas
FORMAT_SCHEMAS = {
    "note": NOTE_SCHEMA,  # DEFAULT format
    "table": SIMPLE_TABLE_SCHEMA,  # Alias for simple_table
    "action_list": ACTION_LIST_SCHEMA,
    "pros_cons": PROS_CONS_TABLE_SCHEMA,  # Short alias
    "pros_cons_table": PROS_CONS_TABLE_SCHEMA,
    "technical_specs": TECHNICAL_SPECS_SCHEMA,
    "specs": TECHNICAL_SPECS_SCHEMA,  # Short alias
    "hierarchy": HIERARCHY_SCHEMA,
    "comparison_table": COMPARISON_TABLE_SCHEMA,
    "simple_table": SIMPLE_TABLE_SCHEMA,
    # Figma-inspired formats
    "kanban": KANBAN_SCHEMA,
    "mindmap": MINDMAP_SCHEMA,
    "mind_map": MINDMAP_SCHEMA,
    "swot": SWOT_SCHEMA,
    "user_story": USER_STORY_SCHEMA,
    "user_stories": USER_STORY_SCHEMA,
    "flowchart": FLOWCHART_SCHEMA,
}

# Default format type
DEFAULT_FORMAT = "note"

def get_format_schema(format_type: str) -> Dict[str, Any]:
    """
    Get the JSON schema for a specific format type.

    Args:
        format_type: The format type (e.g., "action_list", "pros_cons_table")

    Returns:
        JSON Schema dictionary

    Raises:
        ValueError: If format_type is not supported
    """
    if format_type not in FORMAT_SCHEMAS:
        available = ", ".join(FORMAT_SCHEMAS.keys())
        raise ValueError(f"Unsupported format type '{format_type}'. Available: {available}")

    return FORMAT_SCHEMAS[format_type]

def validate_format_type(format_type: str) -> bool:
    """
    Check if a format type is supported.

    Args:
        format_type: The format type to check

    Returns:
        True if supported, False otherwise
    """
    return format_type in FORMAT_SCHEMAS

def get_available_format_types() -> list:
    """
    Get list of all available format types.

    Returns:
        List of format type names
    """
    return list(FORMAT_SCHEMAS.keys())