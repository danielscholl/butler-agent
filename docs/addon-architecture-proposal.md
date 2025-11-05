# Butler Agent: Cluster Add-On Architecture Proposal

## Analysis of HostK8s Add-On System

### Current Architecture

**hostk8s** implements a modular, environment-driven add-on system:

```
Orchestration Flow:
make start → cluster-up.py → [create cluster] → setup-addons() → [individual setup-*.py scripts]
```

**Key Components:**

1. **Environment Configuration** (`.env`):
   ```bash
   METRICS_DISABLED=true      # Opt-out (default: enabled)
   INGRESS_DISABLED=true      # Opt-out (default: enabled)
   METALLB_ENABLED=true       # Opt-in (default: disabled)
   REGISTRY_ENABLED=true      # Opt-in (default: disabled)
   VAULT_ENABLED=true         # Opt-in (default: disabled)
   FLUX_ENABLED=true          # Opt-in (default: disabled)
   ```

2. **Modular Setup Scripts** (`infra/scripts/setup-*.py`):
   - `setup-gateway-api.py` - Always runs (foundational)
   - `setup-metrics.py` - Metrics Server (Helm)
   - `setup-metallb.py` - LoadBalancer support
   - `setup-ingress.py` - NGINX Ingress Controller (Helm)
   - `setup-registry.py` - Local container registry (Docker + UI)
   - `setup-vault.py` - HashiCorp Vault + External Secrets Operator
   - `setup-flux.py` - Flux GitOps controllers

3. **Script Pattern** (each add-on follows this structure):
   ```python
   class AddonSetup:
       def __init__(self):
           # Load configuration from environment

       def check_prerequisites(self):
           # Validate cluster is ready

       def check_if_disabled(self):
           # Check if addon should be skipped

       def check_if_already_installed(self):
           # Idempotent check (skip if exists)

       def install_addon(self):
           # Helm install or kubectl apply

       def wait_for_ready(self):
           # Wait for deployment/pods to be ready

       def verify(self):
           # Test addon functionality
   ```

4. **Installation Order** (dependencies matter):
   ```
   1. Gateway API (CRDs)
   2. Metrics Server (core K8s API extension)
   3. MetalLB (if LoadBalancer needed)
   4. NGINX Ingress (depends on MetalLB or NodePort)
   5. Registry (standalone)
   6. Vault (depends on cluster ready)
   7. Flux (depends on cluster ready)
   ```

### Key Features

- **Idempotent**: Safe to re-run, checks if already installed
- **Configurable**: Environment variables + version overrides
- **Resilient**: Failures don't stop cluster creation (warnings)
- **OS-agnostic**: Python scripts handle cross-platform logic
- **Versioned**: Each add-on has configurable chart/app versions

---

## Proposed Integration for Butler Agent

### Option 1: Simple Parameter Approach (Recommended for MVP)

Add optional parameters to `create_cluster()` tool:

```python
def create_cluster(
    name: str,
    config: str = "default",
    kubernetes_version: str | None = None,
    addons: list[str] | None = None,  # NEW: ["ingress", "registry", "vault"]
) -> dict[str, Any]:
    """Create cluster with optional add-ons.

    Available add-ons:
    - ingress: NGINX Ingress Controller
    - registry: Local container registry
    - metrics: Metrics Server (enabled by default)
    - vault: HashiCorp Vault
    - flux: Flux GitOps
    """
```

**User Experience:**
```
> create a cluster with ingress and registry
[Butler creates cluster, installs NGINX + Registry]

> create a cluster called dev with vault
[Butler creates dev cluster with Vault]
```

**Pros:**
- ✅ Simple, natural language friendly
- ✅ Quick to implement
- ✅ Minimal changes to existing code

**Cons:**
- ❌ Not declarative (can't version-control add-on choices)
- ❌ Limited configuration (versions, settings)

---

### Option 2: Declarative YAML Approach (Recommended for Production)

Extend cluster YAML configs with `addons` section:

```yaml
# data/infra/kind-osdu.yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: {name}

# ... existing cluster config ...

# NEW: Butler add-ons section
addons:
  gateway-api:
    enabled: true
    version: "1.3.0"

  metrics-server:
    enabled: true
    chart_version: "3.13.0"

  ingress-nginx:
    enabled: true
    chart_version: "4.13.2"
    values:
      controller:
        service:
          type: NodePort

  registry:
    enabled: true
    port: 5002
    ui: true

  vault:
    enabled: true
    mode: dev
    chart_version: "0.30.1"

  flux:
    enabled: true
    version: "v2.7.1"
    repo: https://github.com/org/repo
    branch: main
```

**Implementation:**
```python
# New addon manager
class AddonManager:
    def __init__(self, cluster_name: str, kubeconfig_path: Path):
        self.cluster_name = cluster_name
        self.kubeconfig_path = kubeconfig_path

    def install_addons(self, addon_config: dict) -> dict:
        """Install addons from YAML config."""
        results = {}

        # Install in dependency order
        for addon_name in ["gateway-api", "metrics-server", "ingress-nginx", "registry", "vault", "flux"]:
            if addon_config.get(addon_name, {}).get("enabled", False):
                results[addon_name] = self.install_addon(addon_name, addon_config[addon_name])

        return results

    def install_addon(self, name: str, config: dict) -> dict:
        """Install a specific addon."""
        # Import and run setup module dynamically
        addon_module = importlib.import_module(f"agent.cluster.addons.{name.replace('-', '_')}")
        setup_class = addon_module.AddonSetup(self.cluster_name, self.kubeconfig_path, config)
        return setup_class.run()
```

**User Experience:**
```
> create a cluster using osdu config
[Butler reads kind-osdu.yaml, sees addons section, installs: gateway-api, metrics, ingress, registry, vault, flux]

> create a development cluster
[Butler uses kind-dev.yaml with minimal addons: just metrics and ingress]
```

**Pros:**
- ✅ Declarative (version-controlled cluster definitions)
- ✅ Highly configurable (versions, settings)
- ✅ Reusable cluster profiles
- ✅ Matches existing Butler config pattern

**Cons:**
- ❌ More complex to implement
- ❌ Requires YAML understanding from users

---

### Option 3: Hybrid Approach (Best of Both Worlds)

Support both parameters AND YAML config:

```python
def create_cluster(
    name: str,
    config: str = "default",
    kubernetes_version: str | None = None,
    addons: list[str] | None = None,  # Override YAML config
) -> dict[str, Any]:
    """Create cluster with optional add-ons.

    Add-ons can be specified via:
    1. Parameter: addons=["ingress", "registry"]
    2. YAML config: addons section in kind-{config}.yaml

    Parameter overrides YAML config if both provided.
    """
```

**Decision Logic:**
```
1. Read cluster YAML config (kind-{config}.yaml)
2. If YAML has `addons` section → parse it
3. If addons parameter provided → override YAML
4. Install selected addons in dependency order
```

**User Experience:**
```
# Using YAML config
> create a cluster using production
[Reads kind-production.yaml addons section]

# Override with parameter
> create a cluster using production with just ingress
[Uses kind-production.yaml but only installs ingress addon]

# Pure parameter
> create a simple cluster with registry
[Uses kind-simple.yaml, adds registry addon]
```

---

## Recommended Implementation Plan

### Phase 1: Foundation (Week 1)

1. **Create add-on module structure:**
   ```
   src/agent/cluster/addons/
   ├── __init__.py
   ├── base.py              # BaseAddon class
   ├── gateway_api.py       # Gateway API CRDs
   ├── metrics_server.py    # Metrics Server
   ├── ingress_nginx.py     # NGINX Ingress
   ├── registry.py          # Container Registry
   ├── vault.py             # HashiCorp Vault
   └── flux.py              # Flux GitOps
   ```

2. **Create BaseAddon abstract class:**
   ```python
   class BaseAddon(ABC):
       def __init__(self, cluster_name: str, kubeconfig_path: Path, config: dict):
           self.cluster_name = cluster_name
           self.kubeconfig_path = kubeconfig_path
           self.config = config

       @abstractmethod
       def check_prerequisites(self) -> bool:
           pass

       @abstractmethod
       def is_installed(self) -> bool:
           pass

       @abstractmethod
       def install(self) -> dict:
           pass

       @abstractmethod
       def wait_for_ready(self, timeout: int = 120) -> bool:
           pass

       def run(self) -> dict:
           """Standard installation flow."""
           if not self.check_prerequisites():
               return {"success": False, "error": "Prerequisites not met"}

           if self.is_installed():
               return {"success": True, "message": "Already installed", "skipped": True}

           result = self.install()
           if result.get("success"):
               self.wait_for_ready()

           return result
   ```

### Phase 2: Core Add-ons (Week 2)

Implement priority add-ons following hostk8s patterns:

1. **Gateway API** (always enabled, foundational)
2. **Metrics Server** (default enabled)
3. **NGINX Ingress** (most common use case)

### Phase 3: Advanced Add-ons (Week 3)

4. **Registry** (container development workflow)
5. **Vault** (secrets management)
6. **Flux** (GitOps)

### Phase 4: Integration & Testing (Week 4)

1. Update `create_cluster()` to support add-ons
2. Update system prompt with add-on capabilities
3. Add tests for each add-on
4. Documentation

---

## System Prompt Updates

Add to `<butler-agent>` XML:

```xml
<capabilities>
  <!-- existing capabilities -->

  <category name="cluster-addons">
    <addon name="gateway-api" status="foundational" default="true">
      <description>Gateway API CRDs for advanced traffic management</description>
    </addon>
    <addon name="metrics-server" status="core" default="true">
      <description>Resource metrics API for kubectl top and HPA</description>
    </addon>
    <addon name="ingress" status="common" default="false">
      <description>NGINX Ingress Controller for HTTP/HTTPS routing</description>
    </addon>
    <addon name="registry" status="optional" default="false">
      <description>Local container registry for development</description>
    </addon>
    <addon name="vault" status="optional" default="false">
      <description>HashiCorp Vault for secrets management</description>
    </addon>
    <addon name="flux" status="optional" default="false">
      <description>Flux GitOps for continuous delivery</description>
    </addon>
  </category>
</capabilities>

<addon-guidelines>
  <installation-order importance="critical">
    Gateway API → Metrics → Ingress → Registry → Vault → Flux
  </installation-order>

  <defaults>
    <default addon="gateway-api" enabled="true" note="Always installed (foundational)"/>
    <default addon="metrics-server" enabled="true" note="Core K8s functionality"/>
    <default addon="ingress" enabled="false" note="Specify explicitly"/>
    <default addon="registry" enabled="false" note="Specify explicitly"/>
    <default addon="vault" enabled="false" note="Specify explicitly"/>
    <default addon="flux" enabled="false" note="Specify explicitly"/>
  </defaults>

  <usage-examples>
    <example input="create a cluster with ingress" addons="[gateway-api, metrics, ingress]"/>
    <example input="create dev with registry and ingress" addons="[gateway-api, metrics, registry, ingress]"/>
    <example input="create a production cluster with vault" addons="[gateway-api, metrics, vault]"/>
  </usage-examples>
</addon-guidelines>
```

---

## Summary

**Recommendation: Start with Option 1 (Parameter Approach), evolve to Option 3 (Hybrid)**

**Immediate Actions:**
1. Port hostk8s add-on scripts to Butler's `src/agent/cluster/addons/`
2. Add `addons` parameter to `create_cluster()` tool
3. Update system prompt with add-on capabilities
4. Test with: `create a cluster with ingress and registry`

**Future Enhancements:**
1. Support YAML-based add-on configuration
2. Add `install_addon()` and `remove_addon()` tools for post-creation management
3. Add `list_available_addons()` tool
4. Version management and upgrades

This approach leverages your proven hostk8s patterns while making them accessible through Butler's natural language interface.
