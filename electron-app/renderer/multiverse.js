/**
 * VibeMind Multiverse Navigator for Electron
 * 
 * Features:
 * - Ideas Universe (blue bubbles)
 * - Desktop Automation (golden Light Planet)
 * - Animated camera navigation between spaces
 * - Hand gesture navigation via WebSocket
 * - IPC integration with Python backend
 */

class MultiverseApp {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            console.error('[Multiverse] Container not found:', containerId);
            return;
        }
        
        // State
        this.currentSpace = 'ideas';
        this.currentAgent = 'rachel';
        this.isNavigating = false;
        this.handSocket = null;
        this.selectedBubbleIndex = -1;  // Track selected bubble
        this.selectedBubbleId = null;    // Track selected bubble ID
        this.selectedProjectIndex = -1;  // Track selected project
        this.selectedProjectId = null;   // Track selected project ID
        this.isInsideBubble = false;     // Track if we're in bubble view
        this.shuttleManager = null;      // Requirement shuttle manager
        
        // Constants
        this.HELIX_HEIGHT = 6;           // DNA Helix height constant
        this.HELIX_RADIUS = 1.2;         // DNA Helix radius
        
        // Three.js objects
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.controls = null;
        this.clock = null;
        
        // Space definitions
        this.spaces = {
            ideas: {
                objects: [],
                position: new THREE.Vector3(0, 0, 0),
                icon: '💭',
                name: 'Ideas Universe',
                agent: { name: 'Rachel', slug: 'rachel', role: 'Idea Navigator' },
                color: 0x4488ff
            },
            projects: {
                objects: [],
                position: new THREE.Vector3(16, 0, 11),
                icon: '🧬',
                name: 'Project Space',
                agent: { name: 'Coding', slug: 'coding', role: 'Project Manager' },
                color: 0x44ff88
            },
            desktop: {
                objects: [],
                position: new THREE.Vector3(22, 0, -14),
                icon: '🌟',
                name: 'Desktop Automation',
                agent: { name: 'Desktop', slug: 'desktop', role: 'Desktop Worker' },
                color: 0xff8844
            },
            roarboot: {
                objects: [],
                position: new THREE.Vector3(-17, 0, -8),
                icon: '\u{1F6A3}',
                name: 'Rowboat',
                agent: { name: 'Rowboat', slug: 'roarboot', role: 'Knowledge Navigator' },
                color: 0x22ccaa
            },
            swedesign: {
                objects: [],
                position: new THREE.Vector3(8, 0, 5.5),
                icon: '\u{1F3ED}',
                name: 'SWE Design Factory',
                agent: { name: 'Factory', slug: 'swedesign', role: 'Spec Generator' },
                color: 0xff6633
            },
            clawport: {
                objects: [],
                position: new THREE.Vector3(-8, 0, 12),
                icon: '\u{1F4CA}',
                name: 'Dashboard',
                agent: { name: 'Dashboard', slug: 'clawport', role: 'System Dashboard' },
                color: 0x8866ff
            },
            agentfarm: {
                objects: [],
                position: new THREE.Vector3(-14, 0, 18),
                icon: '\u{1F3E1}',
                name: 'Agent Farm',
                agent: { name: 'Farmer', slug: 'agentfarm', role: 'Agent Orchestrator' },
                color: 0x88aa44
            },
            thebrain: {
                objects: [],
                position: new THREE.Vector3(14, 0, -22),
                icon: '\u{1F9E0}',
                name: 'The Brain',
                agent: { name: 'Brain', slug: 'thebrain', role: 'Knowledge Center' },
                color: 0xff66aa
            },
            video: {
                objects: [],
                position: new THREE.Vector3(-20, 0, 24),
                icon: '\u{1F3AC}',
                name: 'Video Studio',
                agent: { name: 'Director', slug: 'video', role: 'Video Producer' },
                color: 0xee4466
            }
        };
        
        this.init();
    }
    
    // ========================================================================
    // SHADERS
    // ========================================================================
    
    get planetVertexShader() {
        return `
            uniform float u_time;
            uniform float u_pulse;
            uniform vec3 u_handPos;
            varying vec3 vNormal;
            varying vec3 vPosition;
            
            // Simplex noise function
            vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
            vec4 mod289(vec4 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
            vec4 permute(vec4 x) { return mod289(((x*34.0)+1.0)*x); }
            vec4 taylorInvSqrt(vec4 r) { return 1.79284291400159 - 0.85373472095314 * r; }
            
            float snoise(vec3 v) {
                const vec2 C = vec2(1.0/6.0, 1.0/3.0);
                const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);
                vec3 i  = floor(v + dot(v, C.yyy));
                vec3 x0 = v - i + dot(i, C.xxx);
                vec3 g = step(x0.yzx, x0.xyz);
                vec3 l = 1.0 - g;
                vec3 i1 = min(g.xyz, l.zxy);
                vec3 i2 = max(g.xyz, l.zxy);
                vec3 x1 = x0 - i1 + C.xxx;
                vec3 x2 = x0 - i2 + C.yyy;
                vec3 x3 = x0 - D.yyy;
                i = mod289(i);
                vec4 p = permute(permute(permute(
                    i.z + vec4(0.0, i1.z, i2.z, 1.0))
                    + i.y + vec4(0.0, i1.y, i2.y, 1.0))
                    + i.x + vec4(0.0, i1.x, i2.x, 1.0));
                float n_ = 0.142857142857;
                vec3 ns = n_ * D.wyz - D.xzx;
                vec4 j = p - 49.0 * floor(p * ns.z * ns.z);
                vec4 x_ = floor(j * ns.z);
                vec4 y_ = floor(j - 7.0 * x_);
                vec4 x = x_ *ns.x + ns.yyyy;
                vec4 y = y_ *ns.x + ns.yyyy;
                vec4 h = 1.0 - abs(x) - abs(y);
                vec4 b0 = vec4(x.xy, y.xy);
                vec4 b1 = vec4(x.zw, y.zw);
                vec4 s0 = floor(b0)*2.0 + 1.0;
                vec4 s1 = floor(b1)*2.0 + 1.0;
                vec4 sh = -step(h, vec4(0.0));
                vec4 a0 = b0.xzyw + s0.xzyw*sh.xxyy;
                vec4 a1 = b1.xzyw + s1.xzyw*sh.zzww;
                vec3 p0 = vec3(a0.xy, h.x);
                vec3 p1 = vec3(a0.zw, h.y);
                vec3 p2 = vec3(a1.xy, h.z);
                vec3 p3 = vec3(a1.zw, h.w);
                vec4 norm = taylorInvSqrt(vec4(dot(p0,p0), dot(p1,p1), dot(p2,p2), dot(p3,p3)));
                p0 *= norm.x; p1 *= norm.y; p2 *= norm.z; p3 *= norm.w;
                vec4 m = max(0.6 - vec4(dot(x0,x0), dot(x1,x1), dot(x2,x2), dot(x3,x3)), 0.0);
                m = m * m;
                return 42.0 * dot(m*m, vec4(dot(p0,x0), dot(p1,x1), dot(p2,x2), dot(p3,x3)));
            }
            
            void main() {
                vNormal = normal;
                vec3 pos = position;
                
                // Base noise deformation
                float noise = snoise(pos * 2.0 + u_time * 0.3) * 0.15;
                pos += normal * noise;
                
                // Pulsation
                float pulse = sin(u_time * 2.0) * 0.05 * u_pulse;
                pos *= (1.0 + pulse);
                
                // Hand influence - morph toward hand position
                if (length(u_handPos) > 0.0) {
                    vec3 toHand = normalize(u_handPos - pos);
                    float influence = max(0.0, 1.0 - length(pos - u_handPos) * 0.5);
                    pos += toHand * influence * 0.3;
                }
                
                vPosition = pos;
                gl_Position = projectionMatrix * modelViewMatrix * vec4(pos, 1.0);
            }
        `;
    }
    
    get planetFragmentShader() {
        return `
            uniform vec3 u_color;
            uniform float u_time;
            uniform float u_intensity;
            varying vec3 vNormal;
            varying vec3 vPosition;

            void main() {
                vec3 viewDir = normalize(cameraPosition - vPosition);
                float fresnel = pow(1.0 - max(dot(viewDir, vNormal), 0.0), 3.0);

                vec3 color = u_color * (1.0 + fresnel * 0.5);
                float shimmer = sin(vPosition.x * 10.0 + u_time * 2.0) * 0.1 + 0.9;
                color *= shimmer * u_intensity;
                
                gl_FragColor = vec4(color, 0.9);
            }
        `;
    }
    
    // DNA Helix Vertex Shader for Project Space
    get dnaHelixVertexShader() {
        return `
            uniform float u_time;
            uniform float u_twist;
            varying vec3 vPosition;
            varying vec2 vUv;
            varying vec3 vNormal;
            
            void main() {
                vPosition = position;
                vUv = uv;
                vNormal = normal;
                
                // Helix twist deformation
                float angle = position.y * u_twist + u_time * 0.5;
                vec3 twisted = vec3(
                    position.x * cos(angle) - position.z * sin(angle),
                    position.y,
                    position.x * sin(angle) + position.z * cos(angle)
                );
                
                gl_Position = projectionMatrix * modelViewMatrix * vec4(twisted, 1.0);
            }
        `;
    }
    
    // DNA Helix Fragment Shader for Project Space
    get dnaHelixFragmentShader() {
        return `
            uniform vec3 u_colorA;
            uniform vec3 u_colorB;
            uniform float u_time;
            uniform float u_glow;
            varying vec3 vPosition;
            varying vec2 vUv;
            varying vec3 vNormal;
            
            void main() {
                // Gradient along helix
                float gradient = sin(vUv.y * 3.14159 * 2.0 + u_time) * 0.5 + 0.5;
                vec3 color = mix(u_colorA, u_colorB, gradient);
                
                // Fresnel glow
                vec3 viewDir = normalize(cameraPosition - vPosition);
                float fresnel = pow(1.0 - abs(dot(viewDir, vNormal)), 2.0);
                color += fresnel * u_glow * vec3(0.5, 1.0, 0.8);
                
                // Pulsing effect
                float pulse = sin(u_time * 2.0) * 0.1 + 0.9;
                color *= pulse;
                
                gl_FragColor = vec4(color, 0.85);
            }
        `;
    }
    
    // ========================================================================
    // INITIALIZATION
    // ========================================================================
    
    init() {
        console.log('[Multiverse] Initializing...');
        
        // Scene
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x0a0812);
        this.scene.fog = new THREE.FogExp2(0x0a0812, 0.020);
        
        // Camera
        this.camera = new THREE.PerspectiveCamera(
            60,
            this.container.clientWidth / this.container.clientHeight,
            0.1,
            200
        );
        this.camera.position.set(0, 2, 10);
        
        // Renderer
        this.renderer = new THREE.WebGLRenderer({ antialias: true });
        this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
        this.renderer.toneMappingExposure = 1.5;
        this.container.appendChild(this.renderer.domElement);
        
        // Controls
        this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.05;
        this.controls.maxDistance = 30;
        this.controls.minDistance = 3;
        
        // Clock
        this.clock = new THREE.Clock();
        
        // Create scene objects
        this.createIdeasSpace();
        this.createProjectSpace();
        this.createDesktopSpace();
        this.createRoarbootSpace();
        this.createSweDesignSpace();
        this.createDashboardSpace();
        this.createAgentFarmSpace();
        this.createVideoSpace();
        this.createBrainSpace();
        this.createEnvironment();
        this.createConnectionPaths();

        // Initialize ShuttleManager for requirement pipeline visualization
        if (typeof ShuttleManager !== 'undefined') {
            this.shuttleManager = new ShuttleManager(this.scene, this.spaces);
            console.log('[Multiverse] ShuttleManager initialized');
        }

        // Event listeners
        window.addEventListener('resize', () => this.onWindowResize());
        window.addEventListener('keydown', (e) => this.onKeyDown(e));
        
        // Click handler for bubble/project selection
        this.container.addEventListener('click', (e) => this.onContainerClick(e));

        // Hover handler for bubble tooltip
        this.container.addEventListener('mousemove', (e) => this.onContainerMouseMove(e));
        this.hoveredBubbleIndex = -1;
        this.tooltipPinned = false; // Keep tooltip visible after click
        this.tooltipBubbleId = null; // ID of bubble currently shown in tooltip

        // Prevent tooltip hide when mouse is over the info panel
        const infoPanel = document.getElementById('info-panel');
        if (infoPanel) {
            infoPanel.addEventListener('mouseenter', () => { this.tooltipPinned = true; });
            infoPanel.addEventListener('mouseleave', () => {
                this.tooltipPinned = false;
                // Hide after leaving panel if not hovering a bubble
                if (this.hoveredBubbleIndex < 0 && this.selectedBubbleIndex < 0) {
                    this.hideBubbleTooltip();
                }
            });
        }
        
        // Connect to hand tracking WebSocket
        this.connectHandTracking();
        
        // Start animation loop
        this.animate();

        // Game console chat overlay
        this.initGameConsole();

        console.log('[Multiverse] Initialized successfully');
    }
    
    // ========================================================================
    // IDEAS SPACE (Bubbles)
    // ========================================================================
    
    createIdeasSpace() {
        const spaceGroup = new THREE.Group();
        spaceGroup.position.copy(this.spaces.ideas.position);
        
        // Create glass bubbles
        const bubbleData = [
            { title: "Universe Alpha", pos: { x: -2, y: 0.5, z: 0 }, color: 0x66aaff, radius: 0.8 },
            { title: "Universe Beta", pos: { x: 2, y: -0.5, z: -1 }, color: 0xff66aa, radius: 0.7 },
            { title: "Research Hub", pos: { x: 0, y: 1.5, z: 1 }, color: 0x66ffaa, radius: 0.6 },
            { title: "Creative Space", pos: { x: -1, y: -1, z: 2 }, color: 0xffcc66, radius: 0.75 },
            { title: "Data Nexus", pos: { x: 1.5, y: 0, z: -2 }, color: 0xcc66ff, radius: 0.65 },
        ];
        
        bubbleData.forEach(data => {
            const geometry = new THREE.IcosahedronGeometry(data.radius, 3);
            const material = new THREE.MeshPhysicalMaterial({
                color: data.color,
                metalness: 0.1,
                roughness: 0.1,
                transmission: 0.9,
                transparent: true,
                opacity: 0.8,
            });
            
            const bubble = new THREE.Mesh(geometry, material);
            bubble.position.set(data.pos.x, data.pos.y, data.pos.z);
            bubble.userData = { type: 'bubble', title: data.title };
            spaceGroup.add(bubble);
            this.spaces.ideas.objects.push(bubble);
        });
        
        // Central marker ring
        const markerGeometry = new THREE.RingGeometry(2.5, 3, 32);
        const markerMaterial = new THREE.MeshBasicMaterial({
            color: 0x4488ff,
            transparent: true,
            opacity: 0.3,
            side: THREE.DoubleSide
        });
        const marker = new THREE.Mesh(markerGeometry, markerMaterial);
        marker.rotation.x = -Math.PI / 2;
        marker.position.y = -2;
        spaceGroup.add(marker);
        
        this.scene.add(spaceGroup);
        this.spaces.ideas.group = spaceGroup;
    }
    
    // ========================================================================
    // PROJECT SPACE (DNA Helix)
    // ========================================================================
    
    createProjectSpace() {
        const spaceGroup = new THREE.Group();
        spaceGroup.position.copy(this.spaces.projects.position);

        // Create DNA Double Helix
        this.createDNAHelix(spaceGroup);

        // Projects will be synced from database via syncProjects()
        // Request real projects from backend
        this.requestRealProjects();

        // Central marker ring
        const markerGeometry = new THREE.RingGeometry(2.5, 3, 32);
        const markerMaterial = new THREE.MeshBasicMaterial({
            color: 0x44ff88,
            transparent: true,
            opacity: 0.3,
            side: THREE.DoubleSide
        });
        const marker = new THREE.Mesh(markerGeometry, markerMaterial);
        marker.rotation.x = -Math.PI / 2;
        marker.position.y = -3;
        spaceGroup.add(marker);

        this.scene.add(spaceGroup);
        this.spaces.projects.group = spaceGroup;

        console.log('[Multiverse] Project Space created with DNA Helix');
    }

    /**
     * Request real projects from Python backend
     */
    requestRealProjects() {
        if (window.vibemind && window.vibemind.sendToPython) {
            window.vibemind.sendToPython({
                type: 'get_generated_projects'
            });
            console.log('[Multiverse] Requested real projects from database');
        }
    }

    /**
     * Sync Projects Space with real database projects
     * @param {Array} projects - List of projects from database
     */
    syncProjects(projects) {
        if (!this.spaces.projects.group) {
            console.warn('[Multiverse] Project space group not ready');
            return;
        }

        const spaceGroup = this.spaces.projects.group;

        // Remove existing project nodes (but keep DNA helix and marker)
        const nodesToRemove = [];
        spaceGroup.children.forEach(child => {
            if (child.userData && child.userData.isProject) {
                nodesToRemove.push(child);
            }
        });
        nodesToRemove.forEach(node => {
            spaceGroup.remove(node);
            if (node.geometry) node.geometry.dispose();
            if (node.material) {
                if (Array.isArray(node.material)) {
                    node.material.forEach(m => m.dispose());
                } else {
                    node.material.dispose();
                }
            }
        });

        // Clear objects array (keep only non-project objects)
        this.spaces.projects.objects = this.spaces.projects.objects.filter(
            obj => !obj.userData?.isProject
        );

        // Create nodes for real projects
        if (projects && projects.length > 0) {
            projects.forEach((project, index) => {
                const angle = (index / projects.length) * Math.PI * 2;
                const height = (index % 3 - 1) * 2; // Distribute at heights -2, 0, +2

                const data = {
                    id: project.id,
                    title: project.name || project.title || 'Unnamed Project',
                    status: project.status || 'active',
                    progress: project.completion_percentage || 0,
                    linked_shuttle: project.linked_shuttle || null,
                    from_idea_id: project.from_idea_id || null,
                    pos: { angle: angle, height: height }
                };

                this.createProjectNode(spaceGroup, data, index);
            });

            console.log(`[Multiverse] Synced ${projects.length} real projects to Projects Space`);
        } else {
            console.log('[Multiverse] No projects to sync');
        }
    }
    
    createDNAHelix(parentGroup) {
        const helixRadius = this.HELIX_RADIUS;
        const helixHeight = this.HELIX_HEIGHT;
        const twists = 2;
        const segments = 100;
        
        // Create helix curves for both strands
        const strand1Points = [];
        const strand2Points = [];
        
        for (let i = 0; i <= segments; i++) {
            const t = i / segments;
            const y = (t - 0.5) * helixHeight;
            const angle = t * Math.PI * 2 * twists;
            
            // Strand 1
            strand1Points.push(new THREE.Vector3(
                Math.cos(angle) * helixRadius,
                y,
                Math.sin(angle) * helixRadius
            ));
            
            // Strand 2 (opposite phase)
            strand2Points.push(new THREE.Vector3(
                Math.cos(angle + Math.PI) * helixRadius,
                y,
                Math.sin(angle + Math.PI) * helixRadius
            ));
        }
        
        // Tube material with shader
        const helixMaterial = new THREE.ShaderMaterial({
            vertexShader: this.dnaHelixVertexShader,
            fragmentShader: this.dnaHelixFragmentShader,
            uniforms: {
                u_time: { value: 0 },
                u_twist: { value: 0 }, // Already twisted in geometry
                u_colorA: { value: new THREE.Color(0x00ffff) }, // Cyan
                u_colorB: { value: new THREE.Color(0xff00ff) }, // Magenta
                u_glow: { value: 0.5 }
            },
            transparent: true,
            side: THREE.DoubleSide
        });
        
        // Create tubes for both strands
        const curve1 = new THREE.CatmullRomCurve3(strand1Points);
        const curve2 = new THREE.CatmullRomCurve3(strand2Points);
        
        const tubeGeometry1 = new THREE.TubeGeometry(curve1, segments, 0.08, 8, false);
        const tubeGeometry2 = new THREE.TubeGeometry(curve2, segments, 0.08, 8, false);
        
        const strand1 = new THREE.Mesh(tubeGeometry1, helixMaterial.clone());
        const strand2 = new THREE.Mesh(tubeGeometry2, helixMaterial.clone());
        
        // Swap colors for strand 2
        strand2.material.uniforms.u_colorA.value = new THREE.Color(0xff00ff);
        strand2.material.uniforms.u_colorB.value = new THREE.Color(0x00ffff);
        
        strand1.userData = { type: 'dna-strand', strand: 1 };
        strand2.userData = { type: 'dna-strand', strand: 2 };
        
        parentGroup.add(strand1);
        parentGroup.add(strand2);
        
        this.spaces.projects.helix = { strand1, strand2 };
        this.spaces.projects.objects.push(strand1, strand2);
        
        // Create orbiting particles around helix
        const particleCount = 300;
        const particlePositions = new Float32Array(particleCount * 3);
        
        for (let i = 0; i < particleCount; i++) {
            const t = Math.random();
            const y = (t - 0.5) * helixHeight;
            const angle = Math.random() * Math.PI * 2;
            const radius = helixRadius + 0.5 + Math.random() * 1.5;
            
            particlePositions[i * 3] = Math.cos(angle) * radius;
            particlePositions[i * 3 + 1] = y;
            particlePositions[i * 3 + 2] = Math.sin(angle) * radius;
        }
        
        const particleGeometry = new THREE.BufferGeometry();
        particleGeometry.setAttribute('position', new THREE.BufferAttribute(particlePositions, 3));
        
        const particleMaterial = new THREE.PointsMaterial({
            color: 0x44ff88,
            size: 0.04,
            transparent: true,
            opacity: 0.7,
            blending: THREE.AdditiveBlending
        });
        
        const particles = new THREE.Points(particleGeometry, particleMaterial);
        parentGroup.add(particles);
        this.spaces.projects.particles = particles;
        this.spaces.projects.objects.push(particles);
    }
    
    createProjectNode(parentGroup, data, index) {
        // Status colors (Phase 8: added shuttling and needs_work)
        const statusColors = {
            active: 0x44ff44,      // Green - ready for code gen
            progress: 0xffff44,    // Yellow - generating
            blocked: 0xff4444,     // Red
            completed: 0x4488ff,   // Blue - done
            shuttling: 0x888888,   // Gray - processing requirements
            needs_work: 0xffaa44,  // Orange - failed validation
            generating: 0xffff44   // Yellow - code being generated
        };

        const color = statusColors[data.status] || 0xffffff;
        const isShuttling = data.status === 'shuttling';
        
        // Calculate position along helix
        const helixRadius = 1.8;
        const x = Math.cos(data.pos.angle) * helixRadius;
        const z = Math.sin(data.pos.angle) * helixRadius;
        const y = data.pos.height;
        
        // Create node sphere
        const nodeGeometry = new THREE.SphereGeometry(0.35, 16, 16);
        const nodeMaterial = new THREE.MeshPhysicalMaterial({
            color: color,
            metalness: 0.3,
            roughness: 0.2,
            emissive: color,
            emissiveIntensity: isShuttling ? 0.1 : 0.3,  // Dimmer for shuttling
            transparent: true,
            opacity: isShuttling ? 0.6 : 0.9,  // More transparent for shuttling
        });

        const node = new THREE.Mesh(nodeGeometry, nodeMaterial);
        node.position.set(x, y, z);
        node.userData = {
            type: 'project',
            title: data.title,
            status: data.status,
            progress: data.progress,
            index: index,
            isShuttling: isShuttling,  // Track for animation
            linkedShuttleId: data.linked_shuttle || null,
            isProject: true,  // Mark for cleanup/sync
            projectId: data.id || null
        };
        
        parentGroup.add(node);
        this.spaces.projects.objects.push(node);
        
        // Glow effect
        const glowGeometry = new THREE.SphereGeometry(0.5, 8, 8);
        const glowMaterial = new THREE.MeshBasicMaterial({
            color: color,
            transparent: true,
            opacity: 0.2,
            side: THREE.BackSide
        });
        const glow = new THREE.Mesh(glowGeometry, glowMaterial);
        glow.position.copy(node.position);
        parentGroup.add(glow);
        
        // Progress ring
        if (data.progress < 100) {
            const progressAngle = (data.progress / 100) * Math.PI * 2;
            const ringGeometry = new THREE.RingGeometry(0.4, 0.45, 32, 1, 0, progressAngle);
            const ringMaterial = new THREE.MeshBasicMaterial({
                color: color,
                transparent: true,
                opacity: 0.8,
                side: THREE.DoubleSide
            });
            const ring = new THREE.Mesh(ringGeometry, ringMaterial);
            ring.position.copy(node.position);
            ring.rotation.x = -Math.PI / 2;
            ring.position.y += 0.5;
            parentGroup.add(ring);
        }
        
        return node;
    }
    
    // ========================================================================
    // DESKTOP SPACE (Light Planet)
    // ========================================================================
    
    createDesktopSpace() {
        const spaceGroup = new THREE.Group();
        spaceGroup.position.copy(this.spaces.desktop.position);
        
        // Light Planet with shader
        const planetGeometry = new THREE.IcosahedronGeometry(1.5, 4);
        const planetMaterial = new THREE.ShaderMaterial({
            vertexShader: this.planetVertexShader,
            fragmentShader: this.planetFragmentShader,
            uniforms: {
                u_time: { value: 0 },
                u_pulse: { value: 1.0 },
                u_color: { value: new THREE.Color(0xffaa44) },
                u_handPos: { value: new THREE.Vector3(0, 0, 0) },
                u_intensity: { value: 1.0 }
            },
            transparent: true,
        });
        
        const planet = new THREE.Mesh(planetGeometry, planetMaterial);
        planet.userData = { type: 'planet', title: 'Light Planet' };
        spaceGroup.add(planet);
        this.spaces.desktop.objects.push(planet);
        this.spaces.desktop.planet = planet;
        
        // Glow effect
        const glowGeometry = new THREE.IcosahedronGeometry(2.0, 2);
        const glowMaterial = new THREE.MeshBasicMaterial({
            color: 0xff8844,
            transparent: true,
            opacity: 0.2,
            side: THREE.BackSide
        });
        const glow = new THREE.Mesh(glowGeometry, glowMaterial);
        spaceGroup.add(glow);
        
        // Orbiting particles
        const particleCount = 500;
        const particlePositions = new Float32Array(particleCount * 3);
        
        for (let i = 0; i < particleCount; i++) {
            const radius = 2.5 + Math.random() * 2;
            const theta = Math.random() * Math.PI * 2;
            const phi = Math.acos(2 * Math.random() - 1);
            
            particlePositions[i * 3] = radius * Math.sin(phi) * Math.cos(theta);
            particlePositions[i * 3 + 1] = radius * Math.sin(phi) * Math.sin(theta);
            particlePositions[i * 3 + 2] = radius * Math.cos(phi);
        }
        
        const particleGeometry = new THREE.BufferGeometry();
        particleGeometry.setAttribute('position', new THREE.BufferAttribute(particlePositions, 3));
        
        const particleMaterial = new THREE.PointsMaterial({
            color: 0xffcc66,
            size: 0.05,
            transparent: true,
            opacity: 0.8,
            blending: THREE.AdditiveBlending
        });
        
        const particles = new THREE.Points(particleGeometry, particleMaterial);
        spaceGroup.add(particles);
        this.spaces.desktop.objects.push(particles);
        
        // Saturn-like rings
        const ringGeometry = new THREE.RingGeometry(2.2, 3.5, 64);
        const ringMaterial = new THREE.MeshBasicMaterial({
            color: 0x886644,
            transparent: true,
            opacity: 0.4,
            side: THREE.DoubleSide
        });
        const ring = new THREE.Mesh(ringGeometry, ringMaterial);
        ring.rotation.x = Math.PI / 2 + 0.3;
        spaceGroup.add(ring);
        
        // Central marker
        const markerGeometry = new THREE.RingGeometry(3, 3.5, 32);
        const markerMaterial = new THREE.MeshBasicMaterial({
            color: 0xff8844,
            transparent: true,
            opacity: 0.3,
            side: THREE.DoubleSide
        });
        const marker = new THREE.Mesh(markerGeometry, markerMaterial);
        marker.rotation.x = -Math.PI / 2;
        marker.position.y = -2;
        spaceGroup.add(marker);
        
        this.scene.add(spaceGroup);
        this.spaces.desktop.group = spaceGroup;
    }

    // ========================================================================
    // ROARBOOT SPACE (Rowing Boat)
    // ========================================================================

    createRoarbootSpace() {
        const spaceGroup = new THREE.Group();
        spaceGroup.position.copy(this.spaces.roarboot.position);

        const boatColor = 0x22ccaa;

        // --- Hull (elongated half-ellipsoid) ---
        const hullGeom = new THREE.SphereGeometry(1.2, 16, 12, 0, Math.PI * 2, 0, Math.PI / 2);
        const hullMat = new THREE.MeshPhongMaterial({
            color: boatColor,
            transparent: true,
            opacity: 0.7,
            emissive: boatColor,
            emissiveIntensity: 0.3,
            side: THREE.DoubleSide,
        });
        const hull = new THREE.Mesh(hullGeom, hullMat);
        hull.scale.set(1, 0.4, 2.2);
        hull.rotation.x = Math.PI;
        hull.position.y = 0.1;
        hull.userData = { type: 'rowboat', title: 'Rowboat' };
        spaceGroup.add(hull);
        this.spaces.roarboot.objects.push(hull);
        this.spaces.roarboot.boat = hull;

        // --- Mast ---
        const mastGeom = new THREE.CylinderGeometry(0.03, 0.03, 2.0, 8);
        const mastMat = new THREE.MeshBasicMaterial({
            color: 0xffffff, transparent: true, opacity: 0.6,
        });
        const mast = new THREE.Mesh(mastGeom, mastMat);
        mast.position.set(0, 1.0, -0.3);
        spaceGroup.add(mast);

        // --- Sail (triangle) ---
        const sailShape = new THREE.Shape();
        sailShape.moveTo(0, 0);
        sailShape.lineTo(0.8, 0.6);
        sailShape.lineTo(0, 1.6);
        sailShape.lineTo(0, 0);
        const sailGeom = new THREE.ShapeGeometry(sailShape);
        const sailMat = new THREE.MeshBasicMaterial({
            color: 0x44ffcc, transparent: true, opacity: 0.35, side: THREE.DoubleSide,
        });
        const sail = new THREE.Mesh(sailGeom, sailMat);
        sail.position.set(0.02, 0.2, -0.3);
        sail.rotation.y = Math.PI / 2;
        spaceGroup.add(sail);
        this.spaces.roarboot.sail = sail;

        // --- Water ripple ring ---
        const rippleGeom = new THREE.RingGeometry(1.8, 2.6, 32);
        const rippleMat = new THREE.MeshBasicMaterial({
            color: boatColor, transparent: true, opacity: 0.15, side: THREE.DoubleSide,
        });
        const ripple = new THREE.Mesh(rippleGeom, rippleMat);
        ripple.rotation.x = -Math.PI / 2;
        ripple.position.y = -0.3;
        spaceGroup.add(ripple);
        this.spaces.roarboot.ripple = ripple;

        // --- Glow sphere ---
        const glowGeom = new THREE.IcosahedronGeometry(2.5, 2);
        const glowMat = new THREE.MeshBasicMaterial({
            color: boatColor, transparent: true, opacity: 0.08, side: THREE.BackSide,
        });
        spaceGroup.add(new THREE.Mesh(glowGeom, glowMat));

        // --- Knowledge particles ---
        const pCount = 200;
        const pPos = new Float32Array(pCount * 3);
        for (let i = 0; i < pCount; i++) {
            const r = 2 + Math.random() * 2;
            const th = Math.random() * Math.PI * 2;
            const ph = Math.acos(2 * Math.random() - 1);
            pPos[i * 3]     = r * Math.sin(ph) * Math.cos(th);
            pPos[i * 3 + 1] = r * Math.sin(ph) * Math.sin(th);
            pPos[i * 3 + 2] = r * Math.cos(ph);
        }
        const pGeom = new THREE.BufferGeometry();
        pGeom.setAttribute('position', new THREE.BufferAttribute(pPos, 3));
        const pMat = new THREE.PointsMaterial({
            color: 0x66ffdd, size: 0.06, transparent: true, opacity: 0.6,
            blending: THREE.AdditiveBlending,
        });
        spaceGroup.add(new THREE.Points(pGeom, pMat));

        // --- Base marker ring ---
        const baseGeom = new THREE.RingGeometry(3, 3.4, 32);
        const baseMat = new THREE.MeshBasicMaterial({
            color: boatColor, transparent: true, opacity: 0.25, side: THREE.DoubleSide,
        });
        const base = new THREE.Mesh(baseGeom, baseMat);
        base.rotation.x = -Math.PI / 2;
        base.position.y = -2;
        spaceGroup.add(base);

        this.scene.add(spaceGroup);
        this.spaces.roarboot.group = spaceGroup;
    }

    // ========================================================================
    // SWE DESIGN FACTORY SPACE
    // ========================================================================

    createSweDesignSpace() {
        const spaceGroup = new THREE.Group();
        spaceGroup.position.copy(this.spaces.swedesign.position);

        const factoryColor = 0xff6633;

        // --- Factory Building (translucent box) ---
        const buildingGeom = new THREE.BoxGeometry(2.4, 1.8, 1.6);
        const buildingMat = new THREE.MeshPhongMaterial({
            color: factoryColor,
            transparent: true,
            opacity: 0.35,
            emissive: factoryColor,
            emissiveIntensity: 0.2,
            side: THREE.DoubleSide,
        });
        const building = new THREE.Mesh(buildingGeom, buildingMat);
        building.position.y = 0.9;
        building.userData = { type: 'factory', title: 'SWE Design Factory' };
        spaceGroup.add(building);
        this.spaces.swedesign.objects.push(building);
        this.spaces.swedesign.building = building;

        // --- Roof (slightly wider flat box) ---
        const roofGeom = new THREE.BoxGeometry(2.8, 0.15, 2.0);
        const roofMat = new THREE.MeshPhongMaterial({
            color: 0xcc5522,
            transparent: true,
            opacity: 0.6,
            emissive: 0xcc5522,
            emissiveIntensity: 0.15,
        });
        const roof = new THREE.Mesh(roofGeom, roofMat);
        roof.position.y = 1.85;
        spaceGroup.add(roof);

        // --- Smokestack 1 ---
        const stackGeom = new THREE.CylinderGeometry(0.15, 0.18, 1.2, 8);
        const stackMat = new THREE.MeshPhongMaterial({
            color: 0x884422,
            emissive: 0x663311,
            emissiveIntensity: 0.3,
        });
        const stack1 = new THREE.Mesh(stackGeom, stackMat);
        stack1.position.set(-0.6, 2.5, -0.4);
        spaceGroup.add(stack1);

        // --- Smokestack 2 ---
        const stack2 = new THREE.Mesh(stackGeom, stackMat);
        stack2.position.set(0.6, 2.5, -0.4);
        spaceGroup.add(stack2);

        // --- Smoke particles (rising from stacks) ---
        const smokeCount = 30;
        const smokePositions = new Float32Array(smokeCount * 3);
        for (let i = 0; i < smokeCount; i++) {
            smokePositions[i * 3] = (Math.random() - 0.5) * 0.3;
            smokePositions[i * 3 + 1] = Math.random() * 2.0;
            smokePositions[i * 3 + 2] = (Math.random() - 0.5) * 0.3;
        }
        const smokeGeom = new THREE.BufferGeometry();
        smokeGeom.setAttribute('position', new THREE.BufferAttribute(smokePositions, 3));
        const smokeMat = new THREE.PointsMaterial({
            size: 0.12,
            color: 0xffaa77,
            transparent: true,
            opacity: 0.4,
        });
        const smoke1 = new THREE.Points(smokeGeom, smokeMat);
        smoke1.position.set(-0.6, 3.1, -0.4);
        spaceGroup.add(smoke1);
        this.spaces.swedesign.smoke1 = smoke1;

        const smoke2 = new THREE.Points(smokeGeom.clone(), smokeMat.clone());
        smoke2.position.set(0.6, 3.1, -0.4);
        spaceGroup.add(smoke2);
        this.spaces.swedesign.smoke2 = smoke2;

        // --- Gear 1 (left side, visible through translucent wall) ---
        const gearGeom = new THREE.TorusGeometry(0.4, 0.08, 8, 12);
        const gearMat = new THREE.MeshPhongMaterial({
            color: 0xffcc44,
            emissive: 0xffaa22,
            emissiveIntensity: 0.3,
            transparent: true,
            opacity: 0.8,
        });
        const gear1 = new THREE.Mesh(gearGeom, gearMat);
        gear1.position.set(-0.5, 0.9, 0.82);
        spaceGroup.add(gear1);
        this.spaces.swedesign.gear1 = gear1;

        // --- Gear 2 (right side, interlocking) ---
        const gear2 = new THREE.Mesh(gearGeom, gearMat);
        gear2.position.set(0.5, 0.9, 0.82);
        spaceGroup.add(gear2);
        this.spaces.swedesign.gear2 = gear2;

        // --- Conveyor Belt (flat box from left to right) ---
        const conveyorGeom = new THREE.BoxGeometry(4.0, 0.08, 0.5);
        const conveyorMat = new THREE.MeshPhongMaterial({
            color: 0x886644,
            emissive: 0x553322,
            emissiveIntensity: 0.2,
            transparent: true,
            opacity: 0.6,
        });
        const conveyor = new THREE.Mesh(conveyorGeom, conveyorMat);
        conveyor.position.set(0, 0.04, 0.9);
        spaceGroup.add(conveyor);

        // --- Glow sphere (warm orange) ---
        const glowGeom = new THREE.IcosahedronGeometry(2.5, 2);
        const glowMat = new THREE.MeshBasicMaterial({
            color: factoryColor,
            transparent: true,
            opacity: 0.08,
            side: THREE.BackSide,
        });
        const glow = new THREE.Mesh(glowGeom, glowMat);
        spaceGroup.add(glow);

        // --- Base marker ring ---
        const baseGeom = new THREE.RingGeometry(2.5, 3, 32);
        const baseMat = new THREE.MeshBasicMaterial({
            color: factoryColor,
            transparent: true,
            opacity: 0.2,
            side: THREE.DoubleSide,
        });
        const base = new THREE.Mesh(baseGeom, baseMat);
        base.rotation.x = -Math.PI / 2;
        base.position.y = -2;
        spaceGroup.add(base);

        this.scene.add(spaceGroup);
        this.spaces.swedesign.group = spaceGroup;

        console.log('[Multiverse] SWE Design Factory created');
    }

    // ========================================================================
    // DASHBOARD (ClawPort) SPACE — Schülertafel
    // ========================================================================

    createDashboardSpace() {
        const spaceGroup = new THREE.Group();
        spaceGroup.position.copy(this.spaces.clawport.position);
        const dashColor = 0x8866ff;

        // --- Schülertafel (Chalkboard) — main visual element ---
        const boardGroup = new THREE.Group();
        boardGroup.position.set(0, 1.6, 0);

        // Board surface (dark green)
        const boardW = 3.2, boardH = 2.0, boardD = 0.06;
        const boardGeom = new THREE.BoxGeometry(boardW, boardH, boardD);
        const boardMat  = new THREE.MeshPhongMaterial({
            color: 0x1a3a1a,
            emissive: 0x0a1a0a,
            emissiveIntensity: 0.15,
            specular: 0x111111,
            shininess: 20,
        });
        const board = new THREE.Mesh(boardGeom, boardMat);
        boardGroup.add(board);

        // Wooden frame (4 bars)
        const frameMat = new THREE.MeshPhongMaterial({
            color: 0x8B5A2B,
            emissive: 0x3a2510,
            emissiveIntensity: 0.15,
        });
        const ft = 0.08;
        const topBar = new THREE.Mesh(new THREE.BoxGeometry(boardW + ft * 2, ft, boardD + 0.02), frameMat);
        topBar.position.y = boardH / 2 + ft / 2;
        boardGroup.add(topBar);
        const botBar = new THREE.Mesh(new THREE.BoxGeometry(boardW + ft * 2, ft, boardD + 0.02), frameMat);
        botBar.position.y = -(boardH / 2 + ft / 2);
        boardGroup.add(botBar);
        const leftBar = new THREE.Mesh(new THREE.BoxGeometry(ft, boardH, boardD + 0.02), frameMat);
        leftBar.position.x = -(boardW / 2 + ft / 2);
        boardGroup.add(leftBar);
        const rightBar = new THREE.Mesh(new THREE.BoxGeometry(ft, boardH, boardD + 0.02), frameMat);
        rightBar.position.x = boardW / 2 + ft / 2;
        boardGroup.add(rightBar);

        // Chalk tray
        const tray = new THREE.Mesh(
            new THREE.BoxGeometry(boardW * 0.8, 0.06, 0.18), frameMat);
        tray.position.set(0, -(boardH / 2 + ft + 0.02), boardD / 2 + 0.09);
        boardGroup.add(tray);

        // Stand legs (A-frame)
        const legMat = new THREE.MeshPhongMaterial({
            color: 0x6B4226, emissive: 0x2a1a0a, emissiveIntensity: 0.1,
        });
        const legGeom = new THREE.CylinderGeometry(0.04, 0.05, 2.8, 6);
        const legL = new THREE.Mesh(legGeom, legMat);
        legL.position.set(-1.2, -1.4, 0.1);
        legL.rotation.z = 0.08;
        boardGroup.add(legL);
        const legR = new THREE.Mesh(legGeom, legMat);
        legR.position.set(1.2, -1.4, 0.1);
        legR.rotation.z = -0.08;
        boardGroup.add(legR);
        // rear legs
        const rearGeom = new THREE.CylinderGeometry(0.035, 0.04, 2.4, 6);
        const rearL = new THREE.Mesh(rearGeom, legMat);
        rearL.position.set(-0.9, -1.2, -0.5);
        rearL.rotation.x = 0.25;
        boardGroup.add(rearL);
        const rearR = new THREE.Mesh(rearGeom, legMat);
        rearR.position.set(0.9, -1.2, -0.5);
        rearR.rotation.x = 0.25;
        boardGroup.add(rearR);

        // Canvas text on board
        const canvas = document.createElement('canvas');
        canvas.width  = 512;
        canvas.height = 320;
        const ctx = canvas.getContext('2d');
        ctx.fillStyle = '#1a3a1a';
        ctx.fillRect(0, 0, 512, 320);
        // Title
        ctx.fillStyle = '#e8e8d0';
        ctx.font = 'bold 42px "Segoe UI", Arial, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Dashboard', 256, 58);
        // Subtitle
        ctx.font = '22px "Segoe UI", Arial, sans-serif';
        ctx.fillStyle = '#ccccaa';
        ctx.fillText('System Monitor', 256, 95);
        // Separator
        ctx.strokeStyle = '#aaaaaa';
        ctx.lineWidth = 1.5;
        ctx.setLineDash([6, 4]);
        ctx.beginPath();
        ctx.moveTo(60, 115);
        ctx.lineTo(452, 115);
        ctx.stroke();
        // Bullet points
        ctx.setLineDash([]);
        ctx.fillStyle = '#bbbbaa';
        ctx.font = '20px "Segoe UI", Arial, sans-serif';
        ctx.textAlign = 'left';
        const items = [
            '📅  Schedule Monitor',
            '🤖  Agent Status',
            '💬  Chat Interface',
            '🧠  Memory Browser',
        ];
        items.forEach((txt, i) => {
            ctx.fillText(txt, 65, 150 + i * 36);
        });
        // Chalk dust marks
        ctx.fillStyle = 'rgba(255,255,255,0.12)';
        for (let i = 0; i < 20; i++) {
            ctx.fillRect(
                Math.random() * 480 + 16,
                Math.random() * 300 + 10,
                Math.random() * 12 + 2, 1);
        }

        const boardTexture = new THREE.CanvasTexture(canvas);
        const textPlane = new THREE.Mesh(
            new THREE.PlaneGeometry(boardW - 0.1, boardH - 0.1),
            new THREE.MeshBasicMaterial({ map: boardTexture, transparent: true })
        );
        textPlane.position.z = boardD / 2 + 0.005;
        boardGroup.add(textPlane);

        // Make the board clickable
        board.userData = { type: 'dashboard-board', title: 'Dashboard' };
        this.spaces.clawport.objects.push(board);

        spaceGroup.add(boardGroup);
        this.spaces.clawport.board = boardGroup;
        this.spaces.clawport.boardTexture = boardTexture;
        this.spaces.clawport.boardCanvas = canvas;

        // Glow sphere (purple)
        const glowGeom = new THREE.IcosahedronGeometry(2.5, 2);
        const glowMat = new THREE.MeshBasicMaterial({
            color: dashColor, transparent: true, opacity: 0.06, side: THREE.BackSide,
        });
        spaceGroup.add(new THREE.Mesh(glowGeom, glowMat));

        // Base ring
        const baseGeom = new THREE.RingGeometry(2.5, 3, 32);
        const baseMat = new THREE.MeshBasicMaterial({
            color: dashColor, transparent: true, opacity: 0.2, side: THREE.DoubleSide,
        });
        const base = new THREE.Mesh(baseGeom, baseMat);
        base.rotation.x = -Math.PI / 2;
        base.position.y = -2;
        spaceGroup.add(base);

        this.scene.add(spaceGroup);
        this.spaces.clawport.group = spaceGroup;

        console.log('[Multiverse] Dashboard Space (Chalkboard) created');
    }

    // ========================================================================
    // AGENT FARM SPACE (BAUERNHOF)
    // ========================================================================

    createAgentFarmSpace() {
        const spaceGroup = new THREE.Group();
        spaceGroup.position.copy(this.spaces.agentfarm.position);

        const farmColor = 0x88aa44;

        // --- Barn (main building) ---
        const barnGroup = new THREE.Group();
        barnGroup.position.set(0, 0, 0);

        // Barn body (red wooden barn)
        const barnBodyGeom = new THREE.BoxGeometry(2.4, 1.6, 1.8);
        const barnBodyMat = new THREE.MeshPhongMaterial({
            color: 0xaa3322,
            emissive: 0x441111,
            emissiveIntensity: 0.2,
        });
        const barnBody = new THREE.Mesh(barnBodyGeom, barnBodyMat);
        barnBody.position.y = 0.8;
        barnBody.userData = { type: 'agentfarm-barn', title: 'Agent Farm' };
        barnGroup.add(barnBody);
        this.spaces.agentfarm.objects.push(barnBody);

        // Barn roof (triangular prism)
        const roofShape = new THREE.Shape();
        roofShape.moveTo(-1.4, 0);
        roofShape.lineTo(0, 1.1);
        roofShape.lineTo(1.4, 0);
        roofShape.lineTo(-1.4, 0);
        const roofExtrudeSettings = { depth: 2.0, bevelEnabled: false };
        const roofGeom = new THREE.ExtrudeGeometry(roofShape, roofExtrudeSettings);
        const roofMat = new THREE.MeshPhongMaterial({
            color: 0x664422,
            emissive: 0x221100,
            emissiveIntensity: 0.1,
        });
        const roof = new THREE.Mesh(roofGeom, roofMat);
        roof.position.set(0, 1.6, -1.0);
        barnGroup.add(roof);

        // Barn door (dark opening)
        const doorGeom = new THREE.PlaneGeometry(0.6, 0.9);
        const doorMat = new THREE.MeshBasicMaterial({ color: 0x221111 });
        const door = new THREE.Mesh(doorGeom, doorMat);
        door.position.set(0, 0.45, 0.91);
        barnGroup.add(door);

        // Silo (cylinder next to barn)
        const siloGeom = new THREE.CylinderGeometry(0.35, 0.35, 2.2, 12);
        const siloMat = new THREE.MeshPhongMaterial({
            color: 0x888888,
            emissive: 0x222222,
            emissiveIntensity: 0.15,
        });
        const silo = new THREE.Mesh(siloGeom, siloMat);
        silo.position.set(1.6, 1.1, -0.3);
        barnGroup.add(silo);

        // Silo cap (dome)
        const siloCapGeom = new THREE.SphereGeometry(0.35, 12, 8, 0, Math.PI * 2, 0, Math.PI / 2);
        const siloCap = new THREE.Mesh(siloCapGeom, siloMat);
        siloCap.position.set(1.6, 2.2, -0.3);
        barnGroup.add(siloCap);

        spaceGroup.add(barnGroup);
        this.spaces.agentfarm.barn = barnGroup;

        // --- Fence (wooden fence around property) ---
        const fenceMat = new THREE.MeshPhongMaterial({
            color: 0x886633,
            emissive: 0x221100,
            emissiveIntensity: 0.1,
        });

        // Fence posts in a semicircle
        for (let i = 0; i < 8; i++) {
            const angle = (i / 8) * Math.PI + Math.PI / 2;
            const r = 3.0;
            const postGeom = new THREE.BoxGeometry(0.08, 0.6, 0.08);
            const post = new THREE.Mesh(postGeom, fenceMat);
            post.position.set(Math.cos(angle) * r, 0.3, Math.sin(angle) * r);
            spaceGroup.add(post);

            // Horizontal rail
            if (i < 7) {
                const nextAngle = ((i + 1) / 8) * Math.PI + Math.PI / 2;
                const railGeom = new THREE.BoxGeometry(0.04, 0.04, 1.2);
                const rail = new THREE.Mesh(railGeom, fenceMat);
                const mx = (Math.cos(angle) + Math.cos(nextAngle)) * r / 2;
                const mz = (Math.sin(angle) + Math.sin(nextAngle)) * r / 2;
                rail.position.set(mx, 0.4, mz);
                rail.lookAt(new THREE.Vector3(
                    Math.cos(nextAngle) * r + spaceGroup.position.x,
                    0.4 + spaceGroup.position.y,
                    Math.sin(nextAngle) * r + spaceGroup.position.z
                ));
                spaceGroup.add(rail);
            }
        }

        // --- Windmill ---
        const windmillGroup = new THREE.Group();
        windmillGroup.position.set(-2.0, 0, 1.5);

        // Windmill tower
        const towerGeom = new THREE.CylinderGeometry(0.15, 0.25, 2.0, 8);
        const towerMat = new THREE.MeshPhongMaterial({
            color: 0xccbb99,
            emissive: 0x332200,
            emissiveIntensity: 0.1,
        });
        const tower = new THREE.Mesh(towerGeom, towerMat);
        tower.position.y = 1.0;
        windmillGroup.add(tower);

        // Windmill blades (cross shape)
        const bladesGroup = new THREE.Group();
        bladesGroup.position.set(0, 2.1, 0.18);
        for (let i = 0; i < 4; i++) {
            const bladeGeom = new THREE.BoxGeometry(0.12, 0.9, 0.02);
            const bladeMat = new THREE.MeshBasicMaterial({
                color: 0xeeddcc,
                transparent: true,
                opacity: 0.8,
            });
            const blade = new THREE.Mesh(bladeGeom, bladeMat);
            blade.position.y = 0.5;
            blade.rotation.z = (i / 4) * Math.PI * 2;
            // Pivot each blade from center
            const bladeWrapper = new THREE.Group();
            bladeWrapper.add(blade);
            bladeWrapper.rotation.z = (i / 4) * Math.PI * 2;
            bladesGroup.add(bladeWrapper);
        }
        windmillGroup.add(bladesGroup);
        this.spaces.agentfarm.blades = bladesGroup;

        spaceGroup.add(windmillGroup);

        // --- Agent "animals" (small colored blobs wandering) ---
        const agentColors = [0xff6644, 0x44aaff, 0xffcc22, 0x44ff88, 0xaa66ff, 0xff4488];
        this.spaces.agentfarm.animals = [];
        for (let i = 0; i < 6; i++) {
            const animalGroup = new THREE.Group();

            // Body (small sphere)
            const bodyGeom = new THREE.SphereGeometry(0.15, 8, 6);
            const bodyMat = new THREE.MeshPhongMaterial({
                color: agentColors[i],
                emissive: agentColors[i],
                emissiveIntensity: 0.4,
            });
            const body = new THREE.Mesh(bodyGeom, bodyMat);
            body.position.y = 0.15;
            animalGroup.add(body);

            // Eyes (two tiny white spheres)
            const eyeGeom = new THREE.SphereGeometry(0.03, 6, 4);
            const eyeMat = new THREE.MeshBasicMaterial({ color: 0xffffff });
            const eyeL = new THREE.Mesh(eyeGeom, eyeMat);
            eyeL.position.set(-0.06, 0.2, 0.12);
            animalGroup.add(eyeL);
            const eyeR = new THREE.Mesh(eyeGeom, eyeMat);
            eyeR.position.set(0.06, 0.2, 0.12);
            animalGroup.add(eyeR);

            // Place around the farm
            const angle = (i / 6) * Math.PI * 2;
            const r = 1.5 + Math.random() * 0.5;
            animalGroup.position.set(Math.cos(angle) * r, 0, Math.sin(angle) * r);
            animalGroup.userData = {
                wanderAngle: angle,
                wanderSpeed: 0.3 + Math.random() * 0.4,
                wanderRadius: r,
                phase: Math.random() * Math.PI * 2,
            };

            spaceGroup.add(animalGroup);
            this.spaces.agentfarm.animals.push(animalGroup);
        }

        // --- Ground (green grass plane) ---
        const groundGeom = new THREE.CircleGeometry(4, 32);
        const groundMat = new THREE.MeshPhongMaterial({
            color: 0x44662a,
            emissive: 0x112200,
            emissiveIntensity: 0.1,
            side: THREE.DoubleSide,
        });
        const ground = new THREE.Mesh(groundGeom, groundMat);
        ground.rotation.x = -Math.PI / 2;
        ground.position.y = -0.01;
        spaceGroup.add(ground);

        // --- Glow sphere ---
        const glowGeom = new THREE.IcosahedronGeometry(3.0, 2);
        const glowMat = new THREE.MeshBasicMaterial({
            color: farmColor, transparent: true, opacity: 0.06, side: THREE.BackSide,
        });
        spaceGroup.add(new THREE.Mesh(glowGeom, glowMat));

        // --- Base marker ring ---
        const baseGeom = new THREE.RingGeometry(3.5, 3.8, 32);
        const baseMat = new THREE.MeshBasicMaterial({
            color: farmColor, transparent: true, opacity: 0.2, side: THREE.DoubleSide,
        });
        const base = new THREE.Mesh(baseGeom, baseMat);
        base.rotation.x = -Math.PI / 2;
        base.position.y = -2;
        spaceGroup.add(base);

        this.scene.add(spaceGroup);
        this.spaces.agentfarm.group = spaceGroup;

        console.log('[Multiverse] Agent Farm Space (Bauernhof) created');
    }

    // ========================================================================
    // VIDEO STUDIO SPACE (FILMSTUDIO)
    // ========================================================================

    createVideoSpace() {
        const spaceGroup = new THREE.Group();
        spaceGroup.position.copy(this.spaces.video.position);

        const studioColor = 0xee4466;

        // --- Studio building (flat wide box) ---
        const studioGeom = new THREE.BoxGeometry(3.5, 1.8, 2.5);
        const studioMat = new THREE.MeshPhongMaterial({
            color: 0x2a2a3a,
            transparent: true,
            opacity: 0.85,
        });
        const studio = new THREE.Mesh(studioGeom, studioMat);
        studio.position.y = 0.9;
        studio.userData = { type: 'video-studio', title: 'Video Studio' };
        spaceGroup.add(studio);
        this.spaces.video.objects.push(studio);

        // --- Film clapperboard on top ---
        const clapGeom = new THREE.BoxGeometry(1.2, 0.08, 0.8);
        const clapMat = new THREE.MeshPhongMaterial({ color: 0x111111 });
        const clap = new THREE.Mesh(clapGeom, clapMat);
        clap.position.set(0, 1.85, 0);
        spaceGroup.add(clap);

        // Clapperboard stripes (red/white)
        const stripeGeom = new THREE.BoxGeometry(1.2, 0.06, 0.35);
        const stripeMat = new THREE.MeshPhongMaterial({ color: studioColor });
        const stripe = new THREE.Mesh(stripeGeom, stripeMat);
        stripe.position.set(0, 1.92, -0.15);
        stripe.rotation.x = -0.15;
        spaceGroup.add(stripe);
        this.spaces.video.clap = stripe;

        // --- Camera on tripod (right side) ---
        const tripodGeom = new THREE.CylinderGeometry(0.03, 0.05, 1.2, 6);
        const tripodMat = new THREE.MeshPhongMaterial({ color: 0x444444 });
        const tripod = new THREE.Mesh(tripodGeom, tripodMat);
        tripod.position.set(2.2, 0.6, 0);
        spaceGroup.add(tripod);

        const cameraGeom = new THREE.BoxGeometry(0.4, 0.3, 0.5);
        const cameraMat = new THREE.MeshPhongMaterial({ color: 0x222222 });
        const camera = new THREE.Mesh(cameraGeom, cameraMat);
        camera.position.set(2.2, 1.3, 0);
        spaceGroup.add(camera);

        // Camera lens (small cylinder)
        const lensGeom = new THREE.CylinderGeometry(0.08, 0.1, 0.2, 8);
        const lensMat = new THREE.MeshPhongMaterial({ color: 0x3366aa, emissive: 0x112244, emissiveIntensity: 0.5 });
        const lens = new THREE.Mesh(lensGeom, lensMat);
        lens.rotation.z = Math.PI / 2;
        lens.position.set(2.2, 1.3, -0.35);
        spaceGroup.add(lens);

        // --- Spotlight (left side, angled) ---
        const spotPoleGeom = new THREE.CylinderGeometry(0.03, 0.04, 1.8, 6);
        const spotPole = new THREE.Mesh(spotPoleGeom, tripodMat);
        spotPole.position.set(-2.0, 0.9, 0.5);
        spaceGroup.add(spotPole);

        const spotLightGeom = new THREE.ConeGeometry(0.2, 0.35, 8);
        const spotLightMat = new THREE.MeshPhongMaterial({ color: 0xffdd44, emissive: 0xffaa00, emissiveIntensity: 0.8 });
        const spotLight = new THREE.Mesh(spotLightGeom, spotLightMat);
        spotLight.position.set(-2.0, 1.9, 0.5);
        spotLight.rotation.z = 0.3;
        spaceGroup.add(spotLight);
        this.spaces.video.spotlight = spotLight;

        // --- Ground (dark studio floor) ---
        const groundGeom = new THREE.CircleGeometry(5, 32);
        const groundMat = new THREE.MeshPhongMaterial({
            color: 0x1a1a2a,
            transparent: true,
            opacity: 0.6,
        });
        const ground = new THREE.Mesh(groundGeom, groundMat);
        ground.rotation.x = -Math.PI / 2;
        ground.position.y = 0.01;
        spaceGroup.add(ground);

        // --- Accent ring ---
        const ringGeom = new THREE.RingGeometry(4.5, 5, 48);
        const ringMat = new THREE.MeshBasicMaterial({
            color: studioColor,
            transparent: true,
            opacity: 0.25,
            side: THREE.DoubleSide,
        });
        const ring = new THREE.Mesh(ringGeom, ringMat);
        ring.rotation.x = -Math.PI / 2;
        ring.position.y = 0.02;
        spaceGroup.add(ring);

        // --- Base marker ring ---
        const baseGeom = new THREE.RingGeometry(4.5, 4.8, 32);
        const baseMat = new THREE.MeshBasicMaterial({
            color: studioColor, transparent: true, opacity: 0.2, side: THREE.DoubleSide,
        });
        const base = new THREE.Mesh(baseGeom, baseMat);
        base.rotation.x = -Math.PI / 2;
        base.position.y = -2;
        spaceGroup.add(base);

        this.scene.add(spaceGroup);
        this.spaces.video.group = spaceGroup;

        console.log('[Multiverse] Video Studio Space created');
    }

    // ========================================================================
    // THE BRAIN SPACE (GEHIRN)
    // ========================================================================

    createBrainSpace() {
        const spaceGroup = new THREE.Group();
        spaceGroup.position.copy(this.spaces.thebrain.position);

        const brainColor = 0xff66aa;

        // --- Brain (organic deformed sphere) ---
        const brainGroup = new THREE.Group();
        brainGroup.position.set(0, 1.8, 0);

        // Main brain shape (icosahedron for organic look)
        const brainGeom = new THREE.IcosahedronGeometry(1.2, 3);
        // Deform vertices for organic brain wrinkles
        const positions = brainGeom.attributes.position;
        for (let i = 0; i < positions.count; i++) {
            const x = positions.getX(i);
            const y = positions.getY(i);
            const z = positions.getZ(i);
            const noise = Math.sin(x * 5) * Math.cos(y * 4) * Math.sin(z * 6) * 0.08;
            const fissure = Math.sin(x * 12 + y * 8) * 0.04;
            const len = Math.sqrt(x * x + y * y + z * z);
            const scale = 1 + noise + fissure;
            positions.setXYZ(i, x / len * 1.2 * scale, y / len * 1.0 * scale, z / len * 1.1 * scale);
        }
        brainGeom.computeVertexNormals();

        const brainMat = new THREE.MeshPhongMaterial({
            color: 0xee8899,
            emissive: 0x662244,
            emissiveIntensity: 0.3,
            shininess: 30,
            transparent: true,
            opacity: 0.85,
        });
        const brain = new THREE.Mesh(brainGeom, brainMat);
        brain.userData = { type: 'thebrain', title: 'The Brain' };
        brainGroup.add(brain);
        this.spaces.thebrain.objects.push(brain);
        this.spaces.thebrain.brain = brain;

        // Brain center fissure line (median line)
        const fissureGeom = new THREE.BoxGeometry(0.02, 1.0, 1.4);
        const fissureMat = new THREE.MeshBasicMaterial({
            color: 0xcc5577, transparent: true, opacity: 0.5,
        });
        const fissure = new THREE.Mesh(fissureGeom, fissureMat);
        fissure.position.y = 0.15;
        brainGroup.add(fissure);

        spaceGroup.add(brainGroup);
        this.spaces.thebrain.brainGroup = brainGroup;

        // --- Neural network (synaptic connections) ---
        const neuronCount = 60;
        const neuronPositions = new Float32Array(neuronCount * 3);
        for (let i = 0; i < neuronCount; i++) {
            const r = 2.0 + Math.random() * 2.0;
            const theta = Math.random() * Math.PI * 2;
            const phi = Math.acos(2 * Math.random() - 1);
            neuronPositions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
            neuronPositions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta) + 1.5;
            neuronPositions[i * 3 + 2] = r * Math.cos(phi);
        }
        const neuronGeom = new THREE.BufferGeometry();
        neuronGeom.setAttribute('position', new THREE.BufferAttribute(neuronPositions, 3));
        const neuronMat = new THREE.PointsMaterial({
            color: 0xff88cc, size: 0.08, transparent: true, opacity: 0.7,
            blending: THREE.AdditiveBlending,
        });
        const neurons = new THREE.Points(neuronGeom, neuronMat);
        spaceGroup.add(neurons);
        this.spaces.thebrain.neurons = neurons;

        // --- Synaptic connection lines (firing neurons) ---
        const lineCount = 30;
        const lineMat = new THREE.LineBasicMaterial({
            color: 0xff99dd, transparent: true, opacity: 0.2,
        });
        this.spaces.thebrain.synapses = [];
        for (let i = 0; i < lineCount; i++) {
            const a = Math.floor(Math.random() * neuronCount);
            const b = Math.floor(Math.random() * neuronCount);
            const lineGeom = new THREE.BufferGeometry();
            const pts = new Float32Array(6);
            pts[0] = neuronPositions[a * 3];
            pts[1] = neuronPositions[a * 3 + 1];
            pts[2] = neuronPositions[a * 3 + 2];
            pts[3] = neuronPositions[b * 3];
            pts[4] = neuronPositions[b * 3 + 1];
            pts[5] = neuronPositions[b * 3 + 2];
            lineGeom.setAttribute('position', new THREE.BufferAttribute(pts, 3));
            const line = new THREE.Line(lineGeom, lineMat.clone());
            spaceGroup.add(line);
            this.spaces.thebrain.synapses.push(line);
        }

        // --- Brain stem (cylinder going downward) ---
        const stemGeom = new THREE.CylinderGeometry(0.2, 0.15, 1.2, 8);
        const stemMat = new THREE.MeshPhongMaterial({
            color: 0xdd7788,
            emissive: 0x441122,
            emissiveIntensity: 0.2,
        });
        const stem = new THREE.Mesh(stemGeom, stemMat);
        stem.position.set(0, 0.4, -0.2);
        spaceGroup.add(stem);

        // --- Thought bubbles (floating ideas) ---
        this.spaces.thebrain.thoughtBubbles = [];
        for (let i = 0; i < 5; i++) {
            const bubbleGeom = new THREE.SphereGeometry(0.12 + Math.random() * 0.1, 8, 6);
            const bubbleMat = new THREE.MeshBasicMaterial({
                color: 0xffaadd, transparent: true, opacity: 0.3 + Math.random() * 0.2,
            });
            const bubble = new THREE.Mesh(bubbleGeom, bubbleMat);
            const angle = (i / 5) * Math.PI * 2;
            bubble.position.set(
                Math.cos(angle) * 2.5,
                2.5 + Math.random() * 1.5,
                Math.sin(angle) * 2.5
            );
            bubble.userData = {
                floatPhase: Math.random() * Math.PI * 2,
                floatSpeed: 0.5 + Math.random() * 0.5,
                baseY: bubble.position.y,
            };
            spaceGroup.add(bubble);
            this.spaces.thebrain.thoughtBubbles.push(bubble);
        }

        // --- Glow sphere ---
        const glowGeom = new THREE.IcosahedronGeometry(3.5, 2);
        const glowMat = new THREE.MeshBasicMaterial({
            color: brainColor, transparent: true, opacity: 0.06, side: THREE.BackSide,
        });
        spaceGroup.add(new THREE.Mesh(glowGeom, glowMat));

        // --- Base marker ring ---
        const baseGeom = new THREE.RingGeometry(3.5, 3.8, 32);
        const baseMat = new THREE.MeshBasicMaterial({
            color: brainColor, transparent: true, opacity: 0.2, side: THREE.DoubleSide,
        });
        const base = new THREE.Mesh(baseGeom, baseMat);
        base.rotation.x = -Math.PI / 2;
        base.position.y = -2;
        spaceGroup.add(base);

        this.scene.add(spaceGroup);
        this.spaces.thebrain.group = spaceGroup;

        console.log('[Multiverse] Brain Space (Gehirn) created');
    }

    // ========================================================================
    // ENVIRONMENT
    // ========================================================================
    
    createEnvironment() {
        // Stars
        const starCount = 2000;
        const starPositions = new Float32Array(starCount * 3);
        
        for (let i = 0; i < starCount; i++) {
            const radius = 50 + Math.random() * 50;
            const theta = Math.random() * Math.PI * 2;
            const phi = Math.acos(2 * Math.random() - 1);
            
            starPositions[i * 3] = radius * Math.sin(phi) * Math.cos(theta);
            starPositions[i * 3 + 1] = radius * Math.sin(phi) * Math.sin(theta);
            starPositions[i * 3 + 2] = radius * Math.cos(phi);
        }
        
        const starGeometry = new THREE.BufferGeometry();
        starGeometry.setAttribute('position', new THREE.BufferAttribute(starPositions, 3));
        
        const starMaterial = new THREE.PointsMaterial({
            size: 0.1,
            color: 0xffffff,
            transparent: true,
            opacity: 0.6
        });
        
        this.scene.add(new THREE.Points(starGeometry, starMaterial));
        
        // Lighting
        const ambient = new THREE.AmbientLight(0x222233, 0.5);
        this.scene.add(ambient);
        
        const ideasLight = new THREE.PointLight(0x4488ff, 1, 20);
        ideasLight.position.copy(this.spaces.ideas.position);
        this.scene.add(ideasLight);
        
        const desktopLight = new THREE.PointLight(0xff8844, 1, 20);
        desktopLight.position.copy(this.spaces.desktop.position);
        this.scene.add(desktopLight);
        
        // Add light for Project Space
        const projectLight = new THREE.PointLight(0x44ff88, 1, 20);
        projectLight.position.copy(this.spaces.projects.position);
        this.scene.add(projectLight);

        // Add light for Roarboot Space
        const roarbootLight = new THREE.PointLight(0x22ccaa, 1, 20);
        roarbootLight.position.copy(this.spaces.roarboot.position);
        this.scene.add(roarbootLight);

        // Add light for SWE Design Factory
        const factoryLight = new THREE.PointLight(0xff6633, 1, 20);
        factoryLight.position.copy(this.spaces.swedesign.position);
        factoryLight.position.y += 2; // Above the building
        this.scene.add(factoryLight);
    }
    
    createConnectionPaths() {
        // Path 1: Ideas -> Factory (main shuttle route, orange)
        this.createSinglePath(
            this.spaces.ideas.position,
            this.spaces.swedesign.position,
            0xff8844,
            0.5
        );

        // Path 2: Factory -> Projects (output route, green)
        this.createSinglePath(
            this.spaces.swedesign.position,
            this.spaces.projects.position,
            0x88cc44,
            0.4
        );

        // Path 3: Ideas -> Projects (legacy direct, very subtle)
        this.createSinglePath(
            this.spaces.ideas.position,
            this.spaces.projects.position,
            0x5588aa,
            0.15
        );

        // Path 4: Projects -> Desktop
        this.createSinglePath(
            this.spaces.projects.position,
            this.spaces.desktop.position,
            0x88aa55
        );

        // Path 5: Ideas -> Desktop (long path, subtle)
        this.createSinglePath(
            this.spaces.ideas.position,
            this.spaces.desktop.position,
            0x6688aa,
            0.2
        );

        // Path 6: Ideas -> Roarboot
        this.createSinglePath(
            this.spaces.ideas.position,
            this.spaces.roarboot.position,
            0x33aa99,
            0.3
        );
    }
    
    createSinglePath(start, end, color, opacity = 0.4) {
        const mid = new THREE.Vector3(
            (start.x + end.x) / 2,
            3,
            (start.z + end.z) / 2
        );
        
        const curve = new THREE.QuadraticBezierCurve3(start.clone(), mid, end.clone());
        const points = curve.getPoints(50);
        
        const pathGeometry = new THREE.BufferGeometry().setFromPoints(points);
        const pathMaterial = new THREE.LineDashedMaterial({
            color: color,
            dashSize: 0.3,
            gapSize: 0.2,
            transparent: true,
            opacity: opacity
        });
        
        const path = new THREE.Line(pathGeometry, pathMaterial);
        path.computeLineDistances();
        this.scene.add(path);
    }
    
    // Keep old method for backwards compatibility
    createConnectionPath() {
        this.createSinglePath(
            this.spaces.ideas.position,
            this.spaces.projects.position,
            0x5588aa
        );
        this.createSinglePath(
            this.spaces.projects.position,
            this.spaces.desktop.position,
            0x88aa55
        );
    }
    
    // ========================================================================
    // NAVIGATION
    // ========================================================================
    
    navigateToSpace(targetSpace) {
        if (this.isNavigating || targetSpace === this.currentSpace) {
            return;
        }

        console.log('[Multiverse] Navigating to:', targetSpace);
        this.isNavigating = true;

        // Apply space theme to CSS custom properties
        const SPACE_ACCENT_RGB = {
            ideas:     '68,136,255',
            projects:  '68,255,136',
            desktop:   '255,136,68',
            roarboot:  '34,204,170',
            swedesign: '255,102,51',
            clawport:  '136,102,255',
            agentfarm: '136,170,68',
            video:     '238,68,102',
            thebrain:  '255,102,170',
        };
        const accentRgb = SPACE_ACCENT_RGB[targetSpace] || SPACE_ACCENT_RGB.ideas;
        document.documentElement.style.setProperty('--space-accent-rgb', accentRgb);
        const hexColor = this.spaces[targetSpace]?.color;
        document.documentElement.style.setProperty('--space-accent',
            hexColor ? '#' + hexColor.toString(16).padStart(6, '0') : '#4488ff');

        // Update game console agent badge
        this.updateGameConsoleAgent(targetSpace);

        const space = this.spaces[targetSpace];
        if (!space) {
            console.error('[Multiverse] Unknown space:', targetSpace);
            this.isNavigating = false;
            return;
        }

        // Hide dashboard if we're leaving projects space
        if (this.currentSpace === 'projects' && targetSpace !== 'projects') {
            if (window.vibemind && window.vibemind.hideDashboard) {
                window.vibemind.hideDashboard();
                console.log('[Multiverse] Hiding Coding Engine Dashboard');
            }
        }

        // Hide Rowboat BrowserView when leaving roarboot space
        if (this.currentSpace === 'roarboot' && targetSpace !== 'roarboot') {
            if (window.vibemind && window.vibemind.hideRowboat) {
                window.vibemind.hideRowboat();
                console.log('[Multiverse] Hiding Rowboat BrowserView');
            }
        }

        // Hide SWE Design BrowserView when leaving swedesign space
        if (this.currentSpace === 'swedesign' && targetSpace !== 'swedesign') {
            if (window.vibemind && window.vibemind.hideSweDesign) {
                window.vibemind.hideSweDesign();
                console.log('[Multiverse] Hiding SWE Design BrowserView');
            }
        }

        // Hide ClawPort Dashboard BrowserView when leaving clawport space
        if (this.currentSpace === 'clawport' && targetSpace !== 'clawport') {
            if (window.vibemind && window.vibemind.hideClawPort) {
                window.vibemind.hideClawPort();
                console.log('[Multiverse] Hiding ClawPort Dashboard');
            }
        }

        // Hide Brain Dashboard BrowserView when leaving thebrain space
        if (this.currentSpace === 'thebrain' && targetSpace !== 'thebrain') {
            if (window.vibemind && window.vibemind.hideBrain) {
                window.vibemind.hideBrain();
                console.log('[Multiverse] Hiding Brain Dashboard');
            }
        }

        // Hide Agent Farm BrowserView when leaving agentfarm or video space
        if ((this.currentSpace === 'agentfarm' || this.currentSpace === 'video') &&
            targetSpace !== 'agentfarm' && targetSpace !== 'video') {
            if (window.vibemind && window.vibemind.hideAgentFarm) {
                window.vibemind.hideAgentFarm();
                console.log('[Multiverse] Hiding Agent Farm');
            }
        }

        // Hide Desktop Dashboard when leaving desktop space
        if (this.currentSpace === 'desktop' && targetSpace !== 'desktop') {
            if (this._insideDesktopDashboard) {
                const panel = document.getElementById('vapi-panel');
                if (panel) {
                    panel.classList.remove('fade-in', 'visible');
                }
                this._insideDesktopDashboard = false;
            }
        }

        // Calculate camera target
        const targetPos = space.position.clone();
        targetPos.z += 10;
        targetPos.y += 2;

        // Animate camera
        this.animateCameraTo(targetPos, space.position, () => {
            this.currentSpace = targetSpace;
            this.currentAgent = space.agent.slug;
            this.isNavigating = false;

            // Show dashboard when entering projects space
            if (targetSpace === 'projects') {
                if (window.vibemind && window.vibemind.showDashboard) {
                    window.vibemind.showDashboard();
                    console.log('[Multiverse] Showing Coding Engine Dashboard');
                }
            }

            // Show Rowboat BrowserView when entering roarboot space
            if (targetSpace === 'roarboot') {
                if (window.vibemind && window.vibemind.showRowboat) {
                    window.vibemind.showRowboat();
                    console.log('[Multiverse] Showing Rowboat BrowserView');
                }
            }

            // Show SWE Design BrowserView when entering swedesign space
            if (targetSpace === 'swedesign') {
                if (window.vibemind && window.vibemind.showSweDesign) {
                    window.vibemind.showSweDesign();
                    console.log('[Multiverse] Showing SWE Design BrowserView');
                }
            }

            // Show ClawPort Dashboard BrowserView when entering clawport space
            if (targetSpace === 'clawport') {
                if (window.vibemind && window.vibemind.showClawPort) {
                    window.vibemind.showClawPort();
                    console.log('[Multiverse] Showing ClawPort Dashboard');
                }
            }

            // Show Brain Dashboard BrowserView when entering thebrain space
            if (targetSpace === 'thebrain') {
                if (window.vibemind && window.vibemind.showBrain) {
                    window.vibemind.showBrain();
                    console.log('[Multiverse] Showing Brain Dashboard');
                }
            }

            // Show Agent Farm BrowserView when entering agentfarm space
            if (targetSpace === 'agentfarm') {
                if (window.vibemind && window.vibemind.showAgentFarm) {
                    window.vibemind.showAgentFarm();
                    console.log('[Multiverse] Showing Agent Farm');
                }
            }

            // Show Agent Farm with Video tab when entering video space
            if (targetSpace === 'video') {
                if (window.vibemind && window.vibemind.showAgentFarmTab) {
                    window.vibemind.showAgentFarmTab('video');
                    console.log('[Multiverse] Showing Agent Farm (Video tab)');
                }
            }

            // Notify IPC
            if (window.vibemind) {
                window.vibemind.navigateToSpace(targetSpace);
            }
        });
    }
    
    animateCameraTo(targetPosition, lookAtPosition, onComplete) {
        const startPosition = this.camera.position.clone();
        const startLookAt = this.controls.target.clone();
        const duration = 1500;
        const startTime = Date.now();
        
        const updateCamera = () => {
            const elapsed = Date.now() - startTime;
            const progress = Math.min(elapsed / duration, 1);
            
            // Ease in-out
            const eased = progress < 0.5
                ? 2 * progress * progress
                : 1 - Math.pow(-2 * progress + 2, 2) / 2;
            
            this.camera.position.lerpVectors(startPosition, targetPosition, eased);
            this.controls.target.lerpVectors(startLookAt, lookAtPosition, eased);
            
            if (progress < 1) {
                requestAnimationFrame(updateCamera);
            } else if (onComplete) {
                onComplete();
            }
        };
        
        updateCamera();
    }

    // ========================================================================
    // GAME CONSOLE CHAT OVERLAY
    // ========================================================================

    initGameConsole() {
        this.gcVisible = false;
        this.gcBusy = false;
        this.gcMessages = [];
        this.GC_MAX_MESSAGES = 5;
        this.GC_FADE_DELAY = 8000;

        const input = document.getElementById('gc-input');
        const sendBtn = document.getElementById('gc-send-btn');

        // Toggle with 'c' key (for chat) — only when not typing in an input
        document.addEventListener('keydown', (e) => {
            if (e.key === 'c' && !e.ctrlKey && !e.metaKey && document.activeElement.tagName !== 'INPUT') {
                e.preventDefault();
                this.toggleGameConsole();
                return;
            }
            if (e.key === 'Escape' && this.gcVisible) {
                input.value = '';
                input.blur();
            }
        });

        // Enter sends
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendGameConsoleMessage();
            }
            // Stop propagation so Three.js keyboard controls don't fire
            e.stopPropagation();
        });

        // Send button click
        sendBtn.addEventListener('click', () => this.sendGameConsoleMessage());

        console.log('[Multiverse] Game console initialized (press ` to toggle)');
    }

    toggleGameConsole() {
        const el = document.getElementById('game-console');
        this.gcVisible = !this.gcVisible;
        el.classList.toggle('hidden', !this.gcVisible);

        // Shift voice panel to avoid overlap
        const voicePanel = document.getElementById('voice-panel');
        if (voicePanel) {
            voicePanel.style.bottom = this.gcVisible ? '90px' : '20px';
            voicePanel.style.transition = 'bottom 0.25s ease';
        }

        if (this.gcVisible) {
            document.getElementById('gc-input').focus();
        }
    }

    async sendGameConsoleMessage() {
        const input = document.getElementById('gc-input');
        const text = input.value.trim();
        if (!text || this.gcBusy) return;

        input.value = '';
        this.gcBusy = true;

        // Show user message
        this.addGcMessage(text, 'user');

        // Show spinner, hide send button
        document.getElementById('gc-spinner').classList.remove('hidden');
        document.getElementById('gc-send-btn').classList.add('hidden');

        try {
            const response = await window.vibemind.sendChatMessage(text);
            const agentMsg = response?.message || 'No response';
            const isError = response?.success === false;
            this.addGcMessage(agentMsg, isError ? 'error' : 'agent');
        } catch (err) {
            this.addGcMessage(`Error: ${err.message}`, 'error');
        } finally {
            this.gcBusy = false;
            document.getElementById('gc-spinner').classList.add('hidden');
            document.getElementById('gc-send-btn').classList.remove('hidden');
        }
    }

    addGcMessage(text, type) {
        const container = document.getElementById('gc-messages');
        const div = document.createElement('div');
        div.className = `gc-msg gc-${type}`;
        div.textContent = text;
        container.appendChild(div);

        this.gcMessages.push(div);

        // Trim to max messages
        while (this.gcMessages.length > this.GC_MAX_MESSAGES) {
            const old = this.gcMessages.shift();
            old.remove();
        }

        // Auto-scroll
        container.scrollTop = container.scrollHeight;

        // Auto-fade after delay
        setTimeout(() => {
            div.classList.add('gc-fading');
            setTimeout(() => {
                div.remove();
                const idx = this.gcMessages.indexOf(div);
                if (idx !== -1) this.gcMessages.splice(idx, 1);
            }, 500);
        }, this.GC_FADE_DELAY);
    }

    updateGameConsoleAgent(spaceId) {
        const space = this.spaces[spaceId];
        if (!space) return;
        const nameEl = document.getElementById('gc-agent-name');
        const iconEl = document.getElementById('gc-agent-icon');
        if (nameEl) nameEl.textContent = space.agent.name;
        if (iconEl) iconEl.textContent = space.icon;
    }

    // ========================================================================
    // HAND TRACKING
    // ========================================================================
    
    connectHandTracking() {
        // Reset attempt flag to allow connection
        this.handSocketAttempted = false;
        this._connectHandTrackingInternal();
    }
    
    _connectHandTrackingInternal() {
        if (this.handSocketAttempted && !this.handSocketConnected) {
            // Don't spam reconnect on initial failure
            return;
        }
        this.handSocketAttempted = true;
        
        try {
            this.handSocket = new WebSocket('ws://localhost:8766');
            
            this.handSocket.onopen = () => {
                console.log('[Multiverse] Hand tracking connected ✓');
                this._updateHandStatus(true, 'Tracking...');
                this.handSocketConnected = true;
            };
            
            this.handSocket.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleHandGesture(data);
                    
                    // Update gesture display
                    const gestureName = document.getElementById('gesture-name');
                    if (gestureName && data.gesture) {
                        gestureName.textContent = data.gesture;
                    }
                } catch (e) {
                    // Silent ignore parse errors
                }
            };
            
            this.handSocket.onerror = () => {
                this._updateHandStatus(false, 'Not Available');
            };
            
            this.handSocket.onclose = () => {
                this._updateHandStatus(false, 'Disconnected');
                this.handSocketConnected = false;
                
                // Auto-reconnect after 5 seconds if was previously connected
                if (this.handSocketAttempted) {
                    setTimeout(() => {
                        console.log('[Multiverse] Attempting hand tracking reconnect...');
                        this._connectHandTrackingInternal();
                    }, 5000);
                }
            };
        } catch (e) {
            this._updateHandStatus(false, 'Unavailable');
        }
    }
    
    _updateHandStatus(connected, text) {
        const statusEl = document.getElementById('hand-status');
        const gestureNameEl = document.getElementById('gesture-name');
        
        if (statusEl) {
            if (connected) {
                statusEl.classList.add('active');
            } else {
                statusEl.classList.remove('active');
            }
        }
        if (gestureNameEl) {
            gestureNameEl.textContent = text || 'Tracking...';
        }
    }
    
    /**
     * Handle hand gestures - SIMPLIFIED to only SWIPE_LEFT and SWIPE_RIGHT
     * for space navigation.
     */
    handleHandGesture(data) {
        const { gesture, position, hand_position } = data;
        
        // Update Light Planet morph based on hand position (visual effect)
        if (this.currentSpace === 'desktop' && this.spaces.desktop.planet) {
            const pos = hand_position || position;
            if (pos) {
                const handVec = new THREE.Vector3(
                    (pos.x - 0.5) * 4,
                    (0.5 - pos.y) * 4,
                    0
                );
                this.spaces.desktop.planet.material.uniforms.u_handPos.value.copy(handVec);
            }
        }
        
        // SIMPLIFIED: Only handle swipe gestures for navigation
        if (gesture === 'SWIPE_LEFT') {
            console.log('[Multiverse] Swipe Left detected - navigating to previous space');
            this._navigateToPreviousSpace();
        } else if (gesture === 'SWIPE_RIGHT') {
            console.log('[Multiverse] Swipe Right detected - navigating to next space');
            this._navigateToNextSpace();
        }
    }
    
    /**
     * Navigate to the previous space (circular)
     */
    _navigateToPreviousSpace() {
        if (this.isNavigating) return;
        
        const spaceKeys = Object.keys(this.spaces);
        const currentIndex = spaceKeys.indexOf(this.currentSpace);
        const prevIndex = (currentIndex - 1 + spaceKeys.length) % spaceKeys.length;
        const prevSpace = spaceKeys[prevIndex];
        
        this.navigateToSpace(prevSpace);
    }
    
    /**
     * Navigate to the next space (circular)
     */
    _navigateToNextSpace() {
        if (this.isNavigating) return;
        
        const spaceKeys = Object.keys(this.spaces);
        const currentIndex = spaceKeys.indexOf(this.currentSpace);
        const nextIndex = (currentIndex + 1) % spaceKeys.length;
        const nextSpace = spaceKeys[nextIndex];
        
        this.navigateToSpace(nextSpace);
    }
    
    // ========================================================================
    // KEYBOARD INPUT
    // ========================================================================
    
    onKeyDown(e) {
        switch (e.key) {
            case 'Enter':
                // Enter current selection
                this.enterCurrentSelection();
                break;
            case 'Escape':
                // Exit desktop dashboard or bubble view
                if (this._insideDesktopDashboard) {
                    this.exitDesktopDashboard();
                } else {
                    this.exitBubbleWithAnimation();
                }
                break;
            case 'ArrowLeft':
                // Navigate to Ideas Space
                if (!this.isNavigating) {
                    this.navigateToSpace('ideas');
                }
                break;
            case 'ArrowUp':
                // Navigate to Project Space
                if (!this.isNavigating) {
                    this.navigateToSpace('projects');
                }
                break;
            case 'ArrowRight':
                // Navigate to Desktop Space
                if (!this.isNavigating) {
                    this.navigateToSpace('desktop');
                }
                break;
            case 'Tab':
                // Cycle through items based on current space
                e.preventDefault();
                if (this.currentSpace === 'projects') {
                    this.selectNextProject(e.shiftKey ? -1 : 1);
                } else {
                    this.selectNextBubble(e.shiftKey ? -1 : 1);
                }
                break;
        }
    }
    
    // ========================================================================
    // Window RESIZE
    // ========================================================================
    
    /**
     * Handle window resize events - updates camera and renderer dimensions
     */
    onWindowResize() {
        if (!this.container || !this.camera || !this.renderer) {
            return;
        }
        
        const width = this.container.clientWidth;
        const height = this.container.clientHeight;
        
        // Update camera aspect ratio
        this.camera.aspect = width / height;
        this.camera.updateProjectionMatrix();
        
        // Update renderer size
        this.renderer.setSize(width, height);
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    }
    
    // ========================================================================
    // ANIMATION LOOP
    // ========================================================================
    
    /**
     * Main animation loop - renders the scene and updates animations
     */
    animate() {
        requestAnimationFrame(() => this.animate());
        
        const delta = this.clock.getDelta();
        const elapsed = this.clock.getElapsedTime();
        
        // Update controls
        if (this.controls) {
            this.controls.update();
        }
        
        // Update shader uniforms for Desktop Space (Light Planet)
        if (this.spaces.desktop.planet && this.spaces.desktop.planet.material.uniforms) {
            this.spaces.desktop.planet.material.uniforms.u_time.value = elapsed;
        }
        
        // Update shader uniforms for Project Space (DNA Helix)
        if (this.spaces.projects.helix) {
            const { strand1, strand2 } = this.spaces.projects.helix;
            if (strand1 && strand1.material.uniforms) {
                strand1.material.uniforms.u_time.value = elapsed;
            }
            if (strand2 && strand2.material.uniforms) {
                strand2.material.uniforms.u_time.value = elapsed;
            }
        }
        
        // Animate Ideas Space bubbles (gentle floating)
        if (this.spaces.ideas.objects) {
            this.spaces.ideas.objects.forEach((obj, index) => {
                if (obj.userData && obj.userData.type === 'bubble') {
                    obj.position.y += Math.sin(elapsed * 0.5 + index) * 0.001;
                    obj.rotation.y += 0.002;
                }
            });
        }
        
        // Animate Project Space particles
        if (this.spaces.projects.particles) {
            this.spaces.projects.particles.rotation.y += 0.001;
        }

        // Animate shuttling projects (pulsing effect for projects with status="shuttling")
        if (this.spaces.projects.objects) {
            this.spaces.projects.objects.forEach(obj => {
                if (obj.userData?.isShuttling && obj.material) {
                    // Pulsing opacity effect
                    obj.material.opacity = 0.4 + Math.sin(elapsed * 3) * 0.2;
                    // Pulsing emissive intensity
                    if (obj.material.emissiveIntensity !== undefined) {
                        obj.material.emissiveIntensity = 0.1 + Math.sin(elapsed * 3) * 0.1;
                    }
                }
            });
        }

        // Animate Desktop Space particles
        if (this.spaces.desktop.objects) {
            this.spaces.desktop.objects.forEach(obj => {
                if (obj.type === 'Points') {
                    obj.rotation.y += 0.0005;
                    obj.rotation.x += 0.0002;
                }
            });
        }

        // Animate SWE Design Factory (gears, smoke, building pulse)
        if (this.spaces.swedesign.gear1) {
            this.spaces.swedesign.gear1.rotation.z += 0.01;
        }
        if (this.spaces.swedesign.gear2) {
            this.spaces.swedesign.gear2.rotation.z -= 0.01;
        }
        if (this.spaces.swedesign.building && this.spaces.swedesign.building.material) {
            this.spaces.swedesign.building.material.emissiveIntensity =
                0.15 + Math.sin(elapsed * 1.5) * 0.1;
        }
        // Smoke particles drift upward and reset
        [this.spaces.swedesign.smoke1, this.spaces.swedesign.smoke2].forEach(smoke => {
            if (smoke && smoke.geometry) {
                const pos = smoke.geometry.attributes.position;
                for (let i = 0; i < pos.count; i++) {
                    let y = pos.getY(i);
                    y += 0.015 + Math.random() * 0.005;
                    if (y > 2.0) y = 0; // reset to base
                    pos.setY(i, y);
                    // gentle horizontal drift
                    pos.setX(i, pos.getX(i) + (Math.random() - 0.5) * 0.003);
                }
                pos.needsUpdate = true;
            }
        });

        // Animate Dashboard Chalkboard (gentle rocking)
        if (this.spaces.clawport.board) {
            this.spaces.clawport.board.rotation.y = Math.sin(elapsed * 0.3) * 0.02;
            this.spaces.clawport.board.rotation.z = Math.sin(elapsed * 0.5 + 1) * 0.008;
        }

        // Animate Agent Farm (windmill blades + wandering animals)
        if (this.spaces.agentfarm.blades) {
            this.spaces.agentfarm.blades.rotation.z += 0.015;
        }
        if (this.spaces.agentfarm.animals) {
            this.spaces.agentfarm.animals.forEach((animal) => {
                const d = animal.userData;
                d.wanderAngle += d.wanderSpeed * 0.01;
                animal.position.x = Math.cos(d.wanderAngle + Math.sin(elapsed * d.wanderSpeed + d.phase) * 0.3) * d.wanderRadius;
                animal.position.z = Math.sin(d.wanderAngle + Math.sin(elapsed * d.wanderSpeed + d.phase) * 0.3) * d.wanderRadius;
                animal.position.y = Math.abs(Math.sin(elapsed * 2 + d.phase)) * 0.05; // tiny hop
            });
        }

        // Animate Video Studio (clapperboard wobble + spotlight pulse)
        if (this.spaces.video.clap) {
            this.spaces.video.clap.rotation.x = -0.15 + Math.sin(elapsed * 3) * 0.08;
        }
        if (this.spaces.video.spotlight) {
            const pulse = 0.6 + Math.sin(elapsed * 2) * 0.3;
            this.spaces.video.spotlight.material.emissiveIntensity = pulse;
        }

        // Animate Brain (pulsing + synapse flicker + thought bubbles float)
        if (this.spaces.thebrain.brain) {
            const pulse = 1 + Math.sin(elapsed * 1.5) * 0.03;
            this.spaces.thebrain.brain.scale.set(pulse, pulse * 0.95, pulse);
        }
        if (this.spaces.thebrain.brainGroup) {
            this.spaces.thebrain.brainGroup.rotation.y = Math.sin(elapsed * 0.2) * 0.05;
        }
        if (this.spaces.thebrain.synapses) {
            this.spaces.thebrain.synapses.forEach((line, i) => {
                line.material.opacity = 0.1 + Math.abs(Math.sin(elapsed * 3 + i * 1.7)) * 0.3;
            });
        }
        if (this.spaces.thebrain.thoughtBubbles) {
            this.spaces.thebrain.thoughtBubbles.forEach((bubble) => {
                const d = bubble.userData;
                bubble.position.y = d.baseY + Math.sin(elapsed * d.floatSpeed + d.floatPhase) * 0.3;
                bubble.material.opacity = 0.2 + Math.sin(elapsed * d.floatSpeed * 0.7 + d.floatPhase) * 0.15;
            });
        }

        // Animate Roarboot Space (gentle bobbing + ripple pulse)
        if (this.spaces.roarboot.boat) {
            this.spaces.roarboot.boat.position.y = 0.1 + Math.sin(elapsed * 0.8) * 0.15;
            this.spaces.roarboot.boat.rotation.z = Math.sin(elapsed * 0.5) * 0.05;
        }
        if (this.spaces.roarboot.sail) {
            this.spaces.roarboot.sail.material.opacity = 0.25 + Math.sin(elapsed * 1.2) * 0.1;
        }
        if (this.spaces.roarboot.ripple) {
            const s = 1 + Math.sin(elapsed * 0.6) * 0.1;
            this.spaces.roarboot.ripple.scale.set(s, s, 1);
            this.spaces.roarboot.ripple.material.opacity = 0.1 + Math.sin(elapsed * 0.6) * 0.05;
        }

        // Update requirement shuttles
        if (this.shuttleManager) {
            this.shuttleManager.update(delta, elapsed);
        }

        // Render the scene
        if (this.renderer && this.scene && this.camera) {
            this.renderer.render(this.scene, this.camera);
        }
    }
    
    // ========================================================================
    // BUBBLE SELECTION & INTERACTION
    // ========================================================================
    
    onContainerClick(event) {
        // Ignore clicks on UI elements (info-panel, buttons, etc.)
        const target = event.target;
        if (target.closest('#info-panel') || target.closest('#enter-btn') ||
            target.closest('.shuttle-info-panel') || target.closest('button')) {
            return; // Let the button handle it
        }

        // Raycasting for bubble/project selection
        const rect = this.container.getBoundingClientRect();
        const mouse = new THREE.Vector2(
            ((event.clientX - rect.left) / rect.width) * 2 - 1,
            -((event.clientY - rect.top) / rect.height) * 2 + 1
        );

        const raycaster = new THREE.Raycaster();
        raycaster.setFromCamera(mouse, this.camera);

        // Check shuttle clicks first (visible across all spaces)
        if (this.shuttleManager && this.shuttleManager.onClick(event, this.camera)) {
            return; // Shuttle click handled
        }

        // Check Factory click (visible from any space) — navigate into SWE Design
        if (this.spaces.swedesign?.group && this.currentSpace !== 'swedesign') {
            const factoryObjects = this.spaces.swedesign.group.children.filter(
                c => c.isMesh
            );
            const factoryHit = raycaster.intersectObjects(factoryObjects);
            if (factoryHit.length > 0) {
                this.navigateToSpace('swedesign');
                return;
            }
        }

        // Check Dashboard chalkboard click — navigate into Dashboard
        if (this.spaces.clawport?.group && this.currentSpace !== 'clawport') {
            const boardObjects = this.spaces.clawport.group.children.flatMap(
                c => c.isGroup ? c.children.filter(m => m.isMesh) : (c.isMesh ? [c] : [])
            );
            const boardHit = raycaster.intersectObjects(boardObjects);
            if (boardHit.length > 0) {
                this.navigateToSpace('clawport');
                return;
            }
        }

        // Check Roarboot boat click (visible from any space) — navigate into Roarboot
        if (this.spaces.roarboot?.group && this.currentSpace !== 'roarboot') {
            const boatObjects = this.spaces.roarboot.group.children.filter(
                c => c.isMesh
            );
            const boatHit = raycaster.intersectObjects(boatObjects);
            if (boatHit.length > 0) {
                this.navigateToSpace('roarboot');
                return;
            }
        }

        // Check Agent Farm click — navigate into Agent Farm
        if (this.spaces.agentfarm?.group && this.currentSpace !== 'agentfarm') {
            const farmObjects = this.spaces.agentfarm.group.children.flatMap(
                c => c.isGroup ? c.children.filter(m => m.isMesh) : (c.isMesh ? [c] : [])
            );
            const farmHit = raycaster.intersectObjects(farmObjects);
            if (farmHit.length > 0) {
                this.navigateToSpace('agentfarm');
                return;
            }
        }

        // Check Video Studio click — navigate to video space
        if (this.spaces.video?.group && this.currentSpace !== 'video') {
            const videoObjects = this.spaces.video.group.children.flatMap(
                c => c.isGroup ? c.children.filter(m => m.isMesh) : (c.isMesh ? [c] : [])
            );
            const videoHit = raycaster.intersectObjects(videoObjects);
            if (videoHit.length > 0) {
                this.navigateToSpace('video');
                return;
            }
        }

        // Check Brain click — navigate into The Brain
        if (this.spaces.thebrain?.group && this.currentSpace !== 'thebrain') {
            const brainObjects = this.spaces.thebrain.group.children.flatMap(
                c => c.isGroup ? c.children.filter(m => m.isMesh) : (c.isMesh ? [c] : [])
            );
            const brainHit = raycaster.intersectObjects(brainObjects);
            if (brainHit.length > 0) {
                this.navigateToSpace('thebrain');
                return;
            }
        }

        // Check based on current space
        if (this.currentSpace === 'ideas') {
            // Check Ideas Space bubbles
            const bubbles = this.spaces.ideas.objects.filter(
                obj => obj.userData && obj.userData.type === 'bubble'
            );
            
            const intersects = raycaster.intersectObjects(bubbles);
            
            if (intersects.length > 0) {
                const bubble = intersects[0].object;
                const index = bubbles.indexOf(bubble);
                this.selectBubble(index);
            } else {
                // Clicked empty space - deselect and hide tooltip
                this.tooltipPinned = false;
                this.selectedBubbleIndex = -1;
                this.selectedBubbleId = null;
                this.hideBubbleTooltip();
            }
        } else if (this.currentSpace === 'projects') {
            // Check Project Space nodes
            const projects = this.spaces.projects.objects.filter(
                obj => obj.userData && obj.userData.type === 'project'
            );

            const intersects = raycaster.intersectObjects(projects);

            if (intersects.length > 0) {
                const project = intersects[0].object;
                const index = projects.indexOf(project);
                this.selectProject(index);
            }
        } else if (this.currentSpace === 'desktop') {
            // Check Desktop Space - click on sun/planet to navigate into desktop dashboard
            const planet = this.spaces.desktop?.planet;
            if (planet) {
                const intersects = raycaster.intersectObjects([planet]);
                if (intersects.length > 0) {
                    this.enterDesktopDashboard();
                }
            }
        }
    }
    
    /**
     * Navigate into the Desktop Dashboard (triggered by clicking the sun).
     * Zooms camera into the sun, then shows fullscreen Vapi + Live Stream dashboard.
     */
    enterDesktopDashboard() {
        if (this.isNavigating || this._insideDesktopDashboard) return;

        // Request Automation_ui backend start (fallback if auto-start didn't work)
        if (window.vibemind?.send) {
            window.vibemind.send({ type: 'start_automation_ui' });
        }

        const planet = this.spaces.desktop?.planet;
        if (!planet) return;

        this.isNavigating = true;
        this._insideDesktopDashboard = true;

        // Get sun world position
        const sunPos = new THREE.Vector3();
        planet.getWorldPosition(sunPos);

        // Save camera state for exit
        this._desktopCamSave = {
            position: this.camera.position.clone(),
            target: this.controls.target.clone()
        };

        // Zoom camera into the sun
        const targetPos = sunPos.clone();
        targetPos.z += 0.5;

        const startPosition = this.camera.position.clone();
        const startLookAt = this.controls.target.clone();
        const duration = 700;
        const startTime = Date.now();

        const zoomIn = () => {
            const elapsed = Date.now() - startTime;
            const progress = Math.min(elapsed / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);

            this.camera.position.lerpVectors(startPosition, targetPos, eased);
            this.controls.target.lerpVectors(startLookAt, sunPos, eased);

            if (progress < 1) {
                requestAnimationFrame(zoomIn);
            } else {
                this.isNavigating = false;
                this._showDesktopDashboard();
            }
        };
        requestAnimationFrame(zoomIn);
    }

    /**
     * Create and show the fullscreen desktop dashboard overlay.
     */
    _showDesktopDashboard() {
        let panel = document.getElementById('vapi-panel');
        if (panel) {
            panel.classList.add('visible');
            requestAnimationFrame(() => panel.classList.add('fade-in'));
            return;
        }

        // Create fullscreen dashboard (no custom header - VibeMind's nav tabs handle navigation)
        panel = document.createElement('div');
        panel.id = 'vapi-panel';
        panel.innerHTML = `
            <div id="vapi-loading">
                <div class="spinner"></div>
                <span>Connecting to Automation backend...</span>
            </div>
            <iframe id="vapi-frame" style="display:none;" allow="microphone; autoplay" allowfullscreen></iframe>
        `;
        document.body.appendChild(panel);

        // Show with fade-in
        requestAnimationFrame(() => {
            panel.classList.add('visible');
            requestAnimationFrame(() => panel.classList.add('fade-in'));
        });

        // Poll backend health, then load iframe
        let attempts = 0;
        const maxAttempts = 20;
        const pollHealth = () => {
            attempts++;
            fetch('http://localhost:8007/api/health/health', { signal: AbortSignal.timeout(2000) })
                .then(r => {
                    if (r.ok) {
                        const loadingEl = document.getElementById('vapi-loading');
                        const frameEl = document.getElementById('vapi-frame');
                        if (loadingEl) loadingEl.style.display = 'none';
                        if (frameEl) {
                            frameEl.src = 'http://localhost:8007/voice/dashboard';
                            frameEl.style.display = 'block';
                        }
                    } else if (attempts < maxAttempts) {
                        setTimeout(pollHealth, 3000);
                    }
                })
                .catch(() => {
                    if (attempts < maxAttempts) {
                        setTimeout(pollHealth, 3000);
                    } else {
                        const loadingEl = document.getElementById('vapi-loading');
                        if (loadingEl) {
                            loadingEl.innerHTML = '<span>Backend not reachable. Check Automation_ui.</span>';
                        }
                    }
                });
        };
        setTimeout(pollHealth, 2000);
    }

    /**
     * Exit the desktop dashboard and zoom back out to Desktop Space view.
     */
    exitDesktopDashboard() {
        if (!this._insideDesktopDashboard) return;

        const panel = document.getElementById('vapi-panel');
        if (panel) {
            panel.classList.remove('fade-in');
            // Wait for fade-out, then hide
            setTimeout(() => {
                panel.classList.remove('visible');
            }, 400);
        }

        // Restore camera position
        if (this._desktopCamSave) {
            this.isNavigating = true;
            const targetPos = this._desktopCamSave.position;
            const targetLookAt = this._desktopCamSave.target;
            const startPosition = this.camera.position.clone();
            const startLookAt = this.controls.target.clone();
            const duration = 600;
            const startTime = Date.now();

            const zoomOut = () => {
                const elapsed = Date.now() - startTime;
                const progress = Math.min(elapsed / duration, 1);
                const eased = 1 - Math.pow(1 - progress, 3);

                this.camera.position.lerpVectors(startPosition, targetPos, eased);
                this.controls.target.lerpVectors(startLookAt, targetLookAt, eased);

                if (progress < 1) {
                    requestAnimationFrame(zoomOut);
                } else {
                    this.isNavigating = false;
                    this._insideDesktopDashboard = false;
                }
            };
            requestAnimationFrame(zoomOut);
        } else {
            this._insideDesktopDashboard = false;
        }
    }

    /**
     * Project a 3D world position to 2D screen coordinates.
     */
    worldToScreen(position) {
        const vec = position.clone();
        vec.project(this.camera);
        const rect = this.container.getBoundingClientRect();
        return {
            x: (vec.x * 0.5 + 0.5) * rect.width + rect.left,
            y: (-vec.y * 0.5 + 0.5) * rect.height + rect.top
        };
    }

    onContainerMouseMove(event) {
        if (this.isInsideBubble) return;

        const rect = this.container.getBoundingClientRect();
        const mouse = new THREE.Vector2(
            ((event.clientX - rect.left) / rect.width) * 2 - 1,
            -((event.clientY - rect.top) / rect.height) * 2 + 1
        );

        const raycaster = new THREE.Raycaster();
        raycaster.setFromCamera(mouse, this.camera);

        if (this.currentSpace === 'ideas') {
            const bubbles = (this.spaces.ideas?.objects || []).filter(
                obj => obj.userData && obj.userData.type === 'bubble'
            );
            const intersects = raycaster.intersectObjects(bubbles);

            if (intersects.length > 0) {
                const bubble = intersects[0].object;
                const index = bubbles.indexOf(bubble);
                if (index !== this.hoveredBubbleIndex) {
                    this.hoveredBubbleIndex = index;
                    this.showBubbleTooltip(bubble);
                } else {
                    // Update tooltip position to follow bubble
                    this.positionTooltipAtBubble(bubble);
                }
            } else if (this.hoveredBubbleIndex >= 0 && !this.tooltipPinned) {
                this.hoveredBubbleIndex = -1;
                this.hideBubbleTooltip();
            }
        }
    }

    showBubbleTooltip(bubble) {
        const infoPanel = document.getElementById('info-panel');
        const titleEl = document.getElementById('selected-title');
        const descEl = document.getElementById('selected-description');
        const enterBtn = document.getElementById('enter-btn');
        const bubbleInfo = document.getElementById('bubble-info');

        // Store the bubble ID for the Enter button to use
        this.tooltipBubbleId = bubble.userData.id || null;

        if (titleEl) titleEl.textContent = bubble.userData.title || 'Bubble';
        // Show bubble content stats
        const data = bubble.userData.data || {};
        const stats = [];
        if (data.description) stats.push(data.description);
        if (data.node_count) stats.push(`${data.node_count} ideas`);
        if (data.numbered_title) stats.push(data.numbered_title);
        if (descEl) descEl.textContent = stats.length ? stats.join(' · ') : '';
        if (enterBtn) enterBtn.classList.remove('hidden');
        if (bubbleInfo) bubbleInfo.classList.remove('hidden');
        if (infoPanel) infoPanel.classList.remove('hidden');

        this.positionTooltipAtBubble(bubble);
    }

    /**
     * Get the bubble ID currently shown in the tooltip
     * @returns {string|null} The bubble ID or null if no tooltip is shown
     */
    getTooltipBubbleId() {
        return this.tooltipBubbleId || null;
    }

    positionTooltipAtBubble(bubble) {
        const infoPanel = document.getElementById('info-panel');
        if (!infoPanel) return;

        const worldPos = new THREE.Vector3();
        bubble.getWorldPosition(worldPos);
        const screen = this.worldToScreen(worldPos);

        // Position above the bubble
        infoPanel.style.position = 'absolute';
        infoPanel.style.left = `${screen.x}px`;
        infoPanel.style.top = `${screen.y - 60}px`;
        infoPanel.style.transform = 'translate(-50%, -100%)';
        infoPanel.style.right = 'auto';
    }

    hideBubbleTooltip() {
        const infoPanel = document.getElementById('info-panel');
        const bubbleInfo = document.getElementById('bubble-info');
        if (bubbleInfo) bubbleInfo.classList.add('hidden');
        if (infoPanel) infoPanel.classList.add('hidden');
        // Clear the tooltip bubble ID
        this.tooltipBubbleId = null;
        // Reset positioning
        if (infoPanel) {
            infoPanel.style.transform = '';
            infoPanel.style.left = '';
            infoPanel.style.right = '';
        }
    }

    selectBubble(index) {
        const bubbles = this.spaces.ideas.objects.filter(
            obj => obj.userData && obj.userData.type === 'bubble'
        );

        if (index < 0 || index >= bubbles.length) {
            return;
        }

        // Deselect previous
        if (this.selectedBubbleIndex >= 0 && this.selectedBubbleIndex < bubbles.length) {
            const prev = bubbles[this.selectedBubbleIndex];
            if (prev.material) {
                prev.material.emissive?.setHex(0x000000);
            }
        }

        // Select new
        this.selectedBubbleIndex = index;
        const bubble = bubbles[index];
        this.selectedBubbleId = bubble.userData.id || bubble.userData.title || index;

        // Visual feedback
        if (bubble.material && bubble.material.emissive) {
            bubble.material.emissive.setHex(0x333333);
        }
        // Show tooltip at bubble position and pin it (click = persistent)
        this.tooltipPinned = true;
        this.showBubbleTooltip(bubble);

        console.log('[Multiverse] Selected bubble:', bubble.userData.title, 'index:', index);
    }
    
    selectNextBubble(direction = 1) {
        const bubbles = (this.spaces.ideas?.objects || []).filter(
            obj => obj.userData && obj.userData.type === 'bubble'
        );
        
        if (bubbles.length === 0) return;
        
        let newIndex = this.selectedBubbleIndex + direction;
        if (newIndex >= bubbles.length) newIndex = 0;
        if (newIndex < 0) newIndex = bubbles.length - 1;
        
        this.selectBubble(newIndex);
    }
    
    selectNearestBubble(handPos) {
        if (!handPos) return;
        
        const bubbles = (this.spaces.ideas?.objects || []).filter(
            obj => obj.userData && obj.userData.type === 'bubble'
        );
        
        if (bubbles.length === 0) return;
        
        // Map hand position to 3D space
        const searchPos = new THREE.Vector3(
            (handPos.x - 0.5) * 6,
            (0.5 - handPos.y) * 4,
            0
        );
        
        let nearestIndex = 0;
        let nearestDist = Infinity;
        
        bubbles.forEach((bubble, index) => {
            const dist = bubble.position.distanceTo(searchPos);
            if (dist < nearestDist) {
                nearestDist = dist;
                nearestIndex = index;
            }
        });
        
        this.selectBubble(nearestIndex);
    }
    
    /**
     * Synchronize bubbles from Python backend - replaces all existing bubbles
     * @param {Array} bubbles - Array of bubble objects from database
     */
    syncBubbles(bubbles) {
        if (!bubbles || !Array.isArray(bubbles)) {
            console.warn('[Multiverse] syncBubbles: Invalid bubble data');
            return;
        }
        
        console.log('[Multiverse] Syncing', bubbles.length, 'bubbles from database');
        
        const ideasGroup = this.spaces.ideas.group;
        if (!ideasGroup) {
            console.warn('[Multiverse] syncBubbles: Ideas group not initialized');
            return;
        }
        
        // Remove all existing bubbles (but keep the marker ring)
        const toRemove = [];
        ideasGroup.children.forEach(child => {
            if (child.userData && child.userData.type === 'bubble') {
                toRemove.push(child);
            }
        });
        toRemove.forEach(obj => {
            ideasGroup.remove(obj);
            if (obj.geometry) obj.geometry.dispose();
            if (obj.material) obj.material.dispose();
        });
        
        // Clear objects array (keep non-bubbles)
        this.spaces.ideas.objects = this.spaces.ideas.objects.filter(
            obj => !obj.userData || obj.userData.type !== 'bubble'
        );
        
        // Color palette for bubbles
        const colors = [0x66aaff, 0xff66aa, 0x66ffaa, 0xffcc66, 0xcc66ff,
                        0xff9966, 0x66ffcc, 0x9966ff, 0xff6666, 0x66ff66];
        
        // Create new bubbles from data
        bubbles.forEach((data, index) => {
            const radius = data.radius || 0.6 + Math.random() * 0.3;
            
            // Use provided color or pick from palette
            let color = data.color;
            if (!color || typeof color !== 'number') {
                color = colors[index % colors.length];
            }
            
            // Calculate position from data or generate spiral
            let pos;
            if (data.position) {
                pos = new THREE.Vector3(data.position.x || 0, data.position.y || 0, data.position.z || 0);
            } else {
                // Generate spiral position
                const angle = index * 0.8;
                const r = 1.5 + (index * 0.3);
                pos = new THREE.Vector3(
                    Math.cos(angle) * r,
                    (index % 3 - 1) * 0.5,
                    Math.sin(angle) * r
                );
            }
            
            const geometry = new THREE.IcosahedronGeometry(radius, 3);
            const material = new THREE.MeshPhysicalMaterial({
                color: color,
                metalness: 0.1,
                roughness: 0.1,
                transmission: 0.9,
                transparent: true,
                opacity: 0.8,
            });
            
            const bubble = new THREE.Mesh(geometry, material);
            bubble.position.copy(pos);
            bubble.userData = {
                type: 'bubble',
                title: data.title || `Bubble ${index + 1}`,
                id: data.id || data.db_id || index,
                db_id: data.db_id || data.id,
                data: data
            };
            
            ideasGroup.add(bubble);
            this.spaces.ideas.objects.push(bubble);
        });
        
        console.log('[Multiverse] Bubbles synced successfully:', bubbles.length);
    }
    
    /**
     * Enter a bubble with a zoom-in animation
     * @param {number} bubbleIndex - Index of the bubble to enter
     * @param {function} onComplete - Callback when animation is complete
     */
    enterBubbleWithAnimation(bubbleIndex, onComplete) {
        if (this.isNavigating || this.isInsideBubble) {
            console.log('[Multiverse] Cannot enter - already navigating or inside bubble');
            if (onComplete) onComplete();
            return;
        }
        
        const bubbles = this.spaces.ideas.objects.filter(
            obj => obj.userData && obj.userData.type === 'bubble'
        );
        
        if (bubbleIndex < 0 || bubbleIndex >= bubbles.length) {
            console.log('[Multiverse] Invalid bubble index:', bubbleIndex);
            if (onComplete) onComplete();
            return;
        }
        
        const bubble = bubbles[bubbleIndex];
        const bubbleWorldPos = new THREE.Vector3();
        bubble.getWorldPosition(bubbleWorldPos);
        
        console.log('[Multiverse] Entering bubble with animation:', bubble.userData.title);
        
        this.isNavigating = true;
        
        // Show transition overlay
        const overlay = document.getElementById('transition-overlay');
        if (overlay) overlay.classList.add('active');
        
        // Calculate target position (very close to bubble center)
        const targetPos = bubbleWorldPos.clone();
        targetPos.z += 0.3; // Just slightly in front
        
        // Animate camera zooming into the bubble
        const startPosition = this.camera.position.clone();
        const startLookAt = this.controls.target.clone();
        const duration = 800; // ms
        const startTime = Date.now();
        
        const updateCamera = () => {
            const elapsed = Date.now() - startTime;
            const progress = Math.min(elapsed / duration, 1);
            
            // Ease out curve for smooth deceleration
            const eased = 1 - Math.pow(1 - progress, 3);
            
            this.camera.position.lerpVectors(startPosition, targetPos, eased);
            this.controls.target.lerpVectors(startLookAt, bubbleWorldPos, eased);
            
            // Scale up bubble (zoom effect)
            const scale = 1 + eased * 2;
            bubble.scale.setScalar(scale);
            
            // Increase brightness as we get closer
            if (bubble.material && bubble.material.opacity !== undefined) {
                bubble.material.opacity = 0.8 + eased * 0.2;
            }
            
            if (progress < 1) {
                requestAnimationFrame(updateCamera);
            } else {
                // Animation complete
                this.isNavigating = false;
                this.isInsideBubble = true;
                
                // Reset bubble scale for when we exit
                bubble.scale.setScalar(1);
                if (bubble.material) bubble.material.opacity = 0.8;
                
                if (onComplete) onComplete();
            }
        };
        
        updateCamera();
    }
    
    /**
     * Exit from inside a bubble with a zoom-out animation
     * @param {function} onComplete - Callback when animation is complete
     */
    exitBubbleWithAnimation(onComplete) {
        if (this.isNavigating || !this.isInsideBubble) {
            console.log('[Multiverse] Cannot exit - already navigating or not inside bubble');
            if (onComplete) onComplete();
            return;
        }
        
        console.log('[Multiverse] Exiting bubble with animation');
        
        this.isNavigating = true;
        
        // Calculate target position (back to normal view)
        const spacePosition = this.spaces[this.currentSpace].position;
        const targetPos = spacePosition.clone();
        targetPos.z += 10;
        targetPos.y += 2;
        
        // Animate camera zooming out
        const startPosition = this.camera.position.clone();
        const startLookAt = this.controls.target.clone();
        const duration = 600; // ms
        const startTime = Date.now();
        
        const updateCamera = () => {
            const elapsed = Date.now() - startTime;
            const progress = Math.min(elapsed / duration, 1);
            
            // Ease in-out curve
            const eased = progress < 0.5
                ? 2 * progress * progress
                : 1 - Math.pow(-2 * progress + 2, 2) / 2;
            
            this.camera.position.lerpVectors(startPosition, targetPos, eased);
            this.controls.target.lerpVectors(startLookAt, spacePosition, eased);
            
            if (progress < 1) {
                requestAnimationFrame(updateCamera);
            } else {
                // Animation complete
                this.isNavigating = false;
                this.isInsideBubble = false;
                
                // Hide transition overlay
                const overlay = document.getElementById('transition-overlay');
                if (overlay) overlay.classList.remove('active');
                
                if (onComplete) onComplete();
            }
        };
        
        updateCamera();
    }
    
    // ========================================================================
    // BUBBLE MANAGEMENT
    // ========================================================================
    
    // Keep selectBubble method for backwards compatibility and for now
    
    /**
     * Add a single bubble to the Ideas Space
     * @param {Object} bubbleData - Bubble data with title, color, position, radius, id
     */
    addBubble(bubbleData) {
        if (!bubbleData) {
            console.warn('[Multiverse] addBubble: Invalid bubble data');
            return;
        }
        
        console.log('[Multiverse] Adding bubble:', bubbleData.title || bubbleData.id);
        
        const ideasGroup = this.spaces.ideas.group;
        if (!ideasGroup) {
            console.warn('[Multiverse] addBubble: Ideas group not initialized');
            return;
        }
        
        const radius = bubbleData.radius || 0.7;
        
        // Handle color in various formats
        let color = 0x66aaff; // default blue
        if (bubbleData.color !== undefined && bubbleData.color !== null) {
            if (typeof bubbleData.color === 'number') {
                color = bubbleData.color;
            } else if (typeof bubbleData.color === 'string') {
                const colorStr = bubbleData.color.replace(/^#0x?/, '');
                color = parseInt(colorStr, 16) || 0x66aaff;
            } else if (typeof bubbleData.color === 'object') {
                // Handle {r, g, b} format (0-1 range)
                const r = Math.floor((bubbleData.color.r || 0) * 255);
                const g = Math.floor((bubbleData.color.g || 0) * 255);
                const b = Math.floor((bubbleData.color.b || 0) * 255);
                color = (r << 16) | (g << 8) | b;
            }
        }
        
        // Calculate position from data or use random
        let pos;
        if (bubbleData.position || bubbleData.pos) {
            const p = bubbleData.position || bubbleData.pos;
            pos = new THREE.Vector3(p.x || 0, p.y || 0, p.z || 0);
        } else {
            // Auto-arrange in space
            const angle = Math.random() * Math.PI * 2;
            const r = 2 + Math.random() * 2;
            pos = new THREE.Vector3(
                Math.cos(angle) * r,
                (Math.random() - 0.5) * 2,
                Math.sin(angle) * r
            );
        }
        
        const geometry = new THREE.IcosahedronGeometry(radius, 3);
        const material = new THREE.MeshPhysicalMaterial({
            color: color,
            metalness: 0.1,
            roughness: 0.1,
            transmission: 0.9,
            transparent: true,
            opacity: 0.8,
        });
        
        const bubble = new THREE.Mesh(geometry, material);
        bubble.position.copy(pos);
        bubble.userData = {
            type: 'bubble',
            title: bubbleData.title || bubbleData.name || 'Bubble',
            id: bubbleData.id || Date.now(),
            db_id: bubbleData.db_id || bubbleData.id,
            data: bubbleData
        };
        
        ideasGroup.add(bubble);
        this.spaces.ideas.objects.push(bubble);
        
        console.log('[Multiverse] Bubble added successfully:', bubble.userData.title);

        return bubble;
    }

    /**
     * Remove a bubble from the Ideas space
     * @param {string|number} id - Bubble ID, db_id, or title
     * @returns {boolean} True if removed successfully
     */
    removeBubble(id) {
        console.log('[Multiverse] removeBubble called with id:', id, 'type:', typeof id);

        const ideasGroup = this.spaces.ideas.group;
        if (!ideasGroup) {
            console.warn('[Multiverse] removeBubble: Ideas group not initialized');
            return false;
        }

        const objects = this.spaces.ideas.objects;
        console.log('[Multiverse] Current bubbles:', objects.map(b => ({
            id: b.userData.id,
            db_id: b.userData.db_id,
            title: b.userData.title
        })));

        // Try multiple matching strategies
        let index = -1;

        // 1. Direct ID match
        index = objects.findIndex(b => b.userData.id === id);

        // 2. db_id match
        if (index === -1) {
            index = objects.findIndex(b => b.userData.db_id === id);
        }

        // 3. String conversion for type mismatch
        if (index === -1) {
            index = objects.findIndex(b => String(b.userData.id) === String(id));
        }

        // 4. db_id string conversion
        if (index === -1) {
            index = objects.findIndex(b => String(b.userData.db_id) === String(id));
        }

        // 5. Partial UUID match (first 8 chars)
        if (index === -1 && typeof id === 'string' && id.length >= 8) {
            index = objects.findIndex(b => {
                const dbId = String(b.userData.db_id || '');
                return dbId.startsWith(id) || id.startsWith(dbId.substring(0, 8));
            });
        }

        // 6. Title match (case-insensitive)
        if (index === -1 && typeof id === 'string') {
            const idLower = id.toLowerCase();
            index = objects.findIndex(b =>
                b.userData.title && b.userData.title.toLowerCase() === idLower
            );
        }

        if (index !== -1) {
            const bubble = objects[index];
            console.log('[Multiverse] Removing bubble:', bubble.userData.title, 'id:', bubble.userData.id);

            // Remove from scene group
            ideasGroup.remove(bubble);

            // Dispose geometry and material
            if (bubble.geometry) bubble.geometry.dispose();
            if (bubble.material) bubble.material.dispose();

            // Remove from objects array
            objects.splice(index, 1);

            // Clear selection if this was the selected bubble
            if (this.selectedBubbleId === bubble.userData.id ||
                this.selectedBubbleId === bubble.userData.db_id) {
                this.selectedBubbleId = null;
                this.selectedBubbleIndex = -1;
            }

            console.log('[Multiverse] Bubble removed successfully');
            return true;
        } else {
            console.warn('[Multiverse] Bubble not found for removal:', id);
            return false;
        }
    }

    /**
     * Update a bubble's properties
     * @param {string|number} id - Bubble ID or db_id
     * @param {Object} updates - Properties to update (title, color, position)
     * @returns {boolean} True if updated successfully
     */
    updateBubble(id, updates) {
        console.log('[Multiverse] updateBubble called with id:', id, 'updates:', updates);

        const objects = this.spaces.ideas.objects;

        // Find the bubble using multiple matching strategies
        let bubble = objects.find(b => b.userData.id === id || b.userData.db_id === id);

        if (!bubble && typeof id === 'string') {
            bubble = objects.find(b =>
                String(b.userData.id) === id ||
                String(b.userData.db_id) === id ||
                (b.userData.title && b.userData.title.toLowerCase() === id.toLowerCase())
            );
        }

        if (bubble) {
            console.log('[Multiverse] Updating bubble:', bubble.userData.title, '->', updates);

            // Update title
            if (updates.title) {
                bubble.userData.title = updates.title;
                if (bubble.userData.data) {
                    bubble.userData.data.title = updates.title;
                }
            }

            // Update position
            if (updates.position) {
                bubble.position.set(
                    updates.position.x || bubble.position.x,
                    updates.position.y || bubble.position.y,
                    updates.position.z || bubble.position.z
                );
            }

            // Update color
            if (updates.color !== undefined) {
                let color = updates.color;
                if (typeof color === 'string') {
                    color = parseInt(color.replace(/^#0x?/, ''), 16);
                }
                if (bubble.material) {
                    bubble.material.color.setHex(color);
                }
            }

            console.log('[Multiverse] Bubble updated successfully');
            return true;
        } else {
            console.warn('[Multiverse] Bubble not found for update:', id);
            return false;
        }
    }

    /**
     * Update agent status display
     * @param {string} agentSlug - The agent slug
     * @param {string} status - Status text
     */
    updateAgentStatus(agentSlug, status) {
        this.currentAgent = agentSlug;
        console.log('[Multiverse] Agent status:', agentSlug, status);
        
        // Find matching space and navigate if needed
        for (const [spaceId, space] of Object.entries(this.spaces)) {
            if (space.agent && space.agent.slug === agentSlug) {
                if (this.currentSpace !== spaceId) {
                    this.navigateToSpace(spaceId);
                }
                break;
            }
        }
    }
    
    // ========================================================================
    // GETTER METHODS (Required by index.html)
    // ========================================================================
    
    /**
     * Get the currently selected bubble ID
     * @returns {string|number|null} The selected bubble ID or null
     */
    getSelectedBubbleId() {
        return this.selectedBubbleId;
    }
    
    /**
     * Get bubble object by ID
     * @param {string|number} bubbleId - The bubble ID to search for
     * @returns {THREE.Mesh|null} The bubble mesh or null
     */
    getBubbleById(bubbleId) {
        const bubbles = (this.spaces.ideas?.objects || []).filter(
            obj => obj.userData && obj.userData.type === 'bubble'
        );
        return bubbles.find(b => b.userData.id === bubbleId || b.userData.db_id === bubbleId) || null;
    }
    
    /**
     * Get bubble index by ID
     * @param {string|number} bubbleId - The bubble ID to search for
     * @returns {number} The index or -1 if not found
     */
    getBubbleIndexById(bubbleId) {
        const bubbles = (this.spaces.ideas?.objects || []).filter(
            obj => obj.userData && obj.userData.type === 'bubble'
        );
        return bubbles.findIndex(b => b.userData.id === bubbleId || b.userData.db_id === bubbleId);
    }
    
    /**
     * Focus camera on a specific bubble
     * @param {string|number} bubbleId - The bubble ID to focus on
     */
    focusBubble(bubbleId) {
        const index = this.getBubbleIndexById(bubbleId);
        if (index >= 0) {
            this.selectBubble(index);
            
            // Animate camera to focus on bubble
            const bubble = this.getBubbleById(bubbleId);
            if (bubble) {
                const bubbleWorldPos = new THREE.Vector3();
                bubble.getWorldPosition(bubbleWorldPos);
                
                const targetPos = bubbleWorldPos.clone();
                targetPos.z += 5;
                targetPos.y += 1;
                
                this.animateCameraTo(targetPos, bubbleWorldPos, () => {
                    console.log('[Multiverse] Focused on bubble:', bubbleId);
                });
            }
        }
    }
    
    /**
     * Enter the currently selected item (bubble or project)
     */
    enterCurrentSelection() {
        if (this.currentSpace === 'ideas' && this.selectedBubbleIndex >= 0) {
            this.enterBubbleWithAnimation(this.selectedBubbleIndex, () => {
                // Notify backend of entering bubble
                if (window.vibemind) {
                    window.vibemind.enterBubble(this.selectedBubbleId);
                }
            });
        } else if (this.currentSpace === 'projects' && this.selectedProjectIndex >= 0) {
            console.log('[Multiverse] Entering project:', this.selectedProjectId);
            // Future: enter project view
            if (window.vibemind) {
                window.vibemind.enterProject(this.selectedProjectId);
            }
        }
    }
    
    /**
     * Get project object by ID
     * @param {string|number} projectId - The project ID to search for
     * @returns {THREE.Mesh|null} The project mesh or null
     */
    getProjectById(projectId) {
        const projects = (this.spaces.projects?.objects || []).filter(
            obj => obj.userData && obj.userData.type === 'project'
        );
        return projects.find(p => p.userData.id === projectId || p.userData.index === projectId) || null;
    }
    
    /**
     * Get information about a space
     * @param {string} spaceId - The space ID ('ideas', 'projects', 'desktop')
     * @returns {Object|null} Space info or null
     */
    getSpaceInfo(spaceId) {
        const space = this.spaces[spaceId];
        if (!space) return null;
        
        return {
            id: spaceId,
            name: space.name,
            icon: space.icon,
            agent: space.agent,
            color: space.color,
            position: space.position.toArray(),
            objectCount: space.objects?.length || 0
        };
    }
    
    /**
     * Select a project by index
     * @param {number} index - The project index
     */
    selectProject(index) {
        const projects = (this.spaces.projects?.objects || []).filter(
            obj => obj.userData && obj.userData.type === 'project'
        );
        
        if (index < 0 || index >= projects.length) {
            return;
        }
        
        // Deselect previous
        if (this.selectedProjectIndex >= 0 && this.selectedProjectIndex < projects.length) {
            const prev = projects[this.selectedProjectIndex];
            if (prev.material && prev.material.emissive) {
                prev.material.emissiveIntensity = 0.3;
            }
        }
        
        // Select new
        this.selectedProjectIndex = index;
        const project = projects[index];
        this.selectedProjectId = project.userData.id || project.userData.title || index;
        
        // Visual feedback
        if (project.material && project.material.emissive) {
            project.material.emissiveIntensity = 0.8;
        }
        
        // Update info panel
        const titleEl = document.getElementById('selected-title');
        const descEl = document.getElementById('selected-description');
        const enterBtn = document.getElementById('enter-btn');
        const infoPanel = document.getElementById('bubble-info');
        
        if (titleEl) titleEl.textContent = project.userData.title || 'Project';
        if (descEl) {
            const status = project.userData.status || 'unknown';
            const progress = project.userData.progress || 0;
            descEl.textContent = `Status: ${status} | Progress: ${progress}%`;
        }
        if (enterBtn) enterBtn.classList.remove('hidden');
        if (infoPanel) infoPanel.classList.remove('hidden');
        
        console.log('[Multiverse] Selected project:', project.userData.title, 'index:', index);
    }
    
    /**
     * Select next project (cycle through)
     * @param {number} direction - 1 for next, -1 for previous
     */
    selectNextProject(direction = 1) {
        const projects = (this.spaces.projects?.objects || []).filter(
            obj => obj.userData && obj.userData.type === 'project'
        );
        
        if (projects.length === 0) return;
        
        let newIndex = this.selectedProjectIndex + direction;
        if (newIndex >= projects.length) newIndex = 0;
        if (newIndex < 0) newIndex = projects.length - 1;
        
        this.selectProject(newIndex);
    }
}

// Export for Electron
window.MultiverseApp = MultiverseApp;
