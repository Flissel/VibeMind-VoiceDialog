/**
 * ShuttleManager - Visualizes requirement shuttles traveling from Ideas Space to Projects Space
 *
 * Shuttles represent the req-orchestrator pipeline progress:
 * - Position on path = DNA pipeline stage (5 stages)
 * - Checkpoints = Mining → Requirements → Validation → Knowledge Graph → TechStack
 * - Click = transfer to Alice for navigation
 */

// The 4 DNA Pipeline stages from req-orchestrator (matching UI tabs)
const DNA_STAGES = [
    { name: 'Mining', key: 'mining', icon: '🏭', position: 0.2, color: 0x8866ff },
    { name: 'Validation', key: 'validation', icon: '⚖️', position: 0.5, color: 0x66ffaa },
    { name: 'Knowledge Graph', key: 'knowledge_graph', icon: '🔗', position: 0.75, color: 0xffaa66 },
    { name: 'TechStack', key: 'techstack', icon: '📁', position: 1.0, color: 0xff66aa },
];

// Checkpoint icon configuration
const CHECKPOINT_ICONS = {
    mining: { emoji: '🏭', label: 'Mining', desc: 'Extract Requirements' },
    validation: { emoji: '⚖️', label: 'Validation', desc: '9-Criteria Scoring' },
    knowledge_graph: { emoji: '🔗', label: 'KGraph', desc: 'Entity Relations' },
    techstack: { emoji: '📁', label: 'TechStack', desc: 'Architecture' }
};

// Lane spacing for multiple shuttles
const LANE_SPACING = 0.5; // Distance between parallel shuttle lanes

// Map stage key to progress position (matches DNA_STAGES)
const STAGE_PROGRESS = {
    'mining': 0.2,
    'validation': 0.5,
    'knowledge_graph': 0.75,
    'techstack': 1.0,
    'complete': 1.0,
};

class ShuttleManager {
    constructor(scene, spaces) {
        this.scene = scene;
        this.spaces = spaces;
        this.shuttles = new Map(); // id -> RequirementShuttle (legacy full shuttles)
        this.raycaster = new THREE.Raycaster();
        this.mouse = new THREE.Vector2();

        // Zoom state
        this.currentlyEnteredShuttle = null;
        this.isAnimating = false;

        // Voice navigation selection state
        this.selectedShuttleId = null;

        // Lane assignment counter for distributing shuttles
        this.shuttleCount = 0;

        // PHASE 13: Stage-specific shuttles grouped by checkpoint
        // Each checkpoint (mining, validation, knowledge_graph, techstack) has its own shuttle stack
        this.checkpointShuttles = {
            mining: [],
            validation: [],
            knowledge_graph: [],
            techstack: []
        };

        // Group for checkpoint icon sprites (shared across shuttles)
        this.checkpointGroup = new THREE.Group();
        this.checkpointGroup.name = 'checkpoint-icons';
        this.scene.add(this.checkpointGroup);
        this.checkpointsCreated = false;

        // Store positions for curve creation
        this.ideasPos = spaces.ideas.position.clone();
        this.projectsPos = new THREE.Vector3(10, 0, 7); // Projects Space position

        // Default path from Ideas center to Projects (used for checkpoints)
        this.ideasToProjectsCurve = new THREE.QuadraticBezierCurve3(
            this.ideasPos,
            new THREE.Vector3(
                (this.ideasPos.x + this.projectsPos.x) / 2,   // 5
                4.5,                                           // Higher arc
                (this.ideasPos.z + this.projectsPos.z) / 2    // 3.5
            ),
            this.projectsPos
        );

        // Create shared checkpoint icons along the path
        this.createCheckpointIcons();

        // Bind click handler
        this.onClick = this.onClick.bind(this);
    }

    /**
     * Calculate lane offset for a shuttle to prevent overlapping
     * Distributes shuttles across lanes: 0, +1, -1, +2, -2, etc.
     */
    getLaneOffset(shuttleIndex) {
        if (shuttleIndex === 0) return 0;
        const lane = shuttleIndex % 2 === 0
            ? shuttleIndex / 2
            : -Math.ceil(shuttleIndex / 2);
        return lane * LANE_SPACING;
    }

    /**
     * Find a bubble's position by name or ID
     * @param {string} bubbleName - Name of the bubble to find
     * @param {string} bubbleId - ID of the bubble to find
     * @returns {THREE.Vector3} Position of the bubble, or Ideas Space center if not found
     */
    findBubblePosition(bubbleName, bubbleId) {
        // Try to find the bubble in the Ideas Space
        if (this.spaces.ideas && this.spaces.ideas.objects) {
            console.log(`[ShuttleManager] Searching for bubble: name="${bubbleName}", id="${bubbleId}" in ${this.spaces.ideas.objects.length} objects`);

            for (const obj of this.spaces.ideas.objects) {
                const userData = obj.userData || {};

                // Match by ID first
                if (bubbleId && (userData.id === bubbleId || userData.db_id === bubbleId)) {
                    // Get WORLD position (accounts for parent group transforms)
                    const worldPos = new THREE.Vector3();
                    obj.getWorldPosition(worldPos);
                    console.log(`[ShuttleManager] Found bubble by ID: ${userData.title} local:`, obj.position, 'world:', worldPos);
                    return worldPos;
                }
                // Match by name
                if (bubbleName && userData.title) {
                    const objName = userData.title.toLowerCase();
                    const searchName = bubbleName.toLowerCase();
                    if (objName.includes(searchName) || searchName.includes(objName)) {
                        // Get WORLD position (accounts for parent group transforms)
                        const worldPos = new THREE.Vector3();
                        obj.getWorldPosition(worldPos);
                        console.log(`[ShuttleManager] Found bubble by name: ${userData.title} local:`, obj.position, 'world:', worldPos);
                        return worldPos;
                    }
                }
            }

            // Debug: log all available bubbles
            console.log('[ShuttleManager] Available bubbles:');
            this.spaces.ideas.objects.forEach((obj, i) => {
                const ud = obj.userData || {};
                console.log(`  [${i}] id=${ud.id}, db_id=${ud.db_id}, title="${ud.title}"`);
            });
        } else {
            console.warn('[ShuttleManager] spaces.ideas.objects not available');
        }

        // Fallback: return Ideas Space center
        console.warn(`[ShuttleManager] Bubble not found: ${bubbleName || bubbleId}, using Ideas Space center`);
        return this.ideasPos.clone();
    }

    /**
     * Create a curve from a bubble position to Projects Space
     * @param {THREE.Vector3} startPos - Starting position (bubble)
     * @returns {THREE.QuadraticBezierCurve3} The curve for this shuttle
     */
    createShuttleCurve(startPos) {
        // Calculate control point for a nice arc
        const midX = (startPos.x + this.projectsPos.x) / 2;
        const midZ = (startPos.z + this.projectsPos.z) / 2;

        // Arc height proportional to distance (min 3, max 5)
        const distance = startPos.distanceTo(this.projectsPos);
        const arcHeight = Math.min(5, Math.max(3, distance * 0.4));

        return new THREE.QuadraticBezierCurve3(
            startPos.clone(),  // Clone to prevent reference issues
            new THREE.Vector3(midX, arcHeight, midZ),
            this.projectsPos.clone()  // Clone to prevent reference issues
        );
    }

    /**
     * Create shared checkpoint icons along the path (called once)
     */
    createCheckpointIcons() {
        if (this.checkpointsCreated) return;

        DNA_STAGES.forEach((stage, index) => {
            const pos = this.ideasToProjectsCurve.getPoint(stage.position);

            // Create canvas-based sprite for icon
            const sprite = this.createIconSprite(stage.key, pos);
            this.checkpointGroup.add(sprite);
        });

        this.checkpointsCreated = true;
        console.log('[ShuttleManager] Created checkpoint icons along path');
    }

    /**
     * Create an icon sprite using canvas
     */
    createIconSprite(stageKey, position) {
        const config = CHECKPOINT_ICONS[stageKey];
        if (!config) return null;

        const canvas = document.createElement('canvas');
        canvas.width = 128;
        canvas.height = 128;
        const ctx = canvas.getContext('2d');

        // Background circle (semi-transparent)
        ctx.beginPath();
        ctx.arc(64, 64, 50, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(40, 60, 80, 0.6)';
        ctx.fill();
        ctx.strokeStyle = 'rgba(100, 200, 255, 0.8)';
        ctx.lineWidth = 3;
        ctx.stroke();

        // Draw emoji icon (large)
        ctx.font = '48px Arial';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(config.emoji, 64, 54);

        // Draw label (small, below)
        ctx.font = 'bold 14px Arial';
        ctx.fillStyle = '#ffffff';
        ctx.fillText(config.label, 64, 100);

        const texture = new THREE.CanvasTexture(canvas);
        const material = new THREE.SpriteMaterial({
            map: texture,
            transparent: true,
            depthWrite: false
        });

        const sprite = new THREE.Sprite(material);
        sprite.position.copy(position);
        sprite.position.y += 0.6; // Position above the path
        sprite.scale.set(0.8, 0.8, 1);
        sprite.userData = {
            stageKey: stageKey,
            isCheckpoint: true
        };

        return sprite;
    }

    /**
     * Create a new shuttle for a bubble's requirements
     */
    createShuttle(data) {
        const { id, bubbleName, bubbleId, startPosition, totalRequirements, batchCount, score, passed, failed, status, currentStage } = data;

        if (this.shuttles.has(id)) {
            console.warn(`[ShuttleManager] Shuttle ${id} already exists`);
            return this.shuttles.get(id);
        }

        // ALWAYS prefer actual bubble mesh world position over stored position
        // This ensures shuttle starts exactly where bubble is visually rendered
        let bubblePosition = null;

        // First, try to get position from actual rendered bubble mesh
        if (this.spaces.ideas && this.spaces.ideas.objects) {
            const bubbleMesh = this.spaces.ideas.objects.find(obj => {
                const ud = obj.userData || {};
                return ud.db_id === bubbleId || ud.id === bubbleId ||
                       (bubbleName && ud.title && ud.title.toLowerCase().includes(bubbleName.toLowerCase()));
            });
            if (bubbleMesh) {
                bubblePosition = new THREE.Vector3();
                bubbleMesh.getWorldPosition(bubblePosition);
                console.log(`[ShuttleManager] Using ACTUAL bubble mesh position for "${bubbleName}":`,
                    `(${bubblePosition.x.toFixed(2)}, ${bubblePosition.y.toFixed(2)}, ${bubblePosition.z.toFixed(2)})`);
            }
        }

        // Fallback to stored startPosition if bubble mesh not found
        if (!bubblePosition && startPosition && startPosition.x !== undefined) {
            bubblePosition = new THREE.Vector3(startPosition.x, startPosition.y, startPosition.z);
            console.log(`[ShuttleManager] Fallback to stored position for "${bubbleName}":`, bubblePosition);
        }

        // Last fallback: use findBubblePosition or Ideas Space center
        if (!bubblePosition) {
            bubblePosition = this.findBubblePosition(bubbleName, bubbleId);
            console.log(`[ShuttleManager] Fallback to findBubblePosition for "${bubbleName}":`, bubblePosition);
        }

        // Create a custom curve from this bubble to Projects Space
        const shuttleCurve = this.createShuttleCurve(bubblePosition);

        // Assign lane offset to prevent overlapping
        const laneOffset = this.getLaneOffset(this.shuttleCount);
        this.shuttleCount++;

        const shuttle = new RequirementShuttle(
            this.scene,
            shuttleCurve,  // Use custom curve from bubble position
            {
                id,
                bubbleName,
                bubbleId,
                totalRequirements,
                batchCount: batchCount || 4, // DNA stages = 4
                score: score || 0,
                passed: passed || 0,
                failed: failed || 0,
                status: status || 'launching',
                currentStage: currentStage || 'mining',
                laneOffset: laneOffset,
                startPosition: bubblePosition.clone() // Store for reference
            }
        );

        // If shuttle has existing progress, restore its position
        if (currentStage && STAGE_PROGRESS[currentStage]) {
            shuttle.animateToProgress(STAGE_PROGRESS[currentStage]);
            shuttle.highlightStage(currentStage);
        } else if (score > 0) {
            shuttle.animateToScore(score);
        }

        this.shuttles.set(id, shuttle);
        console.log(`[ShuttleManager] Created shuttle: ${id} for ${bubbleName} from (${bubblePosition.x.toFixed(1)}, ${bubblePosition.y.toFixed(1)}, ${bubblePosition.z.toFixed(1)}) (lane: ${laneOffset}, stage: ${currentStage || 'mining'})`);

        return shuttle;
    }

    // ========================================================================
    // PHASE 13: STAGE-SPECIFIC SHUTTLE METHODS
    // ========================================================================

    /**
     * Create a stage-specific shuttle parked at a checkpoint.
     *
     * These shuttles don't travel - they stay at their designated checkpoint.
     * Multiple shuttles from different bubbles can stack at the same checkpoint.
     *
     * @param {Object} data - Shuttle data from Python backend
     * @param {string} data.shuttle_id - Unique shuttle ID
     * @param {string} data.bubble_id - Source bubble ID
     * @param {string} data.bubble_name - Source bubble name
     * @param {string} data.stage_type - One of: 'mining', 'validation', 'knowledge_graph', 'techstack'
     * @param {Object} data.stage_data - Stage-specific data
     * @returns {RequirementShuttle} The created shuttle
     */
    createStageShuttle(data) {
        const { shuttle_id, bubble_id, bubble_name, stage_type, stage_data } = data;

        // Validate stage type
        if (!this.checkpointShuttles[stage_type]) {
            console.warn(`[ShuttleManager] Invalid stage_type: ${stage_type}`);
            return null;
        }

        // Check if this shuttle already exists
        const existing = this.getStageShuttle(shuttle_id);
        if (existing) {
            console.warn(`[ShuttleManager] Stage shuttle ${shuttle_id} already exists`);
            return existing;
        }

        // Get the checkpoint position for this stage
        const stage = DNA_STAGES.find(s => s.key === stage_type);
        if (!stage) {
            console.warn(`[ShuttleManager] Stage not found: ${stage_type}`);
            return null;
        }

        // Calculate stack offset (multiple shuttles at same checkpoint stack vertically)
        const existingCount = this.checkpointShuttles[stage_type].length;
        const stackOffset = existingCount * 0.35; // Stack vertically

        // Get checkpoint position on the curve
        const checkpointPos = this.ideasToProjectsCurve.getPoint(stage.position);

        // Apply stack offset (vertical stacking)
        checkpointPos.y += stackOffset;

        // Calculate horizontal offset based on bubble (so shuttles from same bubble align horizontally)
        const bubbleHash = this.hashString(bubble_id || bubble_name);
        const horizontalOffset = ((bubbleHash % 5) - 2) * 0.25; // -0.5 to +0.5 range
        const tangent = this.ideasToProjectsCurve.getTangent(stage.position);
        const perpendicular = new THREE.Vector3(-tangent.z, 0, tangent.x).normalize();
        checkpointPos.add(perpendicular.multiplyScalar(horizontalOffset));

        // Create shuttle data
        const shuttleData = {
            id: shuttle_id,
            bubbleName: bubble_name,
            bubbleId: bubble_id,
            stageType: stage_type,
            stageData: stage_data,
            score: stage_data?.average_score || 0,
            passed: stage_data?.passed || 0,
            failed: stage_data?.failed || 0,
            total: stage_data?.total || stage_data?.total_extracted || 0,
            status: 'parked', // Stage shuttles don't travel
            currentStage: stage_type,
            isStageShuttle: true
        };

        // Create the shuttle mesh at the checkpoint position
        const shuttle = new RequirementShuttle(
            this.scene,
            null, // No curve - parked at checkpoint
            shuttleData
        );

        // Override position to be at checkpoint
        shuttle.mesh.position.copy(checkpointPos);
        shuttle.progress = stage.position;
        shuttle.targetProgress = stage.position;

        // Store in checkpoint group
        this.checkpointShuttles[stage_type].push(shuttle);

        // Also add to main shuttles map for unified access
        this.shuttles.set(shuttle_id, shuttle);

        console.log(`[ShuttleManager] Created stage shuttle: ${shuttle_id} (${stage_type}) for ${bubble_name} at y=${checkpointPos.y.toFixed(1)}`);

        return shuttle;
    }

    /**
     * Get a stage shuttle by ID
     */
    getStageShuttle(shuttleId) {
        return this.shuttles.get(shuttleId);
    }

    /**
     * Get all shuttles at a specific checkpoint
     */
    getCheckpointShuttles(stageType) {
        return this.checkpointShuttles[stageType] || [];
    }

    /**
     * Get all stage shuttles for a specific bubble
     */
    getBubbleStageShuttles(bubbleId) {
        const shuttles = [];
        for (const stageType of Object.keys(this.checkpointShuttles)) {
            for (const shuttle of this.checkpointShuttles[stageType]) {
                if (shuttle.data.bubbleId === bubbleId) {
                    shuttles.push(shuttle);
                }
            }
        }
        return shuttles;
    }

    /**
     * Remove a stage shuttle
     */
    removeStageShuttle(shuttleId) {
        const shuttle = this.shuttles.get(shuttleId);
        if (!shuttle) return false;

        // Remove from checkpoint group
        const stageType = shuttle.data.stageType;
        if (stageType && this.checkpointShuttles[stageType]) {
            const index = this.checkpointShuttles[stageType].findIndex(s => s.data.id === shuttleId);
            if (index !== -1) {
                this.checkpointShuttles[stageType].splice(index, 1);
            }
        }

        // Remove from main map
        this.shuttles.delete(shuttleId);

        // Dispose
        shuttle.dispose();

        console.log(`[ShuttleManager] Removed stage shuttle: ${shuttleId}`);
        return true;
    }

    /**
     * Remove all stage shuttles for a bubble
     */
    removeBubbleStageShuttles(bubbleId) {
        let removed = 0;
        for (const stageType of Object.keys(this.checkpointShuttles)) {
            const shuttles = this.checkpointShuttles[stageType];
            for (let i = shuttles.length - 1; i >= 0; i--) {
                if (shuttles[i].data.bubbleId === bubbleId) {
                    const shuttle = shuttles[i];
                    shuttles.splice(i, 1);
                    this.shuttles.delete(shuttle.data.id);
                    shuttle.dispose();
                    removed++;
                }
            }
        }
        console.log(`[ShuttleManager] Removed ${removed} stage shuttles for bubble ${bubbleId}`);
        return removed;
    }

    /**
     * Helper to generate consistent hash from string (for positioning)
     */
    hashString(str) {
        let hash = 0;
        for (let i = 0; i < (str || '').length; i++) {
            const char = str.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash & hash; // Convert to 32bit integer
        }
        return Math.abs(hash);
    }

    /**
     * Update shuttle stage data (when refreshed from API)
     */
    updateStageShuttleData(shuttleId, stageData) {
        const shuttle = this.shuttles.get(shuttleId);
        if (!shuttle) return false;

        shuttle.data.stageData = stageData;
        shuttle.data.score = stageData?.average_score || stageData?.score || 0;
        shuttle.data.passed = stageData?.passed || 0;
        shuttle.data.failed = stageData?.failed || 0;
        shuttle.data.total = stageData?.total || stageData?.total_extracted || 0;

        // Update color based on new score
        shuttle.updateColor();

        console.log(`[ShuttleManager] Updated stage shuttle data: ${shuttleId}`);
        return true;
    }

    /**
     * Update shuttle progress when a batch completes
     */
    updateBatchProgress(shuttleId, batchIndex, batchResults) {
        const shuttle = this.shuttles.get(shuttleId);
        if (!shuttle) return;

        shuttle.updateBatchStatus(batchIndex, 'complete');

        // Accumulate results
        if (batchResults) {
            shuttle.data.passed += batchResults.passed || 0;
            shuttle.data.failed += batchResults.failed || 0;
        }
    }

    /**
     * Update shuttle with final evaluation results
     */
    updateShuttleComplete(shuttleId, results) {
        const shuttle = this.shuttles.get(shuttleId);
        if (!shuttle) return;

        const { score, passed, failed } = results;

        shuttle.data.score = score;
        shuttle.data.passed = passed;
        shuttle.data.failed = failed;
        shuttle.data.status = score >= 0.7 ? 'arrived' : 'needs_work';

        // Animate to final position
        shuttle.animateToScore(score);

        console.log(`[ShuttleManager] Shuttle ${shuttleId} complete: score=${score}, passed=${passed}, failed=${failed}`);
    }

    /**
     * Update shuttle's current DNA pipeline stage
     */
    updateShuttleStage(shuttleId, stageKey) {
        const shuttle = this.shuttles.get(shuttleId);
        if (!shuttle) return;

        const stage = DNA_STAGES.find(s => s.key === stageKey);
        if (!stage) {
            console.warn(`[ShuttleManager] Unknown stage: ${stageKey}`);
            return;
        }

        shuttle.data.currentStage = stageKey;
        shuttle.highlightStage(stageKey);
        shuttle.animateToProgress(stage.position);

        console.log(`[ShuttleManager] Shuttle ${shuttleId} stage: ${stage.name} (${stage.icon})`);
    }

    /**
     * Get shuttle by ID
     */
    getShuttle(id) {
        return this.shuttles.get(id);
    }

    /**
     * Get all active shuttles
     */
    getAllShuttles() {
        return Array.from(this.shuttles.values());
    }

    /**
     * Remove a shuttle
     */
    removeShuttle(id) {
        const shuttle = this.shuttles.get(id);
        if (shuttle) {
            shuttle.dispose();
            this.shuttles.delete(id);
        }
    }

    /**
     * Handle click events for shuttle interaction
     */
    onClick(event, camera) {
        // Don't process clicks during animation
        if (this.isAnimating) return false;

        // Calculate mouse position in normalized device coordinates
        const rect = event.target.getBoundingClientRect();
        this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
        this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

        this.raycaster.setFromCamera(this.mouse, camera);

        // Check intersections with shuttle meshes (recursive for grouped meshes)
        const shuttleMeshes = Array.from(this.shuttles.values()).map(s => s.mesh);
        const intersects = this.raycaster.intersectObjects(shuttleMeshes, true);

        if (intersects.length > 0) {
            // Find the parent shuttle group from the clicked child mesh
            let clickedObject = intersects[0].object;

            // Walk up to find the shuttle group
            while (clickedObject && !clickedObject.userData.isShuttle) {
                clickedObject = clickedObject.parent;
            }

            if (clickedObject && clickedObject.userData.isShuttle) {
                const shuttleId = clickedObject.userData.shuttleId;
                const shuttle = this.shuttles.get(shuttleId);

                if (shuttle) {
                    this.onShuttleClick(shuttle);
                    return true; // Event handled
                }
            }
        }

        return false;
    }

    /**
     * Handle shuttle click - show info and optionally transfer to Alice
     */
    onShuttleClick(shuttle) {
        console.log(`[ShuttleManager] Shuttle clicked: ${shuttle.data.id}`);

        // Dispatch event for UI to show info panel
        window.dispatchEvent(new CustomEvent('shuttle-clicked', {
            detail: shuttle.data
        }));

        // Notify Python backend
        if (window.vibemind && window.vibemind.sendToPython) {
            window.vibemind.sendToPython({
                type: 'shuttle_clicked',
                shuttle_id: shuttle.data.id,
                bubble_name: shuttle.data.bubbleName,
                score: shuttle.data.score
            });
        }
    }

    /**
     * Update all shuttles (call in animation loop)
     */
    update(deltaTime, elapsedTime) {
        for (const shuttle of this.shuttles.values()) {
            shuttle.update(deltaTime, elapsedTime);
        }
    }

    /**
     * Enter a shuttle with zoom animation (like bubble entry)
     * @param {string} shuttleId - ID of shuttle to enter
     * @param {THREE.Camera} camera - Main camera
     * @param {OrbitControls} controls - Orbit controls
     * @param {Function} onComplete - Callback when animation completes
     */
    enterShuttleWithAnimation(shuttleId, camera, controls, onComplete) {
        const shuttle = this.shuttles.get(shuttleId);
        if (!shuttle) {
            console.warn(`[ShuttleManager] Shuttle ${shuttleId} not found`);
            return;
        }

        this.currentlyEnteredShuttle = shuttle;
        this.isAnimating = true;

        const duration = 800; // ms
        const startTime = performance.now();

        // Store starting positions
        const startPos = camera.position.clone();
        const startTarget = controls.target.clone();

        // Calculate target position (just in front of shuttle)
        const shuttleWorldPos = new THREE.Vector3();
        shuttle.mesh.getWorldPosition(shuttleWorldPos);

        const targetPos = shuttleWorldPos.clone();
        targetPos.z += 0.8; // Distance in front of shuttle
        targetPos.y += 0.2; // Slightly above center

        console.log(`[ShuttleManager] Entering shuttle: ${shuttle.data.bubbleName}`);

        const animate = (now) => {
            const elapsed = now - startTime;
            const progress = Math.min(elapsed / duration, 1);

            // Ease-out cubic for smooth deceleration
            const eased = 1 - Math.pow(1 - progress, 3);

            // Interpolate camera position
            camera.position.lerpVectors(startPos, targetPos, eased);
            controls.target.lerpVectors(startTarget, shuttleWorldPos, eased);
            controls.update();

            // Scale up shuttle during zoom (1 → 4x)
            const scale = 1 + eased * 3;
            shuttle.mesh.scale.setScalar(scale);

            // Increase outer glow opacity
            if (shuttle.outerGlowMaterial) {
                shuttle.outerGlowMaterial.opacity = 0.15 + eased * 0.3;
            }

            if (progress < 1) {
                requestAnimationFrame(animate);
            } else {
                this.isAnimating = false;
                console.log(`[ShuttleManager] Entered shuttle: ${shuttle.data.bubbleName}`);

                // Dispatch event for UI to show interior view
                window.dispatchEvent(new CustomEvent('shuttle-entered', {
                    detail: shuttle.data
                }));

                if (onComplete) onComplete(shuttle);
            }
        };

        requestAnimationFrame(animate);
    }

    /**
     * Exit current shuttle with zoom-out animation
     * @param {THREE.Camera} camera - Main camera
     * @param {OrbitControls} controls - Orbit controls
     * @param {THREE.Vector3} returnPosition - Position to return camera to
     * @param {THREE.Vector3} returnTarget - Orbit target to return to
     * @param {Function} onComplete - Callback when animation completes
     */
    exitShuttleWithAnimation(camera, controls, returnPosition, returnTarget, onComplete) {
        const shuttle = this.currentlyEnteredShuttle;
        if (!shuttle) {
            console.warn(`[ShuttleManager] No shuttle to exit`);
            return;
        }

        this.isAnimating = true;

        const duration = 600; // ms
        const startTime = performance.now();

        // Store starting positions
        const startPos = camera.position.clone();
        const startTarget = controls.target.clone();
        const startScale = shuttle.mesh.scale.x;

        console.log(`[ShuttleManager] Exiting shuttle: ${shuttle.data.bubbleName}`);

        const animate = (now) => {
            const elapsed = now - startTime;
            const progress = Math.min(elapsed / duration, 1);

            // Ease-in-out for smooth transition
            const eased = progress < 0.5
                ? 2 * progress * progress
                : 1 - Math.pow(-2 * progress + 2, 2) / 2;

            // Interpolate camera position
            camera.position.lerpVectors(startPos, returnPosition, eased);
            controls.target.lerpVectors(startTarget, returnTarget, eased);
            controls.update();

            // Scale down shuttle back to normal
            const scale = startScale + (1 - startScale) * eased;
            shuttle.mesh.scale.setScalar(scale);

            // Restore outer glow opacity
            if (shuttle.outerGlowMaterial) {
                shuttle.outerGlowMaterial.opacity = 0.45 - eased * 0.3;
            }

            if (progress < 1) {
                requestAnimationFrame(animate);
            } else {
                this.isAnimating = false;
                this.currentlyEnteredShuttle = null;
                console.log(`[ShuttleManager] Exited shuttle`);

                // Dispatch event for UI to hide interior view
                window.dispatchEvent(new CustomEvent('shuttle-exited', {}));

                if (onComplete) onComplete();
            }
        };

        requestAnimationFrame(animate);
    }

    /**
     * Check if currently inside a shuttle
     */
    isInsideShuttle() {
        return this.currentlyEnteredShuttle !== null;
    }

    /**
     * Get currently entered shuttle
     */
    getCurrentShuttle() {
        return this.currentlyEnteredShuttle;
    }

    // ========================================================================
    // VOICE NAVIGATION HELPER METHODS
    // ========================================================================

    /**
     * Get currently selected shuttle (for voice nav)
     */
    getSelectedShuttle() {
        if (this.selectedShuttleId) {
            return this.shuttles.get(this.selectedShuttleId);
        }
        // If no selection, return first shuttle
        const firstShuttle = this.shuttles.values().next().value;
        return firstShuttle || null;
    }

    /**
     * Set the selected shuttle by ID
     */
    setSelectedShuttle(shuttleId) {
        if (this.shuttles.has(shuttleId)) {
            this.selectedShuttleId = shuttleId;
            console.log(`[ShuttleManager] Selected shuttle: ${shuttleId}`);
            return true;
        }
        return false;
    }

    /**
     * Find shuttle by bubble name (fuzzy match)
     */
    findShuttleByName(name) {
        const lowerName = name.toLowerCase();
        for (const shuttle of this.shuttles.values()) {
            const bubbleName = (shuttle.data.bubbleName || '').toLowerCase();
            if (bubbleName.includes(lowerName) || lowerName.includes(bubbleName)) {
                return shuttle;
            }
        }
        return null;
    }

    /**
     * Get list of all shuttles (for voice listing)
     */
    getShuttleList() {
        return Array.from(this.shuttles.values()).map(s => ({
            id: s.data.id,
            bubbleName: s.data.bubbleName,
            score: s.data.score,
            currentStage: s.data.currentStage
        }));
    }

    /**
     * Select next/previous shuttle
     * @param {number} direction - 1 for next, -1 for previous
     */
    selectShuttle(direction) {
        const shuttleIds = Array.from(this.shuttles.keys());
        if (shuttleIds.length === 0) return null;

        const currentIndex = this.selectedShuttleId
            ? shuttleIds.indexOf(this.selectedShuttleId)
            : -1;

        let newIndex = currentIndex + direction;
        if (newIndex < 0) newIndex = shuttleIds.length - 1;
        if (newIndex >= shuttleIds.length) newIndex = 0;

        this.selectedShuttleId = shuttleIds[newIndex];
        const selected = this.shuttles.get(this.selectedShuttleId);
        console.log(`[ShuttleManager] Selected: ${selected.data.bubbleName}`);
        return selected;
    }

    /**
     * Exit current shuttle (voice command handler)
     */
    exitCurrentShuttle() {
        if (!this.currentlyEnteredShuttle) {
            console.log('[ShuttleManager] No shuttle to exit');
            return;
        }

        // Trigger the exit button click in the UI
        const exitBtn = document.getElementById('shuttle-exit-btn');
        if (exitBtn) {
            exitBtn.click();
        }
    }

    /**
     * Dispose of all resources
     */
    dispose() {
        for (const shuttle of this.shuttles.values()) {
            shuttle.dispose();
        }
        this.shuttles.clear();
    }
}


/**
 * RequirementShuttle - Individual shuttle traveling along the path
 */
class RequirementShuttle {
    constructor(scene, curve, data) {
        this.scene = scene;
        this.curve = curve;
        this.data = data;

        // Lane offset for parallel paths (prevents overlapping)
        this.laneOffset = data.laneOffset || 0;

        // Current position on curve (0.0 to 1.0)
        this.progress = 0;
        this.targetProgress = 0;

        // Animation
        this.animationSpeed = 0.5; // Units per second
        this.pulsePhase = Math.random() * Math.PI * 2;

        // Trail effect - stores previous positions
        this.trailPositions = [];
        this.trailMaxLength = 30;

        // Pre-seed trail with TRUE bubble center (no lane offset)
        // Rockets start exactly at their bubble position, then spread to lanes as they travel
        if (this.curve) {
            const bubbleCenter = this.curve.getPoint(0);
            // NO lane offset applied - trail starts at actual bubble center
            this.trailPositions.push(bubbleCenter.clone());
        }

        // Create visual elements
        this.mesh = this.createMesh();
        this.trail = this.createTrail();
        this.label = this.createLabel();

        // Add to scene
        this.scene.add(this.mesh);
        if (this.trail) this.scene.add(this.trail);

        // Initial position
        this.updatePosition();
    }

    createMesh() {
        // Space Shuttle composed from primitives
        const group = new THREE.Group();

        // Get stage color based on current stage
        const stageIndex = DNA_STAGES.findIndex(s => s.key === this.data.currentStage);
        const stageColor = stageIndex >= 0 ? DNA_STAGES[stageIndex].color : 0x66aaff;

        // 1. NOSE CONE (top of rocket)
        const noseMaterial = new THREE.MeshStandardMaterial({
            color: 0xdddddd,
            metalness: 0.7,
            roughness: 0.3,
            emissive: stageColor,
            emissiveIntensity: 0.2
        });
        const noseGeom = new THREE.ConeGeometry(0.06, 0.15, 8);
        const noseMesh = new THREE.Mesh(noseGeom, noseMaterial);
        noseMesh.position.y = 0.175;
        group.add(noseMesh);

        // 2. BODY (main cylinder)
        const bodyMaterial = new THREE.MeshStandardMaterial({
            color: 0xcccccc,
            metalness: 0.6,
            roughness: 0.4,
            emissive: stageColor,
            emissiveIntensity: 0.15
        });
        const bodyGeom = new THREE.CylinderGeometry(0.06, 0.08, 0.2, 8);
        const bodyMesh = new THREE.Mesh(bodyGeom, bodyMaterial);
        group.add(bodyMesh);
        this.bodyMesh = bodyMesh; // Store for color updates
        this.bodyMaterial = bodyMaterial;

        // 3. FINS (4 stabilizer fins)
        const finMaterial = new THREE.MeshStandardMaterial({
            color: stageColor,
            metalness: 0.5,
            roughness: 0.5,
            emissive: stageColor,
            emissiveIntensity: 0.3
        });
        this.finMaterial = finMaterial;

        for (let i = 0; i < 4; i++) {
            const finGeom = new THREE.ConeGeometry(0.025, 0.08, 4);
            const finMesh = new THREE.Mesh(finGeom, finMaterial);
            finMesh.rotation.z = Math.PI; // Point down
            finMesh.position.y = -0.08;
            finMesh.position.x = Math.cos(i * Math.PI / 2) * 0.07;
            finMesh.position.z = Math.sin(i * Math.PI / 2) * 0.07;
            group.add(finMesh);
        }

        // 4. ENGINE BELL (bottom)
        const engineMaterial = new THREE.MeshBasicMaterial({
            color: 0x444444
        });
        const engineGeom = new THREE.CylinderGeometry(0.04, 0.06, 0.05, 8);
        const engineMesh = new THREE.Mesh(engineGeom, engineMaterial);
        engineMesh.position.y = -0.125;
        group.add(engineMesh);

        // 5. ENGINE GLOW (fire effect)
        const glowMaterial = new THREE.MeshBasicMaterial({
            color: 0xff6600,
            transparent: true,
            opacity: 0.7
        });
        const glowGeom = new THREE.ConeGeometry(0.05, 0.12, 8);
        const engineGlow = new THREE.Mesh(glowGeom, glowMaterial);
        engineGlow.rotation.x = Math.PI; // Point down
        engineGlow.position.y = -0.2;
        group.add(engineGlow);
        this.engineGlow = engineGlow;

        // 6. ENGINE POINT LIGHT
        const engineLight = new THREE.PointLight(0xff6600, 0.8, 0.5);
        engineLight.position.y = -0.2;
        group.add(engineLight);
        this.engineLight = engineLight;

        // 7. OUTER GLOW (selection/hover effect)
        const outerGlowMaterial = new THREE.MeshBasicMaterial({
            color: stageColor,
            transparent: true,
            opacity: 0.15
        });
        const outerGlowGeom = new THREE.SphereGeometry(0.2, 16, 16);
        const outerGlow = new THREE.Mesh(outerGlowGeom, outerGlowMaterial);
        group.add(outerGlow);
        this.outerGlow = outerGlow;
        this.outerGlowMaterial = outerGlowMaterial;

        // Store metadata on group
        group.userData.isShuttle = true;
        group.userData.shuttleId = this.data.id;

        return group;
    }

    /**
     * Create a trail effect behind the shuttle
     */
    createTrail() {
        // Get stage color for trail
        const stageIndex = DNA_STAGES.findIndex(s => s.key === this.data.currentStage);
        const trailColor = stageIndex >= 0 ? DNA_STAGES[stageIndex].color : 0x66aaff;

        // Create line geometry for trail
        const positions = new Float32Array(this.trailMaxLength * 3);
        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));

        const material = new THREE.LineBasicMaterial({
            color: trailColor,
            transparent: true,
            opacity: 0.4,
            linewidth: 2
        });

        const trail = new THREE.Line(geometry, material);
        trail.frustumCulled = false;
        this.trailMaterial = material;

        return trail;
    }

    /**
     * Update trail positions
     */
    updateTrail() {
        if (!this.trail) return;

        // Add current position to front of trail
        this.trailPositions.unshift(this.mesh.position.clone());

        // Keep trail at max length
        if (this.trailPositions.length > this.trailMaxLength) {
            this.trailPositions.pop();
        }

        // Update buffer geometry
        const positions = this.trail.geometry.attributes.position.array;
        for (let i = 0; i < this.trailMaxLength; i++) {
            if (i < this.trailPositions.length) {
                positions[i * 3] = this.trailPositions[i].x;
                positions[i * 3 + 1] = this.trailPositions[i].y;
                positions[i * 3 + 2] = this.trailPositions[i].z;
            } else {
                // Fill remaining with last position to avoid artifacts
                const last = this.trailPositions[this.trailPositions.length - 1] || this.mesh.position;
                positions[i * 3] = last.x;
                positions[i * 3 + 1] = last.y;
                positions[i * 3 + 2] = last.z;
            }
        }
        this.trail.geometry.attributes.position.needsUpdate = true;
        this.trail.geometry.setDrawRange(0, this.trailPositions.length);
    }

    createLabel() {
        // Label will be created as HTML overlay in the renderer
        return null;
    }

    updateBatchStatus(batchIndex, status) {
        // Batch status is now handled by shared checkpoint icons
        // Update shuttle's internal state
        this.data.batchStatus = this.data.batchStatus || [];
        this.data.batchStatus[batchIndex] = status;
    }

    /**
     * Highlight a specific DNA stage (update shuttle colors)
     */
    highlightStage(stageKey) {
        // Update shuttle's current stage
        this.data.currentStage = stageKey;

        // Get stage color
        const stage = DNA_STAGES.find(s => s.key === stageKey);
        if (stage) {
            // Update fin and body colors
            if (this.finMaterial) {
                this.finMaterial.color.setHex(stage.color);
                this.finMaterial.emissive.setHex(stage.color);
            }
            if (this.bodyMaterial) {
                this.bodyMaterial.emissive.setHex(stage.color);
            }
            if (this.outerGlowMaterial) {
                this.outerGlowMaterial.color.setHex(stage.color);
            }
            if (this.trailMaterial) {
                this.trailMaterial.color.setHex(stage.color);
            }
        }
    }

    /**
     * Animate to a specific progress value (0.0 to 1.0)
     */
    animateToProgress(progress) {
        this.targetProgress = progress;
    }

    animateToScore(score) {
        this.targetProgress = this.scoreToProgress(score);
    }

    scoreToProgress(score) {
        // Non-linear mapping: faster progress at higher scores
        // This gives visual feedback that high-quality requirements are "closer" to being code-ready
        return 1 - Math.pow(1 - score, 1.5);
    }

    updatePosition() {
        // Stage shuttles (null curve) don't need position updates - they're parked
        if (!this.curve) {
            this.updateTrail();
            return;
        }

        const point = this.curve.getPoint(this.progress);

        // Apply lane offset only AFTER shuttle has started moving (progress > 5%)
        // This ensures rockets start at bubble center, then gradually spread to lanes
        if (this.laneOffset !== 0 && this.progress > 0.05) {
            const tangent = this.curve.getTangent(this.progress);
            // Perpendicular direction in XZ plane
            const perpendicular = new THREE.Vector3(-tangent.z, 0, tangent.x).normalize();
            // Gradually increase lane offset from 0% to 100% between progress 0.05 and 0.15
            const offsetFactor = Math.min(1, (this.progress - 0.05) / 0.1);
            point.add(perpendicular.multiplyScalar(this.laneOffset * offsetFactor));
        }

        this.mesh.position.copy(point);

        // Make shuttle face direction of travel
        if (this.progress < 0.99) {
            const lookAhead = this.curve.getPoint(Math.min(this.progress + 0.01, 1));
            this.mesh.lookAt(lookAhead);
        }

        // Update trail
        this.updateTrail();
    }

    update(deltaTime, elapsedTime) {
        // Animate progress toward target (only for traveling shuttles with curves)
        if (this.curve && Math.abs(this.progress - this.targetProgress) > 0.001) {
            const direction = this.targetProgress > this.progress ? 1 : -1;
            this.progress += direction * this.animationSpeed * deltaTime;

            // Clamp to target
            if (direction > 0 && this.progress > this.targetProgress) {
                this.progress = this.targetProgress;
            } else if (direction < 0 && this.progress < this.targetProgress) {
                this.progress = this.targetProgress;
            }

            this.updatePosition();
        }

        // Pulse effect on overall scale
        const pulse = Math.sin(elapsedTime * 2 + this.pulsePhase) * 0.1 + 1;
        this.mesh.scale.setScalar(pulse);

        // Engine flame flicker
        if (this.engineGlow) {
            const flicker = Math.sin(elapsedTime * 8 + this.pulsePhase) * 0.2 + 0.8;
            this.engineGlow.scale.y = flicker;
            this.engineGlow.material.opacity = 0.5 + flicker * 0.3;
        }

        // Engine light intensity flicker
        if (this.engineLight) {
            this.engineLight.intensity = 0.6 + Math.sin(elapsedTime * 10) * 0.3;
        }

        // Color based on status/stage
        this.updateColor();
    }

    updateColor() {
        const score = this.data.score || 0;
        const currentStage = this.data.currentStage || 'mining';
        let color;

        // Get stage color
        const stageData = DNA_STAGES.find(s => s.key === currentStage);
        const stageColor = stageData ? stageData.color : 0x66aaff;

        if (this.data.status === 'arrived') {
            color = 0x44ff88; // Green - arrived at projects
        } else if (this.data.status === 'needs_work') {
            color = 0xffaa44; // Orange - needs clarification
        } else if (score >= 0.7) {
            color = 0x88ff88; // Light green - passing
        } else {
            color = stageColor; // Stage color
        }

        // Update fin material color
        if (this.finMaterial) {
            this.finMaterial.color.setHex(color);
            this.finMaterial.emissive.setHex(color);
        }

        // Update body emissive
        if (this.bodyMaterial) {
            this.bodyMaterial.emissive.setHex(color);
        }

        // Update outer glow
        if (this.outerGlowMaterial) {
            this.outerGlowMaterial.color.setHex(color);
        }
    }

    dispose() {
        this.scene.remove(this.mesh);
        if (this.trail) {
            this.scene.remove(this.trail);
            this.trail.geometry.dispose();
            this.trail.material.dispose();
        }

        // Dispose all children in the group
        this.mesh.traverse((child) => {
            if (child.geometry) child.geometry.dispose();
            if (child.material) {
                if (Array.isArray(child.material)) {
                    child.material.forEach(m => m.dispose());
                } else {
                    child.material.dispose();
                }
            }
        });

        // Clear trail positions
        this.trailPositions = [];
    }
}

// Export for use in multiverse.js
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { ShuttleManager, RequirementShuttle };
}
