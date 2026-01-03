#!/usr/bin/env python3
"""
Cleanup-Script: Löscht alle doppelten Tools bei ElevenLabs
Behält nur je EINE Version von jedem Tool (die mit 'kbj' im ID = neueste).
"""
from deploy_tools import load_env, get_api_key, list_tools, delete_tool
from collections import defaultdict

OUTPUT_FILE = "cleanup_output.txt"
output = []

def log(msg):
    print(msg, flush=True)
    output.append(msg)

# Tools die dedupliziert werden sollen
TOOLS_TO_DEDUPLICATE = [
    "connect_ideas",
    "create_bubble", 
    "create_idea",
    "delete_bubble",
    "delete_idea",
    "enter_bubble",
    "exit_bubble", 
    "find_idea",
    "get_bubble_stats",
    "get_current_space",
    "list_bubbles",
    "list_ideas",
    "make_memories",
    "promote_bubble",
    "recall_about_user",
    "score_bubble",
    "update_idea",
    "transfer_to_alice",
    "transfer_to_rachel",
]


def main():
    load_env()
    api_key = get_api_key()
    
    log("="*60)
    log("ElevenLabs Tool Cleanup")
    log("="*60)
    
    # Get all tools
    tools = list_tools(api_key)
    log(f"\nTotal tools before cleanup: {len(tools)}")
    
    # Group by name
    by_name = defaultdict(list)
    for tool in tools:
        config = tool.get("tool_config", {})
        name = config.get("name", "unknown")
        by_name[name].append(tool)
    
    # Find and delete duplicates
    deleted_count = 0
    
    for tool_name in TOOLS_TO_DEDUPLICATE:
        if tool_name not in by_name:
            continue
            
        tool_list = by_name[tool_name]
        if len(tool_list) <= 1:
            continue
        
        log(f"\n{tool_name}: {len(tool_list)} copies found")
        
        # Prefer tools with 'kbj' in ID (newest deploy)
        # If multiple kbj, keep first; if no kbj, keep any
        to_keep = None
        to_delete = []
        
        for tool in tool_list:
            tool_id = tool.get("id", "")
            if "kbj" in tool_id:
                if to_keep is None:
                    to_keep = tool
                else:
                    to_delete.append(tool)
            else:
                to_delete.append(tool)
        
        # Fallback if no kbj found
        if to_keep is None and tool_list:
            to_keep = tool_list[0]
            to_delete = tool_list[1:]
        
        if to_keep:
            log(f"  KEEPING: {to_keep.get('id')[:25]}...")
        
        for tool in to_delete:
            tool_id = tool.get("id")
            log(f"  DELETING: {tool_id[:25]}...")
            if delete_tool(api_key, tool_id):
                log(f"    ✓ Deleted")
                deleted_count += 1
            else:
                log(f"    ✗ Failed")
    
    # Final count
    log(f"\n{'='*60}")
    log(f"CLEANUP COMPLETE")
    log(f"Deleted {deleted_count} duplicate tools")
    log(f"{'='*60}")
    
    # Verify
    tools_after = list_tools(api_key)
    log(f"\nTotal tools after cleanup: {len(tools_after)}")
    
    # Save output
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(output))
    log(f"\nOutput saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()