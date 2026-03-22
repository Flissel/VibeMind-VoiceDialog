# VibeMind Custom n8n Image
# Pre-installed: AI Agent nodes (Langchain), Think Tool, Toolcalls
#
# Build:
#   docker build -t vibemind-n8n .
#
# The @n8n/n8n-nodes-langchain package is bundled with n8n since v1.19+
# This Dockerfile ensures persistence and correct env defaults.

FROM n8nio/n8n:latest

# n8n data directory (workflows, credentials, settings)
VOLUME /home/node/.n8n

# Default environment
ENV N8N_METRICS=true \
    N8N_DIAGNOSTICS_ENABLED=false \
    N8N_TEMPLATES_ENABLED=true \
    N8N_COMMUNITY_PACKAGES_ALLOW_TOOL_USAGE=true \
    GENERIC_TIMEZONE=Europe/Berlin

EXPOSE 5678
