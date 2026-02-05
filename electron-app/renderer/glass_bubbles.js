/**
 * VibeMind Glass Bubble Multiverse
 *
 * Three.js visualization module for Electron app.
 * Renders glass teardrop bubbles with selection and navigation support.
 */

// Easing functions for smooth animations
const Easing = {
    easeInOutCubic: (t) => {
        return t < 0.5
            ? 4 * t * t * t
            : 1 - Math.pow(-2 * t + 2, 3) / 2;
    },
    easeOutQuart: (t) => {
        return 1 - Math.pow(1 - t, 4);
    },
    easeInOutQuad: (t) => {
        return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
    }
};

class MultiverseApp {
    constructor(container) {
        this.container = container || document.getElementById('canvas-container');
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.controls = null;
        this.bubbles = [];
        this.hoveredBubble = null;
        this.selectedBubble = null;
        this.raycaster = null;
        this.mouse = null;
        this.clock = null;
        this.animationId = null;

        // Camera animation state
        this.cameraAnimation = null;
        this.savedCameraPosition = null;
        this.savedCameraTarget = null;

        // Canvas nodes and rich content renderer
        this.canvasNodes = new Map(); // bubbleId -> Map of nodeId -> nodeData
        this.richContentRenderer = null;
        this.currentBubbleId = null; // Currently entered bubble

        this.init();
    }

    // Wait for container to have valid dimensions
    async waitForDimensions() {
        return new Promise((resolve) => {
            const check = () => {
                if (this.container.clientWidth > 0 && this.container.clientHeight > 0) {
                    resolve();
                } else {
                    requestAnimationFrame(check);
                }
            };
            check();
        });
    }

    async init() {
        try {
            // Diagnostic logging
            console.log('[MultiverseApp] ========== INIT START ==========');
            console.log('[MultiverseApp] THREE loaded:', typeof THREE !== 'undefined');
            if (typeof THREE !== 'undefined') {
                console.log('[MultiverseApp] THREE.WebGLRenderer:', typeof THREE.WebGLRenderer);
                console.log('[MultiverseApp] THREE.Scene:', typeof THREE.Scene);
            }
            console.log('[MultiverseApp] OrbitControls:', typeof THREE !== 'undefined' && typeof THREE.OrbitControls !== 'undefined');

            // Check THREE.js is loaded
            if (typeof THREE === 'undefined') {
                console.error('[MultiverseApp] THREE.js not loaded!');
                return;
            }

            // Wait for valid container dimensions
            await this.waitForDimensions();

            const width = this.container.clientWidth;
            const height = this.container.clientHeight;
            console.log('[MultiverseApp] Container dimensions:', width, 'x', height);

            // Scene
            this.scene = new THREE.Scene();
            this.scene.background = new THREE.Color(0x050510);

            // Camera with validated dimensions
            this.camera = new THREE.PerspectiveCamera(60, width / height, 0.1, 100);
            this.camera.position.set(0, 0, 8);

            // Renderer - no alpha for reliable rendering with non-transparent window
            this.renderer = new THREE.WebGLRenderer({
                antialias: true,
                alpha: false,
                powerPreference: "high-performance"
            });
            this.renderer.setSize(width, height);
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        this.renderer.physicallyCorrectLights = true;
        this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
        this.renderer.toneMappingExposure = 1.8;
        this.renderer.outputEncoding = THREE.sRGBEncoding;

        this.container.appendChild(this.renderer.domElement);

        // Controls (if OrbitControls available)
        if (THREE.OrbitControls) {
            this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
            this.controls.enableDamping = true;
            this.controls.dampingFactor = 0.05;
            this.controls.maxDistance = 20;
            this.controls.minDistance = 3;
        }

        // Raycaster
        this.raycaster = new THREE.Raycaster();
        this.mouse = new THREE.Vector2();

        // Clock
        this.clock = new THREE.Clock();

        // Setup
        await this.createEnvironment();
        this.setupLighting();
        // Don't create default bubbles - bubbles come from database via Python
        // this.createDefaultBubbles();
        this.createBackgroundParticles();

        // Initialize rich content renderer for canvas nodes
        this.initializeRichContentRenderer();

        // Events
        window.addEventListener('resize', () => this.onWindowResize());
        this.renderer.domElement.addEventListener('mousemove', (e) => this.onMouseMove(e));
        this.renderer.domElement.addEventListener('click', (e) => this.onClick(e));

        // Canvas node event handlers
        this.setupCanvasNodeEventHandlers();

            // Start animation
            this.animate();

            console.log('[MultiverseApp] Initialized successfully!');
            console.log('[MultiverseApp] Bubbles created:', this.bubbles.length);
        } catch (error) {
            console.error('[MultiverseApp] Initialization failed:', error);
        }
    }

    async createEnvironment() {
        const pmremGenerator = new THREE.PMREMGenerator(this.renderer);
        pmremGenerator.compileEquirectangularShader();
        this.scene.environment = pmremGenerator.fromScene(new THREE.Scene()).texture;
    }

    setupLighting() {
        // Ambient
        const ambient = new THREE.AmbientLight(0x6080a0, 0.8);
        this.scene.add(ambient);

        // Key light
        const keyLight = new THREE.DirectionalLight(0xffffff, 2.0);
        keyLight.position.set(5, 5, 5);
        this.scene.add(keyLight);

        // Fill light
        const fillLight = new THREE.DirectionalLight(0xaaccff, 0.8);
        fillLight.position.set(-5, 0, 2);
        this.scene.add(fillLight);

        // Rim light
        const rimLight = new THREE.DirectionalLight(0xffaaaa, 0.6);
        rimLight.position.set(0, -3, -5);
        this.scene.add(rimLight);

        // Top light
        const topLight = new THREE.DirectionalLight(0xffffff, 1.0);
        topLight.position.set(0, 10, 0);
        this.scene.add(topLight);

        // Point lights for sparkle
        const sparkleLight1 = new THREE.PointLight(0x4488ff, 1.5, 15);
        sparkleLight1.position.set(-3, 2, 2);
        this.scene.add(sparkleLight1);

        const sparkleLight2 = new THREE.PointLight(0xff4488, 1.5, 15);
        sparkleLight2.position.set(3, -1, -2);
        this.scene.add(sparkleLight2);

        const sparkleLight3 = new THREE.PointLight(0x44ff88, 1.0, 12);
        sparkleLight3.position.set(0, -2, 3);
        this.scene.add(sparkleLight3);
    }

    createTeardropGeometry(radius = 1, segments = 64) {
        const points = [];
        const steps = 48;

        for (let i = 0; i <= steps; i++) {
            const t = i / steps;
            const angle = t * Math.PI;
            const a = radius * 0.5;
            const teardropR = a * (1 - Math.cos(angle));
            const x = teardropR * Math.sin(angle);
            const y = -teardropR * Math.cos(angle) * 1.3 + radius * 0.3;

            if (x >= 0) {
                points.push(new THREE.Vector2(x, y));
            }
        }

        points.push(new THREE.Vector2(0, radius * 1.0));

        const geometry = new THREE.LatheGeometry(points, segments);
        geometry.computeVertexNormals();
        return geometry;
    }

    createGlassMaterial(color, isHovered = false, isSelected = false) {
        const material = new THREE.MeshPhysicalMaterial({
            color: color,
            metalness: 0.1,
            roughness: 0.02,
            transmission: 0.85,
            thickness: 0.8,
            ior: 1.45,
            reflectivity: 0.8,
            clearcoat: 1.0,
            clearcoatRoughness: 0.05,
            envMapIntensity: 1.5,
            transparent: true,
            opacity: 0.9,
            side: THREE.DoubleSide,
            emissive: new THREE.Color(color),
            emissiveIntensity: 0.15,
        });

        if (isHovered) {
            material.emissiveIntensity = 0.4;
        }
        if (isSelected) {
            material.emissive = new THREE.Color(0xffffff);
            material.emissiveIntensity = 0.5;
        }

        return material;
    }

    createDefaultBubbles() {
        // DISABLED: Default bubbles are no longer created
        // Bubbles are loaded from database via Python backend
        // Keep method for backwards compatibility but don't create anything
        console.log('[MultiverseApp] Default bubbles disabled - waiting for database bubbles');
        return;
        
        // Original code (disabled):
        // const defaultData = [
        //     { id: 1, title: "Universe A", position: { x: -2, y: 0.5, z: 0 }, color: 0x66aaff, radius: 0.8 },
        //     { id: 2, title: "Universe B", position: { x: 2, y: -0.5, z: -1 }, color: 0xff66aa, radius: 0.7 },
        //     { id: 3, title: "Universe C", position: { x: 0, y: 1.5, z: 1 }, color: 0x66ffaa, radius: 0.6 },
        //     { id: 4, title: "Research Hub", position: { x: -1, y: -1, z: 2 }, color: 0xffcc66, radius: 0.75 },
        //     { id: 5, title: "Creative Space", position: { x: 1.5, y: 0, z: -2 }, color: 0xcc66ff, radius: 0.65 },
        // ];
        // defaultData.forEach(data => this.addBubble(data));
    }

    addBubble(data) {
        const geometry = this.createTeardropGeometry(1, 48);
        const material = this.createGlassMaterial(data.color);
        const mesh = new THREE.Mesh(geometry, material);

        mesh.position.set(data.position.x, data.position.y, data.position.z);
        mesh.scale.setScalar(data.radius);

        mesh.userData = {
            id: data.id,
            db_id: data.db_id || data.id,  // Store DB UUID separately if provided
            title: data.title,
            numbered_title: data.numbered_title || data.title,  // Store numbered title for navigation
            baseColor: data.color,
            baseRadius: data.radius,
            shimmerPhase: Math.random() * Math.PI * 2,
            floatPhase: Math.random() * Math.PI * 2,
            rotationSpeed: 0.1 + Math.random() * 0.2,
        };

        this.scene.add(mesh);
        this.bubbles.push(mesh);
        console.log('[MultiverseApp] Added bubble:', data.id, 'title:', data.title, 'numbered_title:', mesh.userData.numbered_title, 'db_id:', mesh.userData.db_id);
        return mesh;
    }

    removeBubble(id) {
        console.log('[MultiverseApp] removeBubble called with id:', id, 'type:', typeof id);
        console.log('[MultiverseApp] Current bubbles:', this.bubbles.map(b => ({
            id: b.userData.id,
            db_id: b.userData.db_id,
            title: b.userData.title
        })));
        
        // Try to find by direct ID match first
        let index = this.bubbles.findIndex(b => b.userData.id === id);
        
        // If not found, try db_id
        if (index === -1) {
            index = this.bubbles.findIndex(b => b.userData.db_id === id);
        }
        
        // If still not found, try string conversion for integer/string mismatch
        if (index === -1) {
            index = this.bubbles.findIndex(b => String(b.userData.id) === String(id));
        }
        
        // If still not found, try title match (fallback)
        if (index === -1 && typeof id === 'string') {
            index = this.bubbles.findIndex(b => 
                b.userData.title && b.userData.title.toLowerCase() === id.toLowerCase()
            );
        }
        
        if (index !== -1) {
            const bubble = this.bubbles[index];
            console.log('[MultiverseApp] Removing bubble:', bubble.userData.title, 'id:', bubble.userData.id);
            this.scene.remove(bubble);
            bubble.geometry.dispose();
            bubble.material.dispose();
            this.bubbles.splice(index, 1);
            return true;
        } else {
            console.warn('[MultiverseApp] Bubble not found for removal:', id);
            return false;
        }
    }

    updateBubble(id, updates) {
        // Find the bubble by id or db_id
        let bubble = this.bubbles.find(b => b.userData.id === id || b.userData.db_id === id);

        if (!bubble && typeof id === 'string') {
            // Try string conversion
            bubble = this.bubbles.find(b => String(b.userData.id) === id || String(b.userData.db_id) === id);
        }

        if (bubble) {
            console.log('[MultiverseApp] Updating bubble:', bubble.userData.title, '->', updates);

            // Update title if provided
            if (updates.title) {
                bubble.userData.title = updates.title;
                // Only update numbered_title from title if not explicitly provided
                if (!updates.numbered_title) {
                    bubble.userData.numbered_title = updates.title;
                }
            }

            // Update numbered_title independently (for voice index display)
            if (updates.numbered_title) {
                bubble.userData.numbered_title = updates.numbered_title;
            }

            // Update voice index for reference
            if (updates.voice_index !== undefined) {
                bubble.userData.voice_index = updates.voice_index;
            }

            // Update position if provided
            if (updates.position) {
                bubble.position.set(updates.position.x, updates.position.y, updates.position.z);
            }

            // Update color if provided
            if (updates.color) {
                bubble.userData.baseColor = updates.color;
                // Recreate material with new color
                const newMaterial = this.createGlassMaterial(updates.color);
                bubble.material.dispose();
                bubble.material = newMaterial;
            }

            return true;
        } else {
            console.warn('[MultiverseApp] Bubble not found for update:', id);
            return false;
        }
    }

    createBackgroundParticles() {
        const particleCount = 500;
        const positions = new Float32Array(particleCount * 3);
        const colors = new Float32Array(particleCount * 3);

        for (let i = 0; i < particleCount; i++) {
            const radius = 15 + Math.random() * 20;
            const theta = Math.random() * Math.PI * 2;
            const phi = Math.acos(2 * Math.random() - 1);

            positions[i * 3] = radius * Math.sin(phi) * Math.cos(theta);
            positions[i * 3 + 1] = radius * Math.sin(phi) * Math.sin(theta);
            positions[i * 3 + 2] = radius * Math.cos(phi);

            colors[i * 3] = 0.3 + Math.random() * 0.3;
            colors[i * 3 + 1] = 0.3 + Math.random() * 0.3;
            colors[i * 3 + 2] = 0.5 + Math.random() * 0.5;
        }

        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

        const material = new THREE.PointsMaterial({
            size: 0.05,
            vertexColors: true,
            transparent: true,
            opacity: 0.6,
            blending: THREE.AdditiveBlending,
        });

        const particles = new THREE.Points(geometry, material);
        particles.userData.isBackground = true;
        this.scene.add(particles);
    }

    animate() {
        this.animationId = requestAnimationFrame(() => this.animate());

        const time = this.clock.getElapsedTime();
        const deltaTime = this.clock.getDelta();

        // Process camera animation
        if (this.cameraAnimation) {
            const anim = this.cameraAnimation;
            const elapsed = performance.now() - anim.startTime;
            const progress = Math.min(elapsed / anim.duration, 1);
            const eased = Easing.easeInOutCubic(progress);

            // Lerp camera position
            this.camera.position.lerpVectors(anim.startPosition, anim.targetPosition, eased);

            // Lerp look-at target
            if (this.controls) {
                this.controls.target.lerpVectors(anim.startLookAt, anim.targetLookAt, eased);
            }
            this.camera.lookAt(
                this.controls ? this.controls.target : anim.targetLookAt
            );

            if (progress >= 1) {
                // Animation complete
                if (this.controls) {
                    this.controls.enabled = true;
                }
                if (anim.onComplete) anim.onComplete();
                this.cameraAnimation = null;
            }
        }

        // Animate bubbles
        this.bubbles.forEach(bubble => {
            const data = bubble.userData;

            // Floating motion
            const floatY = Math.sin(time * 0.5 + data.floatPhase) * 0.05;
            const floatX = Math.cos(time * 0.3 + data.floatPhase) * 0.03;
            bubble.position.y += floatY * deltaTime;
            bubble.position.x += floatX * deltaTime;

            // Rotation
            bubble.rotation.y += data.rotationSpeed * deltaTime;

            // Scale animation
            const shimmer = 1 + Math.sin(time * 2 + data.shimmerPhase) * 0.02;
            const baseScale = data.baseRadius;
            const targetScale = bubble === this.hoveredBubble ? baseScale * 1.15 :
                               bubble === this.selectedBubble ? baseScale * 1.1 : baseScale;

            const currentScale = bubble.scale.x;
            const newScale = currentScale + (targetScale - currentScale) * 0.1;
            bubble.scale.setScalar(newScale * shimmer);
        });

        // Rotate background
        this.scene.children.forEach(child => {
            if (child.userData && child.userData.isBackground) {
                child.rotation.y += 0.0005;
            }
        });

        // Update controls
        if (this.controls) {
            this.controls.update();
        }

        this.renderer.render(this.scene, this.camera);
    }

    onWindowResize() {
        const width = this.container.clientWidth;
        const height = this.container.clientHeight;
        // Skip resize if container is hidden (0 dimensions)
        if (width <= 0 || height <= 0) return;

        this.camera.aspect = width / height;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(width, height);
    }

    onMouseMove(event) {
        const rect = this.container.getBoundingClientRect();
        this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
        this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

        this.raycaster.setFromCamera(this.mouse, this.camera);
        const intersects = this.raycaster.intersectObjects(this.bubbles);

        const previousHovered = this.hoveredBubble;

        if (intersects.length > 0) {
            this.hoveredBubble = intersects[0].object;
            this.renderer.domElement.style.cursor = 'pointer';
        } else {
            this.hoveredBubble = null;
            this.renderer.domElement.style.cursor = 'default';
        }

        if (previousHovered !== this.hoveredBubble) {
            if (previousHovered) {
                this.updateBubbleMaterial(previousHovered, false, previousHovered === this.selectedBubble);
            }
            if (this.hoveredBubble) {
                this.updateBubbleMaterial(this.hoveredBubble, true, this.hoveredBubble === this.selectedBubble);
            }
        }
    }

    onClick(event) {
        if (this.hoveredBubble) {
            const previousSelected = this.selectedBubble;
            this.selectedBubble = this.hoveredBubble;

            if (previousSelected && previousSelected !== this.selectedBubble) {
                this.updateBubbleMaterial(previousSelected, previousSelected === this.hoveredBubble, false);
            }
            this.updateBubbleMaterial(this.selectedBubble, true, true);

            // Update UI
            const data = this.selectedBubble.userData;
            document.getElementById('selected-title').textContent = data.numbered_title || data.title;
            document.getElementById('selected-description').textContent = `Universe ID: ${data.id}`;
            document.getElementById('enter-btn').classList.remove('hidden');
            document.getElementById('bubble-info').classList.remove('hidden');

            // Notify Python via IPC
            if (window.vibemind) {
                window.vibemind.selectBubble(data.id);
            }
        }
    }

    updateBubbleMaterial(bubble, isHovered, isSelected) {
        const data = bubble.userData;
        bubble.material.dispose();
        bubble.material = this.createGlassMaterial(data.baseColor, isHovered, isSelected);
    }

    // Public API methods
    getSelectedBubbleId() {
        return this.selectedBubble ? this.selectedBubble.userData.id : null;
    }

    getBubbleById(id) {
        const bubble = this.bubbles.find(b => b.userData.id === id);
        return bubble ? bubble.userData : null;
    }

    focusBubble(id) {
        const bubble = this.bubbles.find(b => b.userData.id === id);
        if (bubble && this.controls) {
            // Animate camera to focus on bubble
            const targetPos = bubble.position.clone();
            this.controls.target.copy(targetPos);
        }
    }

    /**
     * Animate camera to target position with easing
     * @param {THREE.Vector3} targetPosition - Target camera position
     * @param {THREE.Vector3} targetLookAt - Target look-at point
     * @param {number} duration - Animation duration in ms
     * @param {Function} onComplete - Callback when animation completes
     */
    animateCameraTo(targetPosition, targetLookAt, duration = 700, onComplete = null) {
        const startPosition = this.camera.position.clone();
        const startLookAt = this.controls ? this.controls.target.clone() : new THREE.Vector3(0, 0, 0);
        const startTime = performance.now();

        // Disable controls during animation
        if (this.controls) {
            this.controls.enabled = false;
        }

        this.cameraAnimation = {
            startPosition,
            startLookAt,
            targetPosition: targetPosition.clone(),
            targetLookAt: targetLookAt.clone(),
            duration,
            startTime,
            onComplete
        };
    }

    /**
     * Enter a bubble with zoom animation (legacy method - use enterBubbleWithCanvasNodes)
     * @param {number} bubbleIndex - Index of the bubble to enter
     * @param {Function} onComplete - Callback when animation completes
     */
    enterBubbleWithAnimation(bubbleIndex, onComplete) {
        const bubble = this.bubbles[bubbleIndex];
        if (!bubble) {
            console.warn('[MultiverseApp] Bubble not found at index:', bubbleIndex);
            if (onComplete) onComplete();
            return;
        }

        // Save current camera state for exit animation
        this.savedCameraPosition = this.camera.position.clone();
        this.savedCameraTarget = this.controls ? this.controls.target.clone() : new THREE.Vector3(0, 0, 0);

        // Calculate camera target: zoom into bubble center
        const bubblePos = bubble.position.clone();
        const cameraDirection = new THREE.Vector3()
            .subVectors(this.camera.position, bubblePos)
            .normalize();

        // Target position: very close to bubble (0.3 units from center)
        const targetPos = bubblePos.clone().add(cameraDirection.multiplyScalar(0.3));
        const targetLookAt = bubblePos.clone();

        // Visual effects: select this bubble
        this.selectedBubble = bubble;
        this.updateBubbleMaterial(bubble, true, true);

        // Fade out other bubbles
        this.bubbles.forEach((b, i) => {
            if (i !== bubbleIndex) {
                // Store original opacity
                if (!b.userData.originalOpacity) {
                    b.userData.originalOpacity = b.material.opacity;
                }
                // Fade to low opacity
                b.material.opacity = 0.1;
                b.material.emissiveIntensity = 0.05;
            }
        });

        // Intensify selected bubble glow
        bubble.material.emissiveIntensity = 0.6;

        // Animate camera
        this.animateCameraTo(targetPos, targetLookAt, 700, () => {
            // Trigger CSS overlay fade
            const overlay = document.getElementById('transition-overlay');
            if (overlay) {
                overlay.classList.add('active');
            }

            // Small delay then complete
            setTimeout(() => {
                if (onComplete) onComplete();
            }, 200);
        });
    }

    /**
     * Exit bubble with reverse zoom animation
     * @param {Function} onComplete - Callback when animation completes
     */
    exitBubbleWithAnimation(onComplete) {
        // Reset bubble opacities
        this.bubbles.forEach(b => {
            const originalOpacity = b.userData.originalOpacity || 0.9;
            b.material.opacity = originalOpacity;
            b.material.emissiveIntensity = 0.15;
        });

        // Clear selection
        if (this.selectedBubble) {
            this.updateBubbleMaterial(this.selectedBubble, false, false);
            this.selectedBubble = null;
        }

        // Use saved position or default
        const defaultPos = this.savedCameraPosition || new THREE.Vector3(0, 0, 8);
        const defaultLookAt = this.savedCameraTarget || new THREE.Vector3(0, 0, 0);

        // Animate camera back (fast exit - 250ms)
        this.animateCameraTo(defaultPos, defaultLookAt, 250, () => {
            // Hide overlay
            const overlay = document.getElementById('transition-overlay');
            if (overlay) {
                overlay.classList.remove('active');
            }
            if (onComplete) onComplete();
        });
    }

    /**
     * Get bubble by ID (for external callers)
     */
    getBubbleIndexById(id) {
        return this.bubbles.findIndex(b => b.userData.id === id);
    }

    syncBubbles(newBubbleData) {
        // Clear existing bubbles
        this.bubbles.forEach(bubble => {
            this.scene.remove(bubble);
            bubble.geometry.dispose();
            bubble.material.dispose();
        });
        this.bubbles = [];

        // Add new bubbles
        newBubbleData.forEach(data => this.addBubble(data));
    }

    dispose() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
        }

        this.bubbles.forEach(bubble => {
            this.scene.remove(bubble);
            bubble.geometry.dispose();
            bubble.material.dispose();
        });

        // Clean up rich content renderer
        if (this.richContentRenderer) {
            this.richContentRenderer.clear();
        }

        this.renderer.dispose();
    }

    // ========================================
    // RICH CONTENT RENDERER INTEGRATION
    // ========================================

    /**
     * Initialize the rich content renderer for canvas nodes
     */
    initializeRichContentRenderer() {
        // Create a container for canvas nodes (overlay on top of Three.js canvas)
        const canvasNodeContainer = document.createElement('div');
        canvasNodeContainer.id = 'canvas-node-container';
        canvasNodeContainer.style.position = 'absolute';
        canvasNodeContainer.style.top = '0';
        canvasNodeContainer.style.left = '0';
        canvasNodeContainer.style.width = '100%';
        canvasNodeContainer.style.height = '100%';
        canvasNodeContainer.style.pointerEvents = 'none'; // Let Three.js handle interactions
        canvasNodeContainer.style.zIndex = '10';

        // Insert after the Three.js canvas
        this.container.appendChild(canvasNodeContainer);

        // Initialize rich content renderer
        this.richContentRenderer = new RichContentRenderer(canvasNodeContainer);

        console.log('[MultiverseApp] Rich content renderer initialized');
    }

    /**
     * Handle entering a bubble - show canvas nodes
     * @param {number} bubbleIndex - Index of the bubble being entered
     */
    enterBubbleWithCanvasNodes(bubbleIndex, onComplete) {
        const bubble = this.bubbles[bubbleIndex];
        if (!bubble) {
            console.warn('[MultiverseApp] Bubble not found at index:', bubbleIndex);
            if (onComplete) onComplete();
            return;
        }

        this.currentBubbleId = bubble.userData.id;

        // Load canvas nodes for this bubble
        this.loadCanvasNodesForBubble(this.currentBubbleId);

        // Continue with normal bubble entry animation
        this.enterBubbleWithAnimation(bubbleIndex, onComplete);
    }

    /**
     * Handle exiting a bubble - hide canvas nodes
     */
    exitBubbleWithCanvasNodes(onComplete) {
        // Clear canvas nodes
        if (this.richContentRenderer) {
            this.richContentRenderer.clear();
        }

        this.currentBubbleId = null;

        // Continue with normal bubble exit animation
        this.exitBubbleWithAnimation(onComplete);
    }

    /**
     * Load canvas nodes for a specific bubble
     * @param {string} bubbleId - Bubble identifier
     */
    loadCanvasNodesForBubble(bubbleId) {
        console.log('[MultiverseApp] Loading canvas nodes for bubble:', bubbleId);

        // Request canvas nodes from Python backend
        if (window.vibemind) {
            window.vibemind.sendToPython({
                type: 'get_canvas_nodes',
                bubble_id: bubbleId
            });
        }
    }

    /**
     * Handle canvas node updates from Python
     * @param {Object} message - Message containing node updates
     */
    handleCanvasNodeUpdate(message) {
        if (!this.richContentRenderer) return;

        const { bubble_id, nodes } = message;

        // Only process if we're in the correct bubble
        if (bubble_id !== this.currentBubbleId) return;

        console.log('[MultiverseApp] Updating canvas nodes:', nodes);

        // Clear existing nodes
        this.richContentRenderer.clear();

        // Render new nodes
        if (nodes && Array.isArray(nodes)) {
            nodes.forEach(nodeData => {
                if (nodeData.id && nodeData.content) {
                    this.richContentRenderer.renderNode(nodeData.id, nodeData);
                }
            });
        }
    }

    /**
     * Handle individual canvas node updates
     * @param {Object} message - Message containing single node update
     */
    handleCanvasNodeSingleUpdate(message) {
        if (!this.richContentRenderer) return;

        const { bubble_id, node_id, node_data, action } = message;

        // Only process if we're in the correct bubble
        if (bubble_id !== this.currentBubbleId) return;

        console.log('[MultiverseApp] Single node update:', action, node_id);

        switch (action) {
            case 'add':
            case 'update':
                if (node_data) {
                    this.richContentRenderer.renderNode(node_id, node_data);
                }
                break;
            case 'delete':
                this.richContentRenderer.removeNode(node_id);
                break;
        }
    }

    /**
     * Add a new canvas node programmatically
     * @param {string} bubbleId - Bubble identifier
     * @param {Object} nodeData - Node data
     */
    addCanvasNode(bubbleId, nodeData) {
        if (window.vibemind) {
            window.vibemind.addCanvasNode(bubbleId, nodeData);
        }
    }

    /**
     * Update an existing canvas node
     * @param {string} bubbleId - Bubble identifier
     * @param {string} nodeId - Node identifier
     * @param {Object} updates - Node updates
     */
    updateCanvasNode(bubbleId, nodeId, updates) {
        if (window.vibemind) {
            window.vibemind.updateCanvasNode(bubbleId, nodeId, updates);
        }
    }

    /**
     * Delete a canvas node
     * @param {string} bubbleId - Bubble identifier
     * @param {string} nodeId - Node identifier
     */
    deleteCanvasNode(bubbleId, nodeId) {
        if (window.vibemind) {
            window.vibemind.deleteCanvasNode(bubbleId, nodeId);
        }
    }

    /**
     * Setup event handlers for canvas node messages from Python
     */
    setupCanvasNodeEventHandlers() {
        if (!window.vibemind) return;

        window.vibemind.onPythonMessage((message) => {
            switch (message.type) {
                case 'canvas_nodes_update':
                    this.handleCanvasNodeUpdate(message);
                    break;
                case 'canvas_node_update':
                    this.handleCanvasNodeSingleUpdate(message);
                    break;
                case 'node_structured_update':
                    // Handle structured content updates (accept both field names)
                    const structContent = message.content || message.structured_content;
                    if (message.node_id && structContent) {
                        this.handleCanvasNodeSingleUpdate({
                            bubble_id: this.currentBubbleId,
                            node_id: message.node_id,
                            node_data: { ...message, content: structContent },
                            action: 'update'
                        });
                    }
                    break;
            }
        });

        console.log('[MultiverseApp] Canvas node event handlers setup');
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    const container = document.getElementById('canvas-container');
    if (container) {
        window.multiverseApp = new MultiverseApp(container);
    }
});
