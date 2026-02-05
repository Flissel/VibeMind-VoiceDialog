/**
 * Rich Content Renderer for Canvas Nodes
 *
 * Renders structured content (text, lists, code blocks, etc.) within canvas nodes
 * inside bubbles. Handles different content types and provides interactive elements.
 */

class RichContentRenderer {
    constructor(container) {
        this.container = container;
        this.nodes = new Map(); // nodeId -> node element
        this.contentTypes = {
            'text': this.renderText.bind(this),
            'heading': this.renderHeading.bind(this),
            'list': this.renderList.bind(this),
            'code': this.renderCode.bind(this),
            'quote': this.renderQuote.bind(this),
            'divider': this.renderDivider.bind(this),
            'image': this.renderImage.bind(this),
            'link': this.renderLink.bind(this),
            'table': this.renderTable.bind(this),
            // New format types
            'note': this.renderNote.bind(this),
            'action_list': this.renderActionList.bind(this),
            'pros_cons_table': this.renderProsConsTable.bind(this),
            'hierarchy': this.renderHierarchy.bind(this),
            'technical_specs': this.renderTechnicalSpecs.bind(this),
            // Figma-inspired formats
            'kanban': this.renderKanban.bind(this),
            'mindmap': this.renderMindmap.bind(this),
            'swot': this.renderSwot.bind(this),
            'user_story': this.renderUserStory.bind(this),
            'flowchart': this.renderFlowchart.bind(this)
        };
    }

    /**
     * Render a canvas node with structured content
     * @param {string} nodeId - Unique identifier for the node
     * @param {Object} nodeData - Node data containing content and metadata
     */
    renderNode(nodeId, nodeData) {
        console.log('[RichContentRenderer] Rendering node:', nodeId, nodeData);

        // Remove existing node if it exists
        this.removeNode(nodeId);

        // Create node container
        const nodeElement = this.createNodeContainer(nodeId, nodeData);
        this.nodes.set(nodeId, nodeElement);

        // Render content based on type
        if (nodeData.content && nodeData.content.type) {
            const renderFn = this.contentTypes[nodeData.content.type];
            if (renderFn) {
                const contentElement = renderFn(nodeData.content);
                nodeElement.appendChild(contentElement);
            } else {
                console.warn('[RichContentRenderer] Unknown content type:', nodeData.content.type);
                nodeElement.appendChild(this.renderText({ text: 'Unsupported content type' }));
            }
        }

        // Add metadata (timestamps, author, etc.)
        if (nodeData.metadata) {
            const metadataElement = this.renderMetadata(nodeData.metadata);
            nodeElement.appendChild(metadataElement);
        }

        // Position the node
        this.positionNode(nodeElement, nodeData.position);

        // Add to container
        this.container.appendChild(nodeElement);

        return nodeElement;
    }

    /**
     * Update an existing node
     * @param {string} nodeId - Node identifier
     * @param {Object} updates - Updated node data
     */
    updateNode(nodeId, updates) {
        console.log('[RichContentRenderer] Updating node:', nodeId, updates);

        const nodeElement = this.nodes.get(nodeId);
        if (!nodeElement) {
            console.warn('[RichContentRenderer] Node not found for update:', nodeId);
            return;
        }

        // Update position if provided
        if (updates.position) {
            this.positionNode(nodeElement, updates.position);
        }

        // Update content if provided
        if (updates.content) {
            // Clear existing content (but keep metadata)
            const contentElements = nodeElement.querySelectorAll('.node-content');
            contentElements.forEach(el => el.remove());

            const renderFn = this.contentTypes[updates.content.type];
            if (renderFn) {
                const contentElement = renderFn(updates.content);
                // Insert before metadata
                const metadataElement = nodeElement.querySelector('.node-metadata');
                if (metadataElement) {
                    nodeElement.insertBefore(contentElement, metadataElement);
                } else {
                    nodeElement.appendChild(contentElement);
                }
            }
        }

        // Update metadata if provided
        if (updates.metadata) {
            const existingMetadata = nodeElement.querySelector('.node-metadata');
            if (existingMetadata) {
                existingMetadata.remove();
            }
            const metadataElement = this.renderMetadata(updates.metadata);
            nodeElement.appendChild(metadataElement);
        }
    }

    /**
     * Remove a node
     * @param {string} nodeId - Node identifier
     */
    removeNode(nodeId) {
        const nodeElement = this.nodes.get(nodeId);
        if (nodeElement) {
            this.container.removeChild(nodeElement);
            this.nodes.delete(nodeId);
        }
    }

    /**
     * Create the basic node container
     */
    createNodeContainer(nodeId, nodeData) {
        const nodeElement = document.createElement('div');
        nodeElement.className = 'canvas-node';
        nodeElement.dataset.nodeId = nodeId;
        nodeElement.style.position = 'absolute';
        nodeElement.style.minWidth = '200px';
        nodeElement.style.maxWidth = '400px';
        nodeElement.style.backgroundColor = 'rgba(255, 255, 255, 0.95)';
        nodeElement.style.borderRadius = '8px';
        nodeElement.style.padding = '12px';
        nodeElement.style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.1)';
        nodeElement.style.border = '1px solid rgba(0, 0, 0, 0.1)';
        nodeElement.style.backdropFilter = 'blur(10px)';
        nodeElement.style.fontFamily = 'system-ui, -apple-system, sans-serif';

        // Add hover effects
        nodeElement.addEventListener('mouseenter', () => {
            nodeElement.style.transform = 'translateY(-2px)';
            nodeElement.style.boxShadow = '0 4px 16px rgba(0, 0, 0, 0.15)';
        });

        nodeElement.addEventListener('mouseleave', () => {
            nodeElement.style.transform = 'translateY(0)';
            nodeElement.style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.1)';
        });

        return nodeElement;
    }

    /**
     * Position a node element
     */
    positionNode(nodeElement, position) {
        if (position) {
            nodeElement.style.left = `${position.x}px`;
            nodeElement.style.top = `${position.y}px`;
        }
    }

    /**
     * Render text content
     */
    renderText(content) {
        const element = document.createElement('div');
        element.className = 'node-content text-content';
        element.style.marginBottom = '8px';
        element.style.lineHeight = '1.5';
        element.style.color = '#333';

        if (content.text) {
            element.textContent = content.text;
        }

        return element;
    }

    /**
     * Render heading content
     */
    renderHeading(content) {
        const element = document.createElement('div');
        element.className = 'node-content heading-content';

        const heading = document.createElement(content.level ? `h${Math.min(content.level, 6)}` : 'h3');
        heading.textContent = content.text || '';
        heading.style.margin = '0 0 8px 0';
        heading.style.color = '#2c3e50';
        heading.style.fontWeight = '600';

        element.appendChild(heading);
        return element;
    }

    /**
     * Render list content
     */
    renderList(content) {
        const element = document.createElement('div');
        element.className = 'node-content list-content';
        element.style.marginBottom = '8px';

        const list = document.createElement(content.ordered ? 'ol' : 'ul');
        list.style.margin = '0';
        list.style.paddingLeft = '20px';

        if (content.items && Array.isArray(content.items)) {
            content.items.forEach(item => {
                const li = document.createElement('li');
                li.textContent = item;
                li.style.marginBottom = '4px';
                list.appendChild(li);
            });
        }

        element.appendChild(list);
        return element;
    }

    /**
     * Render code content
     */
    renderCode(content) {
        const element = document.createElement('div');
        element.className = 'node-content code-content';
        element.style.marginBottom = '8px';

        const pre = document.createElement('pre');
        pre.style.backgroundColor = '#f8f9fa';
        pre.style.border = '1px solid #e9ecef';
        pre.style.borderRadius = '4px';
        pre.style.padding = '8px';
        pre.style.margin = '0';
        pre.style.fontSize = '14px';
        pre.style.fontFamily = 'Monaco, Menlo, "Ubuntu Mono", monospace';
        pre.style.overflow = 'auto';

        const code = document.createElement('code');
        code.textContent = content.code || '';
        if (content.language) {
            code.className = `language-${content.language}`;
        }

        pre.appendChild(code);
        element.appendChild(pre);
        return element;
    }

    /**
     * Render quote content
     */
    renderQuote(content) {
        const element = document.createElement('div');
        element.className = 'node-content quote-content';
        element.style.marginBottom = '8px';
        element.style.borderLeft = '4px solid #007bff';
        element.style.paddingLeft = '12px';
        element.style.fontStyle = 'italic';
        element.style.color = '#6c757d';

        const quote = document.createElement('blockquote');
        quote.style.margin = '0';
        quote.textContent = content.text || '';

        if (content.author) {
            const cite = document.createElement('cite');
            cite.textContent = `— ${content.author}`;
            cite.style.display = 'block';
            cite.style.marginTop = '8px';
            cite.style.fontStyle = 'normal';
            cite.style.fontSize = '14px';
            quote.appendChild(cite);
        }

        element.appendChild(quote);
        return element;
    }

    /**
     * Render divider content
     */
    renderDivider(content) {
        const element = document.createElement('div');
        element.className = 'node-content divider-content';
        element.style.marginBottom = '8px';

        const hr = document.createElement('hr');
        hr.style.border = 'none';
        hr.style.borderTop = '1px solid #dee2e6';
        hr.style.margin = '8px 0';

        element.appendChild(hr);
        return element;
    }

    /**
     * Render image content
     */
    renderImage(content) {
        const element = document.createElement('div');
        element.className = 'node-content image-content';
        element.style.marginBottom = '8px';

        const img = document.createElement('img');
        img.src = content.src || '';
        img.alt = content.alt || '';
        img.style.maxWidth = '100%';
        img.style.borderRadius = '4px';
        img.style.boxShadow = '0 1px 3px rgba(0, 0, 0, 0.1)';

        if (content.caption) {
            const caption = document.createElement('figcaption');
            caption.textContent = content.caption;
            caption.style.fontSize = '14px';
            caption.style.color = '#6c757d';
            caption.style.textAlign = 'center';
            caption.style.marginTop = '4px';

            const figure = document.createElement('figure');
            figure.style.margin = '0';
            figure.appendChild(img);
            figure.appendChild(caption);
            element.appendChild(figure);
        } else {
            element.appendChild(img);
        }

        return element;
    }

    /**
     * Render link content
     */
    renderLink(content) {
        const element = document.createElement('div');
        element.className = 'node-content link-content';
        element.style.marginBottom = '8px';

        const link = document.createElement('a');
        link.href = content.url || '#';
        link.textContent = content.text || content.url || '';
        link.style.color = '#007bff';
        link.style.textDecoration = 'none';
        link.target = '_blank';
        link.rel = 'noopener noreferrer';

        link.addEventListener('mouseenter', () => {
            link.style.textDecoration = 'underline';
        });

        link.addEventListener('mouseleave', () => {
            link.style.textDecoration = 'none';
        });

        element.appendChild(link);
        return element;
    }

    /**
     * Render table content
     */
    renderTable(content) {
        const element = document.createElement('div');
        element.className = 'node-content table-content';
        element.style.marginBottom = '8px';
        element.style.overflow = 'auto';

        const table = document.createElement('table');
        table.style.width = '100%';
        table.style.borderCollapse = 'collapse';
        table.style.fontSize = '14px';

        if (content.headers && content.rows) {
            // Header row
            const thead = document.createElement('thead');
            const headerRow = document.createElement('tr');

            content.headers.forEach(header => {
                const th = document.createElement('th');
                th.textContent = header;
                th.style.border = '1px solid #dee2e6';
                th.style.padding = '6px 8px';
                th.style.backgroundColor = '#f8f9fa';
                th.style.fontWeight = '600';
                th.style.textAlign = 'left';
                headerRow.appendChild(th);
            });

            thead.appendChild(headerRow);
            table.appendChild(thead);

            // Data rows
            const tbody = document.createElement('tbody');
            content.rows.forEach(row => {
                const tr = document.createElement('tr');

                row.forEach(cell => {
                    const td = document.createElement('td');
                    td.textContent = cell;
                    td.style.border = '1px solid #dee2e6';
                    td.style.padding = '6px 8px';
                    tr.appendChild(td);
                });

                tbody.appendChild(tr);
            });

            table.appendChild(tbody);
        }

        element.appendChild(table);
        return element;
    }

    /**
     * Render note content (simple text format)
     */
    renderNote(content) {
        const element = document.createElement('div');
        element.className = 'node-content note-content';
        element.style.marginBottom = '8px';

        // Title
        if (content.title) {
            const title = document.createElement('h4');
            title.textContent = content.title;
            title.style.margin = '0 0 8px 0';
            title.style.color = '#2c3e50';
            title.style.fontWeight = '600';
            element.appendChild(title);
        }

        // Text content
        if (content.text) {
            const text = document.createElement('p');
            text.textContent = content.text;
            text.style.margin = '0';
            text.style.lineHeight = '1.6';
            text.style.color = '#333';
            text.style.whiteSpace = 'pre-wrap';
            element.appendChild(text);
        }

        // Tags
        if (content.tags && content.tags.length > 0) {
            const tagsContainer = document.createElement('div');
            tagsContainer.style.marginTop = '8px';
            content.tags.forEach(tag => {
                const tagSpan = document.createElement('span');
                tagSpan.textContent = `#${tag}`;
                tagSpan.style.backgroundColor = '#e9ecef';
                tagSpan.style.padding = '2px 6px';
                tagSpan.style.borderRadius = '4px';
                tagSpan.style.marginRight = '4px';
                tagSpan.style.fontSize = '12px';
                tagSpan.style.color = '#495057';
                tagsContainer.appendChild(tagSpan);
            });
            element.appendChild(tagsContainer);
        }

        return element;
    }

    /**
     * Render action list (tasks with status and priority)
     */
    renderActionList(content) {
        const element = document.createElement('div');
        element.className = 'node-content action-list-content';
        element.style.marginBottom = '8px';

        // Title
        if (content.title) {
            const title = document.createElement('h4');
            title.textContent = content.title;
            title.style.margin = '0 0 12px 0';
            title.style.color = '#2c3e50';
            title.style.fontWeight = '600';
            element.appendChild(title);
        }

        // Items
        if (content.items && Array.isArray(content.items)) {
            const list = document.createElement('ul');
            list.style.listStyle = 'none';
            list.style.padding = '0';
            list.style.margin = '0';

            const statusColors = {
                'pending': '#6c757d',
                'in_progress': '#007bff',
                'completed': '#28a745',
                'blocked': '#dc3545'
            };

            const priorityColors = {
                'low': '#6c757d',
                'medium': '#ffc107',
                'high': '#fd7e14',
                'critical': '#dc3545'
            };

            content.items.forEach(item => {
                const li = document.createElement('li');
                li.style.display = 'flex';
                li.style.alignItems = 'center';
                li.style.padding = '8px 0';
                li.style.borderBottom = '1px solid #e9ecef';

                // Checkbox
                const checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.checked = item.status === 'completed';
                checkbox.style.marginRight = '10px';
                checkbox.style.cursor = 'pointer';
                li.appendChild(checkbox);

                // Task text
                const taskText = document.createElement('span');
                taskText.textContent = item.task || '';
                taskText.style.flex = '1';
                if (item.status === 'completed') {
                    taskText.style.textDecoration = 'line-through';
                    taskText.style.color = '#6c757d';
                }
                li.appendChild(taskText);

                // Status badge
                const statusBadge = document.createElement('span');
                statusBadge.textContent = item.status || 'pending';
                statusBadge.style.backgroundColor = statusColors[item.status] || '#6c757d';
                statusBadge.style.color = 'white';
                statusBadge.style.padding = '2px 6px';
                statusBadge.style.borderRadius = '4px';
                statusBadge.style.fontSize = '11px';
                statusBadge.style.marginLeft = '8px';
                li.appendChild(statusBadge);

                // Priority badge
                if (item.priority && item.priority !== 'medium') {
                    const priorityBadge = document.createElement('span');
                    priorityBadge.textContent = item.priority;
                    priorityBadge.style.backgroundColor = priorityColors[item.priority] || '#6c757d';
                    priorityBadge.style.color = 'white';
                    priorityBadge.style.padding = '2px 6px';
                    priorityBadge.style.borderRadius = '4px';
                    priorityBadge.style.fontSize = '11px';
                    priorityBadge.style.marginLeft = '4px';
                    li.appendChild(priorityBadge);
                }

                list.appendChild(li);
            });

            element.appendChild(list);
        }

        return element;
    }

    /**
     * Render pros/cons table
     */
    renderProsConsTable(content) {
        const element = document.createElement('div');
        element.className = 'node-content pros-cons-content';
        element.style.marginBottom = '8px';

        // Title
        if (content.title || content.topic) {
            const title = document.createElement('h4');
            title.textContent = content.title || content.topic;
            title.style.margin = '0 0 12px 0';
            title.style.color = '#2c3e50';
            title.style.fontWeight = '600';
            element.appendChild(title);
        }

        // Two-column container
        const container = document.createElement('div');
        container.style.display = 'flex';
        container.style.gap = '12px';

        // Pros column
        const prosCol = document.createElement('div');
        prosCol.style.flex = '1';
        prosCol.style.backgroundColor = '#d4edda';
        prosCol.style.borderRadius = '8px';
        prosCol.style.padding = '12px';

        const prosHeader = document.createElement('h5');
        prosHeader.textContent = 'Vorteile';
        prosHeader.style.margin = '0 0 8px 0';
        prosHeader.style.color = '#155724';
        prosCol.appendChild(prosHeader);

        if (content.pros && Array.isArray(content.pros)) {
            const prosList = document.createElement('ul');
            prosList.style.margin = '0';
            prosList.style.paddingLeft = '16px';
            content.pros.forEach(pro => {
                const li = document.createElement('li');
                li.textContent = pro.point || pro;
                li.style.marginBottom = '4px';
                li.style.color = '#155724';
                prosList.appendChild(li);
            });
            prosCol.appendChild(prosList);
        }
        container.appendChild(prosCol);

        // Cons column
        const consCol = document.createElement('div');
        consCol.style.flex = '1';
        consCol.style.backgroundColor = '#f8d7da';
        consCol.style.borderRadius = '8px';
        consCol.style.padding = '12px';

        const consHeader = document.createElement('h5');
        consHeader.textContent = 'Nachteile';
        consHeader.style.margin = '0 0 8px 0';
        consHeader.style.color = '#721c24';
        consCol.appendChild(consHeader);

        if (content.cons && Array.isArray(content.cons)) {
            const consList = document.createElement('ul');
            consList.style.margin = '0';
            consList.style.paddingLeft = '16px';
            content.cons.forEach(con => {
                const li = document.createElement('li');
                li.textContent = con.point || con;
                li.style.marginBottom = '4px';
                li.style.color = '#721c24';
                consList.appendChild(li);
            });
            consCol.appendChild(consList);
        }
        container.appendChild(consCol);

        element.appendChild(container);

        // Summary
        if (content.summary && content.summary.recommendation) {
            const summary = document.createElement('div');
            summary.style.marginTop = '12px';
            summary.style.padding = '8px';
            summary.style.backgroundColor = '#e9ecef';
            summary.style.borderRadius = '4px';
            summary.style.fontSize = '13px';
            summary.innerHTML = `<strong>Empfehlung:</strong> ${content.summary.recommendation}`;
            element.appendChild(summary);
        }

        return element;
    }

    /**
     * Render hierarchy/outline structure
     */
    renderHierarchy(content) {
        const element = document.createElement('div');
        element.className = 'node-content hierarchy-content';
        element.style.marginBottom = '8px';

        // Title
        if (content.title || content.root_concept) {
            const title = document.createElement('h4');
            title.textContent = content.title || content.root_concept;
            title.style.margin = '0 0 12px 0';
            title.style.color = '#2c3e50';
            title.style.fontWeight = '600';
            element.appendChild(title);
        }

        // Levels
        if (content.levels && Array.isArray(content.levels)) {
            const tree = document.createElement('div');
            tree.style.fontFamily = 'monospace';

            content.levels.forEach(level => {
                const levelNum = level.level || 1;
                const indent = (levelNum - 1) * 20;

                if (level.items && Array.isArray(level.items)) {
                    level.items.forEach(item => {
                        const itemDiv = document.createElement('div');
                        itemDiv.style.paddingLeft = `${indent}px`;
                        itemDiv.style.marginBottom = '4px';
                        itemDiv.style.display = 'flex';
                        itemDiv.style.alignItems = 'flex-start';

                        // Bullet/connector
                        const bullet = document.createElement('span');
                        bullet.textContent = levelNum === 1 ? '▸ ' : '├─ ';
                        bullet.style.color = '#6c757d';
                        bullet.style.marginRight = '4px';
                        itemDiv.appendChild(bullet);

                        // Item content
                        const itemContent = document.createElement('div');
                        const itemName = document.createElement('strong');
                        itemName.textContent = item.name || item;
                        itemContent.appendChild(itemName);

                        if (item.description) {
                            const desc = document.createElement('span');
                            desc.textContent = ` - ${item.description}`;
                            desc.style.color = '#6c757d';
                            itemContent.appendChild(desc);
                        }

                        itemDiv.appendChild(itemContent);
                        tree.appendChild(itemDiv);
                    });
                }
            });

            element.appendChild(tree);
        }

        return element;
    }

    /**
     * Render technical specifications
     */
    renderTechnicalSpecs(content) {
        const element = document.createElement('div');
        element.className = 'node-content specs-content';
        element.style.marginBottom = '8px';

        // Title
        if (content.title || content.component) {
            const title = document.createElement('h4');
            title.textContent = content.title || `Specs: ${content.component}`;
            title.style.margin = '0 0 12px 0';
            title.style.color = '#2c3e50';
            title.style.fontWeight = '600';
            element.appendChild(title);
        }

        // Specifications
        if (content.specifications && Array.isArray(content.specifications)) {
            const priorityColors = {
                'must_have': '#dc3545',
                'should_have': '#ffc107',
                'nice_to_have': '#28a745'
            };

            // Group by category
            const categories = {};
            content.specifications.forEach(spec => {
                const cat = spec.category || 'General';
                if (!categories[cat]) categories[cat] = [];
                categories[cat].push(spec);
            });

            Object.entries(categories).forEach(([category, specs]) => {
                const catDiv = document.createElement('div');
                catDiv.style.marginBottom = '12px';

                const catHeader = document.createElement('h5');
                catHeader.textContent = category;
                catHeader.style.margin = '0 0 8px 0';
                catHeader.style.color = '#495057';
                catHeader.style.borderBottom = '1px solid #e9ecef';
                catHeader.style.paddingBottom = '4px';
                catDiv.appendChild(catHeader);

                specs.forEach(spec => {
                    const specDiv = document.createElement('div');
                    specDiv.style.display = 'flex';
                    specDiv.style.alignItems = 'flex-start';
                    specDiv.style.marginBottom = '6px';
                    specDiv.style.paddingLeft = '8px';

                    // Priority indicator
                    const priority = document.createElement('span');
                    priority.style.width = '8px';
                    priority.style.height = '8px';
                    priority.style.borderRadius = '50%';
                    priority.style.backgroundColor = priorityColors[spec.priority] || '#6c757d';
                    priority.style.marginRight = '8px';
                    priority.style.marginTop = '6px';
                    priority.style.flexShrink = '0';
                    specDiv.appendChild(priority);

                    // Requirement text
                    const reqText = document.createElement('div');
                    reqText.style.flex = '1';

                    const reqMain = document.createElement('div');
                    reqMain.textContent = spec.requirement || '';
                    reqText.appendChild(reqMain);

                    if (spec.acceptance_criteria) {
                        const criteria = document.createElement('div');
                        criteria.textContent = `Test: ${spec.acceptance_criteria}`;
                        criteria.style.fontSize = '12px';
                        criteria.style.color = '#6c757d';
                        criteria.style.marginTop = '2px';
                        reqText.appendChild(criteria);
                    }

                    specDiv.appendChild(reqText);
                    catDiv.appendChild(specDiv);
                });

                element.appendChild(catDiv);
            });
        }

        // Implementation notes
        if (content.implementation_notes) {
            const notes = document.createElement('div');
            notes.style.marginTop = '12px';
            notes.style.padding = '8px';
            notes.style.backgroundColor = '#fff3cd';
            notes.style.borderRadius = '4px';
            notes.style.fontSize = '13px';
            notes.innerHTML = `<strong>Hinweise:</strong> ${content.implementation_notes}`;
            element.appendChild(notes);
        }

        return element;
    }

    // =========================================================================
    // FIGMA-INSPIRED FORMAT RENDERERS
    // =========================================================================

    /**
     * Render Kanban board with columns and cards
     */
    renderKanban(content) {
        const element = document.createElement('div');
        element.className = 'node-content kanban-content';
        element.style.marginBottom = '8px';

        // Title
        if (content.title) {
            const title = document.createElement('h4');
            title.textContent = content.title;
            title.style.margin = '0 0 12px 0';
            title.style.color = '#2c3e50';
            title.style.fontWeight = '600';
            element.appendChild(title);
        }

        // Columns container
        if (content.columns && Array.isArray(content.columns)) {
            const board = document.createElement('div');
            board.style.display = 'flex';
            board.style.gap = '8px';
            board.style.overflowX = 'auto';
            board.style.paddingBottom = '4px';

            const priorityColors = {
                'low': '#6c757d',
                'medium': '#ffc107',
                'high': '#fd7e14',
                'critical': '#dc3545'
            };

            content.columns.forEach(column => {
                const col = document.createElement('div');
                col.style.minWidth = '140px';
                col.style.flex = '1';
                col.style.backgroundColor = '#f8f9fa';
                col.style.borderRadius = '6px';
                col.style.overflow = 'hidden';

                // Column header
                const header = document.createElement('div');
                header.style.padding = '8px 10px';
                header.style.backgroundColor = column.color || '#e9ecef';
                header.style.fontWeight = '600';
                header.style.fontSize = '12px';
                header.style.color = '#fff';
                header.style.display = 'flex';
                header.style.justifyContent = 'space-between';
                header.style.alignItems = 'center';

                const headerText = document.createElement('span');
                headerText.textContent = column.name || '';
                header.appendChild(headerText);

                if (column.cards && column.cards.length > 0) {
                    const count = document.createElement('span');
                    count.textContent = column.cards.length;
                    count.style.backgroundColor = 'rgba(255,255,255,0.3)';
                    count.style.borderRadius = '10px';
                    count.style.padding = '1px 6px';
                    count.style.fontSize = '11px';
                    header.appendChild(count);
                }

                col.appendChild(header);

                // Cards
                const cardsContainer = document.createElement('div');
                cardsContainer.style.padding = '6px';
                cardsContainer.style.display = 'flex';
                cardsContainer.style.flexDirection = 'column';
                cardsContainer.style.gap = '4px';

                if (column.cards && Array.isArray(column.cards)) {
                    column.cards.forEach(card => {
                        const cardEl = document.createElement('div');
                        cardEl.style.backgroundColor = '#fff';
                        cardEl.style.borderRadius = '4px';
                        cardEl.style.padding = '8px';
                        cardEl.style.boxShadow = '0 1px 2px rgba(0,0,0,0.08)';
                        cardEl.style.fontSize = '12px';
                        cardEl.style.borderLeft = `3px solid ${priorityColors[card.priority] || '#dee2e6'}`;

                        const cardTitle = document.createElement('div');
                        cardTitle.textContent = card.title || '';
                        cardTitle.style.fontWeight = '500';
                        cardTitle.style.color = '#333';
                        cardTitle.style.marginBottom = card.description ? '4px' : '0';
                        cardEl.appendChild(cardTitle);

                        if (card.description) {
                            const cardDesc = document.createElement('div');
                            cardDesc.textContent = card.description;
                            cardDesc.style.color = '#6c757d';
                            cardDesc.style.fontSize = '11px';
                            cardDesc.style.lineHeight = '1.3';
                            cardEl.appendChild(cardDesc);
                        }

                        // Labels
                        if (card.labels && card.labels.length > 0) {
                            const labelsRow = document.createElement('div');
                            labelsRow.style.marginTop = '4px';
                            labelsRow.style.display = 'flex';
                            labelsRow.style.flexWrap = 'wrap';
                            labelsRow.style.gap = '2px';

                            const labelColors = ['#007bff', '#28a745', '#fd7e14', '#6f42c1', '#20c997'];
                            card.labels.forEach((label, i) => {
                                const labelEl = document.createElement('span');
                                labelEl.textContent = label;
                                labelEl.style.backgroundColor = labelColors[i % labelColors.length];
                                labelEl.style.color = '#fff';
                                labelEl.style.padding = '1px 5px';
                                labelEl.style.borderRadius = '3px';
                                labelEl.style.fontSize = '10px';
                                labelsRow.appendChild(labelEl);
                            });
                            cardEl.appendChild(labelsRow);
                        }

                        cardsContainer.appendChild(cardEl);
                    });
                }

                col.appendChild(cardsContainer);
                board.appendChild(col);
            });

            element.appendChild(board);
        }

        return element;
    }

    /**
     * Render mind map with central concept and branches
     */
    renderMindmap(content) {
        const element = document.createElement('div');
        element.className = 'node-content mindmap-content';
        element.style.marginBottom = '8px';

        // Title
        if (content.title) {
            const title = document.createElement('h4');
            title.textContent = content.title;
            title.style.margin = '0 0 12px 0';
            title.style.color = '#2c3e50';
            title.style.fontWeight = '600';
            element.appendChild(title);
        }

        // Center node
        if (content.center) {
            const centerNode = document.createElement('div');
            centerNode.style.textAlign = 'center';
            centerNode.style.marginBottom = '12px';

            const centerLabel = document.createElement('div');
            centerLabel.textContent = content.center.label || '';
            centerLabel.style.display = 'inline-block';
            centerLabel.style.padding = '10px 20px';
            centerLabel.style.backgroundColor = '#2c3e50';
            centerLabel.style.color = '#fff';
            centerLabel.style.borderRadius = '20px';
            centerLabel.style.fontWeight = '600';
            centerLabel.style.fontSize = '14px';
            centerLabel.style.boxShadow = '0 2px 8px rgba(0,0,0,0.15)';
            centerNode.appendChild(centerLabel);

            if (content.center.description) {
                const desc = document.createElement('div');
                desc.textContent = content.center.description;
                desc.style.fontSize = '12px';
                desc.style.color = '#6c757d';
                desc.style.marginTop = '4px';
                centerNode.appendChild(desc);
            }

            element.appendChild(centerNode);
        }

        // Branches
        if (content.branches && Array.isArray(content.branches)) {
            const defaultColors = ['#007bff', '#28a745', '#fd7e14', '#dc3545', '#6f42c1', '#20c997', '#e83e8c'];

            content.branches.forEach((branch, index) => {
                const branchColor = branch.color || defaultColors[index % defaultColors.length];

                const branchEl = document.createElement('div');
                branchEl.style.marginBottom = '8px';
                branchEl.style.borderLeft = `3px solid ${branchColor}`;
                branchEl.style.paddingLeft = '10px';

                // Branch label
                const branchLabel = document.createElement('div');
                branchLabel.textContent = branch.label || '';
                branchLabel.style.fontWeight = '600';
                branchLabel.style.fontSize = '13px';
                branchLabel.style.color = branchColor;
                branchLabel.style.marginBottom = '4px';
                branchEl.appendChild(branchLabel);

                // Children
                if (branch.children && Array.isArray(branch.children)) {
                    branch.children.forEach(child => {
                        const childEl = document.createElement('div');
                        childEl.style.paddingLeft = '12px';
                        childEl.style.marginBottom = '3px';
                        childEl.style.display = 'flex';
                        childEl.style.alignItems = 'flex-start';

                        const bullet = document.createElement('span');
                        bullet.textContent = '\u2022 ';
                        bullet.style.color = branchColor;
                        bullet.style.marginRight = '4px';
                        bullet.style.fontWeight = 'bold';
                        childEl.appendChild(bullet);

                        const childContent = document.createElement('div');
                        const childLabel = document.createElement('span');
                        childLabel.textContent = child.label || '';
                        childLabel.style.fontSize = '12px';
                        childLabel.style.color = '#333';
                        childContent.appendChild(childLabel);

                        if (child.description) {
                            const childDesc = document.createElement('span');
                            childDesc.textContent = ` \u2014 ${child.description}`;
                            childDesc.style.fontSize = '11px';
                            childDesc.style.color = '#6c757d';
                            childContent.appendChild(childDesc);
                        }

                        // Nested children (level 3)
                        if (child.children && Array.isArray(child.children)) {
                            child.children.forEach(grandchild => {
                                const gcEl = document.createElement('div');
                                gcEl.style.paddingLeft = '14px';
                                gcEl.style.fontSize = '11px';
                                gcEl.style.color = '#6c757d';
                                gcEl.textContent = `\u25E6 ${grandchild.label || grandchild}`;
                                childContent.appendChild(gcEl);
                            });
                        }

                        childEl.appendChild(childContent);
                        branchEl.appendChild(childEl);
                    });
                }

                element.appendChild(branchEl);
            });
        }

        return element;
    }

    /**
     * Render SWOT analysis (Strengths, Weaknesses, Opportunities, Threats)
     */
    renderSwot(content) {
        const element = document.createElement('div');
        element.className = 'node-content swot-content';
        element.style.marginBottom = '8px';

        // Title
        if (content.title || content.subject) {
            const title = document.createElement('h4');
            title.textContent = content.title || `SWOT: ${content.subject}`;
            title.style.margin = '0 0 12px 0';
            title.style.color = '#2c3e50';
            title.style.fontWeight = '600';
            element.appendChild(title);
        }

        // 2x2 Grid
        const grid = document.createElement('div');
        grid.style.display = 'grid';
        grid.style.gridTemplateColumns = '1fr 1fr';
        grid.style.gap = '6px';

        const quadrants = [
            { key: 'strengths', label: 'Strengths', bg: '#d4edda', headerBg: '#28a745', color: '#155724', detailKey: 'impact' },
            { key: 'weaknesses', label: 'Weaknesses', bg: '#f8d7da', headerBg: '#dc3545', color: '#721c24', detailKey: 'mitigation' },
            { key: 'opportunities', label: 'Opportunities', bg: '#d1ecf1', headerBg: '#17a2b8', color: '#0c5460', detailKey: 'action' },
            { key: 'threats', label: 'Threats', bg: '#fff3cd', headerBg: '#ffc107', color: '#856404', detailKey: 'contingency' },
        ];

        quadrants.forEach(q => {
            const cell = document.createElement('div');
            cell.style.backgroundColor = q.bg;
            cell.style.borderRadius = '6px';
            cell.style.overflow = 'hidden';

            // Quadrant header
            const header = document.createElement('div');
            header.textContent = q.label;
            header.style.backgroundColor = q.headerBg;
            header.style.color = '#fff';
            header.style.padding = '6px 10px';
            header.style.fontWeight = '600';
            header.style.fontSize = '12px';
            cell.appendChild(header);

            // Items
            const items = content[q.key];
            if (items && Array.isArray(items)) {
                const list = document.createElement('ul');
                list.style.margin = '0';
                list.style.padding = '8px 8px 8px 24px';
                list.style.fontSize = '12px';

                items.forEach(item => {
                    const li = document.createElement('li');
                    li.style.marginBottom = '3px';
                    li.style.color = q.color;
                    li.textContent = item.point || item;

                    // Impact/likelihood badge
                    const level = item.impact || item.likelihood;
                    if (level) {
                        const badge = document.createElement('span');
                        badge.textContent = ` [${level}]`;
                        badge.style.fontSize = '10px';
                        badge.style.opacity = '0.7';
                        li.appendChild(badge);
                    }

                    list.appendChild(li);
                });

                cell.appendChild(list);
            }

            grid.appendChild(cell);
        });

        element.appendChild(grid);

        // Summary
        if (content.summary) {
            const summary = document.createElement('div');
            summary.style.marginTop = '10px';
            summary.style.padding = '8px';
            summary.style.backgroundColor = '#e9ecef';
            summary.style.borderRadius = '4px';
            summary.style.fontSize = '12px';

            if (content.summary.strategic_position) {
                const pos = document.createElement('div');
                pos.innerHTML = `<strong>Position:</strong> ${content.summary.strategic_position}`;
                pos.style.marginBottom = '4px';
                summary.appendChild(pos);
            }

            if (content.summary.key_actions && content.summary.key_actions.length > 0) {
                const actions = document.createElement('div');
                actions.innerHTML = `<strong>Actions:</strong> ${content.summary.key_actions.join(', ')}`;
                summary.appendChild(actions);
            }

            element.appendChild(summary);
        }

        return element;
    }

    /**
     * Render User Stories in agile format
     */
    renderUserStory(content) {
        const element = document.createElement('div');
        element.className = 'node-content user-story-content';
        element.style.marginBottom = '8px';

        // Title / Epic
        if (content.title || content.epic) {
            const title = document.createElement('h4');
            title.textContent = content.title || content.epic;
            title.style.margin = '0 0 4px 0';
            title.style.color = '#2c3e50';
            title.style.fontWeight = '600';
            element.appendChild(title);

            if (content.epic && content.title) {
                const epic = document.createElement('div');
                epic.textContent = `Epic: ${content.epic}`;
                epic.style.fontSize = '12px';
                epic.style.color = '#6f42c1';
                epic.style.marginBottom = '10px';
                element.appendChild(epic);
            }
        }

        const moscowColors = {
            'must_have': '#dc3545',
            'should_have': '#fd7e14',
            'could_have': '#ffc107',
            'wont_have': '#6c757d',
        };

        // Stories
        if (content.stories && Array.isArray(content.stories)) {
            content.stories.forEach(story => {
                const card = document.createElement('div');
                card.style.backgroundColor = '#f8f9fa';
                card.style.borderRadius = '6px';
                card.style.padding = '10px';
                card.style.marginBottom = '8px';
                card.style.borderLeft = `3px solid ${moscowColors[story.priority] || '#007bff'}`;

                // Header row: ID + priority + story points
                const headerRow = document.createElement('div');
                headerRow.style.display = 'flex';
                headerRow.style.alignItems = 'center';
                headerRow.style.gap = '6px';
                headerRow.style.marginBottom = '6px';

                if (story.id) {
                    const idBadge = document.createElement('span');
                    idBadge.textContent = story.id;
                    idBadge.style.backgroundColor = '#007bff';
                    idBadge.style.color = '#fff';
                    idBadge.style.padding = '1px 6px';
                    idBadge.style.borderRadius = '3px';
                    idBadge.style.fontSize = '11px';
                    idBadge.style.fontWeight = '600';
                    headerRow.appendChild(idBadge);
                }

                if (story.priority) {
                    const priBadge = document.createElement('span');
                    priBadge.textContent = story.priority.replace('_', ' ');
                    priBadge.style.backgroundColor = moscowColors[story.priority] || '#6c757d';
                    priBadge.style.color = '#fff';
                    priBadge.style.padding = '1px 6px';
                    priBadge.style.borderRadius = '3px';
                    priBadge.style.fontSize = '10px';
                    priBadge.style.textTransform = 'uppercase';
                    headerRow.appendChild(priBadge);
                }

                if (story.story_points) {
                    const sp = document.createElement('span');
                    sp.textContent = `${story.story_points} SP`;
                    sp.style.marginLeft = 'auto';
                    sp.style.backgroundColor = '#e9ecef';
                    sp.style.padding = '1px 6px';
                    sp.style.borderRadius = '10px';
                    sp.style.fontSize = '11px';
                    sp.style.color = '#495057';
                    sp.style.fontWeight = '600';
                    headerRow.appendChild(sp);
                }

                card.appendChild(headerRow);

                // Story text: Als [role] möchte ich [want] damit [benefit]
                const storyText = document.createElement('div');
                storyText.style.fontSize = '13px';
                storyText.style.lineHeight = '1.4';
                storyText.style.color = '#333';

                const roleSpan = document.createElement('span');
                roleSpan.textContent = `Als ${story.role || '...'}`;
                roleSpan.style.fontWeight = '500';
                storyText.appendChild(roleSpan);

                const wantSpan = document.createElement('span');
                wantSpan.textContent = ` möchte ich ${story.want || '...'}`;
                storyText.appendChild(wantSpan);

                const benefitSpan = document.createElement('span');
                benefitSpan.textContent = ` damit ${story.benefit || '...'}`;
                benefitSpan.style.fontStyle = 'italic';
                benefitSpan.style.color = '#6c757d';
                storyText.appendChild(benefitSpan);

                card.appendChild(storyText);

                // Acceptance criteria
                if (story.acceptance_criteria && story.acceptance_criteria.length > 0) {
                    const acDiv = document.createElement('div');
                    acDiv.style.marginTop = '6px';
                    acDiv.style.paddingTop = '6px';
                    acDiv.style.borderTop = '1px solid #dee2e6';

                    const acLabel = document.createElement('div');
                    acLabel.textContent = 'Akzeptanzkriterien:';
                    acLabel.style.fontSize = '11px';
                    acLabel.style.fontWeight = '600';
                    acLabel.style.color = '#495057';
                    acLabel.style.marginBottom = '3px';
                    acDiv.appendChild(acLabel);

                    story.acceptance_criteria.forEach(ac => {
                        const acItem = document.createElement('div');
                        acItem.style.fontSize = '11px';
                        acItem.style.color = '#6c757d';
                        acItem.style.paddingLeft = '10px';
                        acItem.textContent = `\u2713 ${ac}`;
                        acDiv.appendChild(acItem);
                    });

                    card.appendChild(acDiv);
                }

                element.appendChild(card);
            });
        }

        // Personas
        if (content.personas && content.personas.length > 0) {
            const personaSection = document.createElement('div');
            personaSection.style.marginTop = '8px';
            personaSection.style.padding = '8px';
            personaSection.style.backgroundColor = '#e8f4fd';
            personaSection.style.borderRadius = '4px';

            const personaLabel = document.createElement('div');
            personaLabel.textContent = 'Personas';
            personaLabel.style.fontWeight = '600';
            personaLabel.style.fontSize = '12px';
            personaLabel.style.color = '#0c5460';
            personaLabel.style.marginBottom = '4px';
            personaSection.appendChild(personaLabel);

            content.personas.forEach(persona => {
                const pEl = document.createElement('div');
                pEl.style.fontSize = '11px';
                pEl.style.color = '#0c5460';
                pEl.style.marginBottom = '2px';
                pEl.textContent = `${persona.name || ''} (${persona.role || ''})`;
                personaSection.appendChild(pEl);
            });

            element.appendChild(personaSection);
        }

        return element;
    }

    /**
     * Render Flowchart with process steps and decisions
     */
    renderFlowchart(content) {
        const element = document.createElement('div');
        element.className = 'node-content flowchart-content';
        element.style.marginBottom = '8px';

        // Title
        if (content.title) {
            const title = document.createElement('h4');
            title.textContent = content.title;
            title.style.margin = '0 0 12px 0';
            title.style.color = '#2c3e50';
            title.style.fontWeight = '600';
            element.appendChild(title);
        }

        if (content.description) {
            const desc = document.createElement('div');
            desc.textContent = content.description;
            desc.style.fontSize = '12px';
            desc.style.color = '#6c757d';
            desc.style.marginBottom = '10px';
            element.appendChild(desc);
        }

        // Build adjacency from edges for ordering
        const nodeMap = {};
        if (content.nodes) {
            content.nodes.forEach(n => { nodeMap[n.id] = n; });
        }

        const edgesBySource = {};
        if (content.edges) {
            content.edges.forEach(e => {
                if (!edgesBySource[e.from]) edgesBySource[e.from] = [];
                edgesBySource[e.from].push(e);
            });
        }

        // Node type styles
        const nodeStyles = {
            'start': { bg: '#28a745', color: '#fff', radius: '20px', border: 'none' },
            'end': { bg: '#dc3545', color: '#fff', radius: '20px', border: 'none' },
            'process': { bg: '#e9ecef', color: '#333', radius: '4px', border: '1px solid #ced4da' },
            'decision': { bg: '#fff3cd', color: '#856404', radius: '4px', border: '2px solid #ffc107' },
            'subprocess': { bg: '#d1ecf1', color: '#0c5460', radius: '4px', border: '1px solid #bee5eb' },
        };

        // Render nodes in order
        const flow = document.createElement('div');
        flow.style.display = 'flex';
        flow.style.flexDirection = 'column';
        flow.style.alignItems = 'center';
        flow.style.gap = '0';

        if (content.nodes && Array.isArray(content.nodes)) {
            content.nodes.forEach((node, index) => {
                // Edge label from previous node
                if (index > 0 && content.edges) {
                    const prevNode = content.nodes[index - 1];
                    const connectingEdge = content.edges.find(
                        e => e.from === prevNode.id && e.to === node.id
                    );

                    // Arrow connector
                    const connector = document.createElement('div');
                    connector.style.display = 'flex';
                    connector.style.flexDirection = 'column';
                    connector.style.alignItems = 'center';
                    connector.style.margin = '0';

                    const line = document.createElement('div');
                    line.style.width = '2px';
                    line.style.height = '16px';
                    line.style.backgroundColor = '#adb5bd';
                    connector.appendChild(line);

                    if (connectingEdge && connectingEdge.label) {
                        const edgeLabel = document.createElement('div');
                        edgeLabel.textContent = connectingEdge.label;
                        edgeLabel.style.fontSize = '10px';
                        edgeLabel.style.color = '#6c757d';
                        edgeLabel.style.fontStyle = 'italic';
                        edgeLabel.style.margin = '2px 0';
                        connector.appendChild(edgeLabel);

                        const line2 = document.createElement('div');
                        line2.style.width = '2px';
                        line2.style.height = '8px';
                        line2.style.backgroundColor = '#adb5bd';
                        connector.appendChild(line2);
                    }

                    const arrow = document.createElement('div');
                    arrow.textContent = '\u25BC';
                    arrow.style.fontSize = '10px';
                    arrow.style.color = '#adb5bd';
                    arrow.style.lineHeight = '1';
                    connector.appendChild(arrow);

                    flow.appendChild(connector);
                }

                // Node element
                const style = nodeStyles[node.type] || nodeStyles['process'];
                const nodeEl = document.createElement('div');
                nodeEl.style.padding = '8px 16px';
                nodeEl.style.backgroundColor = style.bg;
                nodeEl.style.color = style.color;
                nodeEl.style.borderRadius = style.radius;
                nodeEl.style.border = style.border;
                nodeEl.style.textAlign = 'center';
                nodeEl.style.minWidth = '120px';
                nodeEl.style.maxWidth = '200px';
                nodeEl.style.fontSize = '12px';
                nodeEl.style.fontWeight = (node.type === 'start' || node.type === 'end') ? '600' : '400';

                if (node.type === 'decision') {
                    nodeEl.style.transform = 'rotate(0deg)';
                    nodeEl.style.borderStyle = 'solid';
                    nodeEl.style.position = 'relative';
                    // Diamond indicator
                    const diamond = document.createElement('span');
                    diamond.textContent = '\u25C7 ';
                    diamond.style.fontWeight = 'bold';
                    nodeEl.appendChild(diamond);
                }

                const labelText = document.createElement('span');
                labelText.textContent = node.label || '';
                nodeEl.appendChild(labelText);

                if (node.description && node.type !== 'start' && node.type !== 'end') {
                    const nodeDesc = document.createElement('div');
                    nodeDesc.textContent = node.description;
                    nodeDesc.style.fontSize = '10px';
                    nodeDesc.style.opacity = '0.8';
                    nodeDesc.style.marginTop = '2px';
                    nodeEl.appendChild(nodeDesc);
                }

                flow.appendChild(nodeEl);
            });
        }

        element.appendChild(flow);
        return element;
    }

    /**
     * Render metadata (timestamps, author, etc.)
     */
    renderMetadata(metadata) {
        const element = document.createElement('div');
        element.className = 'node-metadata';
        element.style.fontSize = '12px';
        element.style.color = '#6c757d';
        element.style.borderTop = '1px solid #e9ecef';
        element.style.paddingTop = '6px';
        element.style.marginTop = '8px';

        const parts = [];

        if (metadata.author) {
            parts.push(`By ${metadata.author}`);
        }

        if (metadata.timestamp) {
            const date = new Date(metadata.timestamp);
            parts.push(date.toLocaleString());
        }

        if (metadata.tags && metadata.tags.length > 0) {
            const tags = metadata.tags.map(tag => `#${tag}`).join(' ');
            parts.push(tags);
        }

        element.textContent = parts.join(' • ');
        return element;
    }

    /**
     * Clear all nodes
     */
    clear() {
        this.nodes.forEach((nodeElement) => {
            if (nodeElement.parentNode) {
                nodeElement.parentNode.removeChild(nodeElement);
            }
        });
        this.nodes.clear();
    }

    /**
     * Get all rendered nodes
     */
    getNodes() {
        return Array.from(this.nodes.keys());
    }

    /**
     * Get a specific node element
     */
    getNodeElement(nodeId) {
        return this.nodes.get(nodeId);
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = RichContentRenderer;
}