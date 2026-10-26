"""
Inference Module
Stage-aware model inference scheduling for RTX 4070 and similar hardware
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from pathlib import Path
import os
import signal
import subprocess
import threading
import time
import json
from enum import Enum
from contextlib import contextmanager

class ModelProvider(Enum):
    OLLAMA = "ollama"
    VLLM = "vllm"
    HUGGINGFACE = "huggingface"
    CPU = "cpu"
    #: An external HTTP service that answers typed decisions. "Loading" means a
    #: health check; the scheduler never spawns a process for it.
    STARTLUX = "startlux"
    #: A GGUF served by an external llama-server. Eidos does not spawn it: the process and its
    #: VRAM belong to the host, and the mutex contract is what keeps it from overlapping StartLux.
    LLAMA_CPP = "llama_cpp"

class ModelSize(Enum):
    SMALL = "small"      # < 4B params
    MEDIUM = "medium"    # 4B - 14B params
    LARGE = "large"      # 14B - 70B params
    XL = "xl"            # > 70B params

def sciencersi_path() -> str:
    """Where the GGUF lives, without hard-coding a drive letter.

    Order: `$SCIENCERSI_GGUF`, then the Hermes managed model directory. A missing file stays a
    missing file — the plan forbids falling back to another quantization.
    """
    override = os.environ.get("SCIENCERSI_GGUF")
    if override:
        return override
    home = os.environ.get("HERMES_HOME") or os.path.join(
        os.environ.get("LOCALAPPDATA", ""), "hermes")
    return os.path.join(home, "models", "ScienceRSI-8b.i1-Q4_K_M.gguf")


@dataclass
class ModelSpec:
    """Model specification for inference scheduling"""
    name: str
    provider: ModelProvider
    size: ModelSize
    path: str
    vram_gb: float
    context_window: int
    supports_streaming: bool = True
    supports_batching: bool = False
    quantization: str = "q4_k_m"  # q4_k_m, q8_0, awq, fp16, etc.
    tags: List[str] = field(default_factory=list)
    #: Models that may never be resident at the same time (VRAM contract, plan §5). The
    #: declaration must be symmetric; `validate_registry` refuses a one-sided claim.
    mutex_with: tuple = ()

@dataclass
class InferenceRequest:
    """Inference request with priority and resource requirements"""
    request_id: str
    model_name: str
    prompt: str
    max_tokens: int = 512
    temperature: float = 0.7
    priority: int = 0  # Higher = more urgent
    stream: bool = False
    timeout: float = 300.0
    metadata: Dict = field(default_factory=dict)

@dataclass
class InferenceResult:
    """Result of an inference request"""
    request_id: str
    success: bool
    content: str = ""
    reasoning: str = ""
    tokens_generated: int = 0
    latency_ms: float = 0.0
    error: str = ""
    model_used: str = ""

class ModelManager:
    """
    Manages model loading/unloading with VRAM awareness.
    Ensures only one large model is loaded at a time on RTX 4070.
    """
    
    # VRAM budget for RTX 4070 (12GB) with safety margin
    VRAM_BUDGET_GB = 10.5  # Leave 1.5GB for system/OS
    
    # Model registry with VRAM estimates
    MODEL_REGISTRY = {
        # Ollama models
        "llama3.1:8b": ModelSpec("llama3.1:8b", ModelProvider.OLLAMA, ModelSize.MEDIUM, 
                                 "llama3.1:8b", 5.0, 8192, tags=["chat", "general"]),
        "llama3.1:70b": ModelSpec("llama3.1:70b", ModelProvider.OLLAMA, ModelSize.LARGE,
                                  "llama3.1:70b", 40.0, 8192, tags=["chat", "reasoning"]),
        "qwen2.5:14b": ModelSpec("qwen2.5:14b", ModelProvider.OLLAMA, ModelSize.MEDIUM,
                                 "qwen2.5:14b", 9.0, 32768, tags=["chat", "code"]),
        "qwen2.5:32b": ModelSpec("qwen2.5:32b", ModelProvider.OLLAMA, ModelSize.LARGE,
                                 "qwen2.5:32b", 20.0, 32768, tags=["chat", "reasoning"]),
        "gemma2:9b": ModelSpec("gemma2:9b", ModelProvider.OLLAMA, ModelSize.MEDIUM,
                               "gemma2:9b", 5.5, 8192, tags=["chat", "general"]),
        "gemma2:27b": ModelSpec("gemma2:27b", ModelProvider.OLLAMA, ModelSize.LARGE,
                                "gemma2:27b", 16.0, 8192, tags=["chat", "reasoning"]),
        "mistral:7b": ModelSpec("mistral:7b", ModelProvider.OLLAMA, ModelSize.MEDIUM,
                                "mistral:7b", 4.5, 8192, tags=["chat", "general"]),
        
        # Local GGUF models (llama.cpp)
        # Decision operator (external service; "loading" is a health check).
        # vram_gb is an ESTIMATE: ~4.3 GB Q8_0 weights + KV cache, not a measured
        # resident set. One entry only: a duplicate key in this dict would silently
        # override the provider and send the scheduler down the wrong load path.
        "StartLux-Decision-4B-Q8_0": ModelSpec(
            "StartLux-Decision-4B-Q8_0", ModelProvider.STARTLUX, ModelSize.MEDIUM,
            os.environ.get("DECISION_SERVICE_URL", "http://127.0.0.1:8090"),
            6.0, 32768, supports_streaming=False, quantization="q8_0",
            tags=["decision", "choice", "yes-no", "score"],
            mutex_with=("ScienceRSI-8b-i1-Q4_K_M",)),
        "ScienceRSI-8b-i1-Q4_K_M": ModelSpec(
            "ScienceRSI-8b-i1-Q4_K_M", ModelProvider.LLAMA_CPP, ModelSize.MEDIUM,
            # 6.9 GB was the plan's estimate; measured 8.56 GB at 28672 (5.03 weights + 3.53 KV).
            # The number here is the measurement, so the budget check refuses what would not fit.
            sciencersi_path(), 8.6, 28672, supports_streaming=True, quantization="q4_k_m",
            tags=["science", "json", "s4", "s7", "hypothesis"],
            mutex_with=("StartLux-Decision-4B-Q8_0",)),
        "Qwen3.6-35B-A3B-UD-Q4_K_M": ModelSpec(
            "Qwen3.6-35B-A3B-UD-Q4_K_M", ModelProvider.CPU, ModelSize.MEDIUM,
            "Qwen3.6-35B-A3B-UD-Q4_K_M.gguf", 9.5, 262144,
            tags=["chat", "reasoning", "moe"]),
        "Qwen3.8-27B-UD-Q4_K_M": ModelSpec(
            "Qwen3.8-27B-UD-Q4_K_M", ModelProvider.CPU, ModelSize.MEDIUM,
            "Qwen3.8-27B-UD-Q4_K_M.gguf", 8.0, 262144,
            tags=["chat", "reasoning", "moe"]),
        "d1-3b-native": ModelSpec(
            "d1-3b-native", ModelProvider.HUGGINGFACE, ModelSize.SMALL,
            "d1-3b-native", 3.0, 32768,
            tags=["decision", "native"]),
    }
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.vram_budget = self.config.get("vram_budget_gb", self.VRAM_BUDGET_GB)
        self.models_dir = Path(self.config.get("models_dir", "./models"))
        self.ollama_host = self.config.get("ollama_host", "http://localhost:11434")
        self.llama_cpp_path = self.config.get("llama_cpp_path", "llama-server")
        
        # State tracking
        self.loaded_models: Dict[str, Dict] = {}  # name -> {process, vram_gb, last_used}
        self.vram_used_gb = 0.0
        self._lock = threading.RLock()
        
        # Ollama client
        self.ollama_available = self._check_ollama()
        
        # llama.cpp server process
        self.llama_cpp_process = None
        self.llama_cpp_port = 18434
    
    def _check_ollama(self) -> bool:
        """Check if Ollama is available"""
        try:
            result = subprocess.run(
                ["ollama", "list"], capture_output=True, text=True, timeout=10
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def get_model_spec(self, model_name: str) -> Optional[ModelSpec]:
        """Get model specification"""
        return self.MODEL_REGISTRY.get(model_name)
    
    def estimate_vram(self, model_name: str) -> float:
        """Estimate VRAM usage for a model"""
        spec = self.get_model_spec(model_name)
        if spec:
            return spec.vram_gb
        # Fallback estimation based on name
        if "70b" in model_name.lower() or "70B" in model_name:
            return 40.0
        elif "35b" in model_name.lower() or "32b" in model_name.lower() or "27b" in model_name.lower():
            return 20.0
        elif "14b" in model_name.lower() or "9b" in model_name.lower() or "8b" in model_name.lower():
            return 9.0
        elif "7b" in model_name.lower() or "4b" in model_name.lower() or "3b" in model_name.lower():
            return 5.0
        return 5.0  # Default
    
    def mutex_partners_loaded(self, model_name: str) -> List[str]:
        """Which declared mutex partners are currently resident."""
        spec = self.get_model_spec(model_name)
        if not spec:
            return []
        return [name for name in getattr(spec, "mutex_with", ()) if name in self.loaded_models]

    @classmethod
    def validate_registry(cls) -> None:
        """Refuse an asymmetric mutex: A says it excludes B, but B does not say it excludes A."""
        problems = []
        for name, spec in cls.MODEL_REGISTRY.items():
            for partner in getattr(spec, "mutex_with", ()):
                other = cls.MODEL_REGISTRY.get(partner)
                if other is None:
                    problems.append(f"{name} declares a mutex with unknown model {partner!r}")
                elif name not in getattr(other, "mutex_with", ()):
                    problems.append(f"{name} excludes {partner}, but {partner} does not exclude {name}")
        if problems:
            raise ValueError("; ".join(problems))

    def can_load(self, model_name: str) -> bool:
        """Check if model can be loaded within the CONFIGURED VRAM budget.

        Comparing against the class constant ignored `vram_budget_gb`, so a manager
        built for an 8 GB card still admitted a 12 GB plan.
        """
        with self._lock:
            if self.mutex_partners_loaded(model_name):
                # Footprints could both fit and still violate the contract (plan §5).
                return False
            needed = self.estimate_vram(model_name)
            return (self.vram_used_gb + needed) <= self.vram_budget
    
    def load_model(self, model_name: str, force: bool = False) -> bool:
        """Load a model (start Ollama or llama.cpp server)"""
        with self._lock:
            spec = self.get_model_spec(model_name)
            if not spec:
                print(f"Unknown model: {model_name}")
                return False
            
            # Check if already loaded
            if model_name in self.loaded_models:
                self.loaded_models[model_name]["last_used"] = time.time()
                return True
            
            # Check VRAM budget
            if not force and not self.can_load(model_name):
                # Try to unload least recently used models
                self._make_room(spec.vram_gb)
                if not self.can_load(model_name):
                    print(f"Cannot load {model_name}: insufficient VRAM")
                    return False
            
            # Load based on provider
            success = False
            if spec.provider == ModelProvider.OLLAMA:
                success = self._load_ollama(model_name)
            elif spec.provider == ModelProvider.CPU:
                success = self._load_llama_cpp(model_name)
            elif spec.provider == ModelProvider.HUGGINGFACE:
                success = self._load_huggingface(model_name)
            elif spec.provider == ModelProvider.STARTLUX:
                success = self._load_startlux(model_name)
            
            if success:
                self.loaded_models[model_name] = {
                    "spec": spec,
                    "loaded_at": time.time(),
                    "last_used": time.time(),
                    "vram_gb": spec.vram_gb
                }
                self.vram_used_gb += spec.vram_gb
                print(f"Loaded {model_name} ({spec.vram_gb} GB VRAM)")
            
            return success
    
    def _load_startlux(self, model_name: str) -> bool:
        """The decision operator is external: 'loading' is a health check.

        No process is spawned and no VRAM is reserved here -- the service owns its
        own residency. False is honest: the stage cannot run, and the caller must
        escalate or skip rather than substitute a different model.
        """
        spec = self.get_model_spec(model_name)
        if spec is None:
            return False
        import urllib.request
        try:
            with urllib.request.urlopen(spec.path.rstrip("/") + "/health", timeout=5) as resp:
                return resp.status < 400
        except Exception:  # noqa: BLE001 - unreachable service is False, not a crash
            return False

    def _load_ollama(self, model_name: str) -> bool:
        """Load model in Ollama"""
        try:
            # Pull if not present
            result = subprocess.run(
                ["ollama", "pull", model_name], 
                capture_output=True, text=True, timeout=300
            )
            if result.returncode != 0:
                print(f"Failed to pull {model_name}: {result.stderr}")
                return False
            
            # Warm up with a quick request
            import urllib.request
            import json
            req = urllib.request.Request(
                f"{self.ollama_host}/api/generate",
                data=json.dumps({"model": model_name, "prompt": "test", "stream": False}).encode(),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                pass
            return True
        except Exception as e:
            print(f"Failed to load {model_name} in Ollama: {e}")
            return False
    
    def _load_llama_cpp(self, model_name: str) -> bool:
        """Load model via llama.cpp server"""
        spec = self.get_model_spec(model_name)
        if not spec or not spec.path:
            return False
        
        model_path = self.models_dir / spec.path
        if not model_path.exists():
            print(f"Model file not found: {model_path}")
            return False
        
        # Stop existing llama.cpp server
        self._stop_llama_cpp()
        
        # Start new server
        cmd = [
            self.llama_cpp_path,
            "-m", str(model_path),
            "--host", "127.0.0.1",
            "--port", str(self.llama_cpp_port),
            "--ctx-size", "32768",
            "--batch-size", "2048",
            "--ubatch-size", "512",
            "--flash-attn",
            "--no-mmap",
            "--mlock"
        ]
        
        try:
            self.llama_cpp_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True
            )
            
            # Wait for server to be ready
            for _ in range(30):
                time.sleep(1)
                try:
                    import urllib.request
                    with urllib.request.urlopen(f"http://127.0.0.1:{self.llama_cpp_port}/health", timeout=2):
                        return True
                except Exception:
                    pass
            
            print(f"llama.cpp server failed to start for {model_name}")
            return False
        except Exception as e:
            print(f"Failed to start llama.cpp for {model_name}: {e}")
            return False
    
    def _stop_llama_cpp(self):
        """Stop llama.cpp server"""
        if self.llama_cpp_process:
            try:
                if hasattr(self.llama_cpp_process, 'terminate'):
                    self.llama_cpp_process.terminate()
                else:
                    # Unix-only fallback; guarded because os.killpg does not exist on Windows.
                    killpg = getattr(os, "killpg", None)
                    getpgid = getattr(os, "getpgid", None)
                    if killpg and getpgid:
                        killpg(getpgid(self.llama_cpp_process.pid), signal.SIGTERM)
                self.llama_cpp_process.wait(timeout=10)
            except Exception:
                try:
                    self.llama_cpp_process.kill()
                except Exception:
                    pass
            self.llama_cpp_process = None
    
    def _load_huggingface(self, model_name: str) -> bool:
        """Load HuggingFace model (placeholder)"""
        # This would use transformers/accelerate for native HF models
        # For now, delegate to local inference
        print(f"HuggingFace loading not fully implemented for {model_name}")
        return False
    
    def unload_model(self, model_name: str) -> bool:
        """Unload a specific model"""
        with self._lock:
            if model_name not in self.loaded_models:
                return True
            
            spec = self.get_model_spec(model_name)
            if spec and spec.provider == ModelProvider.CPU:
                self._stop_llama_cpp()
            
            if model_name in self.loaded_models:
                self.vram_used_gb -= self.loaded_models[model_name]["vram_gb"]
                del self.loaded_models[model_name]
            
            return True
    
    def unload_all(self) -> None:
        """Unload all models"""
        with self._lock:
            self._stop_llama_cpp()
            for model_name in list(self.loaded_models.keys()):
                if self.get_model_spec(model_name).provider == ModelProvider.OLLAMA:
                    try:
                        subprocess.run(["ollama", "stop", model_name], timeout=30)
                    except Exception:
                        pass
            self.loaded_models.clear()
            self.vram_used_gb = 0.0
    
    def _make_room(self, needed_gb: float) -> None:
        """Unload least recently used models to make room"""
        if not self.loaded_models:
            return
        
        # Sort by last_used (oldest first)
        sorted_models = sorted(
            self.loaded_models.items(),
            key=lambda x: x[1]["last_used"]
        )
        
        freed = 0.0
        for name, info in sorted_models:
            if freed >= needed_gb:
                break
            self.unload_model(name)
            freed += info["vram_gb"]
    
    @contextmanager
    def inference_session(self, model_name: str):
        """Context manager for inference with automatic model loading"""
        loaded = self.load_model(model_name)
        if not loaded:
            raise RuntimeError(f"Failed to load model: {model_name}")
        
        try:
            yield self
        finally:
            # Update last_used timestamp
            with self._lock:
                if model_name in self.loaded_models:
                    self.loaded_models[model_name]["last_used"] = time.time()
    
    def infer(self, request: InferenceRequest) -> InferenceResult:
        """Run inference on a model"""
        start_time = time.time()
        
        with self.inference_session(request.model_name):
            spec = self.get_model_spec(request.model_name)
            if not spec:
                return InferenceResult(
                    request_id=request.request_id,
                    success=False,
                    error=f"Unknown model: {request.model_name}"
                )
            
            try:
                if spec.provider == ModelProvider.OLLAMA:
                    result = self._infer_ollama(request)
                elif spec.provider == ModelProvider.CPU:
                    result = self._infer_llama_cpp(request)
                else:
                    return InferenceResult(
                        request_id=request.request_id,
                        success=False,
                        error=f"Provider {spec.provider} not implemented"
                    )
                
                result.latency_ms = (time.time() - start_time) * 1000
                result.model_used = request.model_name
                return result
                
            except Exception as e:
                return InferenceResult(
                    request_id=request.request_id,
                    success=False,
                    error=str(e),
                    latency_ms=(time.time() - start_time) * 1000
                )
    
    def _infer_ollama(self, request: InferenceRequest) -> InferenceResult:
        """Run inference via Ollama"""
        import urllib.request
        import json
        
        payload = {
            "model": request.model_name,
            "prompt": request.prompt,
            "stream": request.stream,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens
            }
        }
        
        req = urllib.request.Request(
            f"{self.ollama_host}/api/generate",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}
        )
        
        with urllib.request.urlopen(req, timeout=request.timeout) as response:
            data = json.loads(response.read().decode())
        
        content = data.get("response", "")
        reasoning = data.get("reasoning_content", "")
        
        return InferenceResult(
            request_id=request.request_id,
            success=True,
            content=content,
            reasoning=reasoning,
            tokens_generated=data.get("eval_count", 0)
        )
    
    def _infer_llama_cpp(self, request: InferenceRequest) -> InferenceResult:
        """Run inference via llama.cpp server"""
        import urllib.request
        import json
        
        payload = {
            "model": request.model_name,
            "messages": [{"role": "user", "content": request.prompt}],
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "stream": request.stream
        }
        
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.llama_cpp_port}/v1/chat/completions",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}
        )
        
        with urllib.request.urlopen(req, timeout=request.timeout) as response:
            data = json.loads(response.read().decode())
        
        choice = data["choices"][0]
        message = choice.get("message", {})
        content = message.get("content", "")
        reasoning = message.get("reasoning_content", "")
        
        return InferenceResult(
            request_id=request.request_id,
            success=True,
            content=content,
            reasoning=reasoning,
            tokens_generated=data.get("usage", {}).get("completion_tokens", 0)
        )

class InferenceScheduler:
    """
    Priority-based inference scheduler with model affinity.
    """
    
    def __init__(self, model_manager: ModelManager):
        self.model_manager = model_manager
        self.request_queue: List[InferenceRequest] = []
        self.processing = False
        self._lock = threading.Lock()
    
    def submit(self, request: InferenceRequest) -> str:
        """Submit inference request"""
        with self._lock:
            self.request_queue.append(request)
            self.request_queue.sort(key=lambda r: -r.priority)
        return request.request_id
    
    def process_queue(self) -> List[InferenceResult]:
        """Process queued requests"""
        results = []
        
        while True:
            with self._lock:
                if not self.request_queue:
                    break
                request = self.request_queue.pop(0)
            
            result = self.model_manager.infer(request)
            yield result
    
    def process_batch(self, requests: List[InferenceRequest]) -> List[InferenceResult]:
        """Process a batch of requests"""
        results = []
        for req in requests:
            result = self.model_manager.infer(req)
            results.append(result)
        return results


class StageAwareScheduler:
    """
    Stage-aware inference scheduler for research pipeline stages.
    Manages model loading/unloading between pipeline stages.
    """
    
    STAGE_MODELS = {
        "hypothesis_generation": ["llama3.1:8b", "qwen2.5:14b"],
        "literature_review": ["llama3.1:8b", "qwen2.5:14b"],
        "experiment_design": ["qwen2.5:14b", "gemma2:9b"],
        "experiment_execution": ["StartLux-Decision-4B-Q8_0"],
        "evaluation": ["llama3.1:8b", "qwen2.5:14b"],
        "manuscript_drafting": ["llama3.1:8b", "qwen2.5:14b"],
        # Decision stages: typed, calibrated answers, one forward pass each.
        "routing": ["StartLux-Decision-4B-Q8_0"],
        "hypothesis_screening": ["StartLux-Decision-4B-Q8_0"],
        "gate_triage": ["StartLux-Decision-4B-Q8_0"],
        "failure_classification": ["StartLux-Decision-4B-Q8_0"],
        "evaluation_gates": ["StartLux-Decision-4B-Q8_0"],
    }
    
    def __init__(self, model_manager: ModelManager):
        self.model_manager = model_manager
    
    def prepare_stage(self, stage: str) -> bool:
        """Pre-load models for a pipeline stage"""
        models = self.STAGE_MODELS.get(stage, [])
        if not models:
            return True
        
        print(f"Preparing stage '{stage}' with models: {models}")
        
        # Load all required models
        for model in models:
            if not self.model_manager.load_model(model):
                print(f"Warning: Failed to load {model} for stage {stage}")
                return False
        
        return True
    
    def cleanup_stage(self, stage: str, keep_for_next: List[str] = None) -> None:
        """Clean up models after stage, keeping ones needed for next stage"""
        keep = set(keep_for_next or [])
        current_models = set(self.model_manager.loaded_models.keys())
        stage_models = set(self.STAGE_MODELS.get(stage, []))
        
        to_unload = current_models & stage_models - keep
        for model in to_unload:
            self.model_manager.unload_model(model)
    
    def get_stage_models(self, stage: str) -> List[str]:
        """Get models required for a stage"""
        return self.STAGE_MODELS.get(stage, [])


# Convenience functions
def create_model_manager(config: Dict = None) -> ModelManager:
    """Create model manager with default config"""
    return ModelManager(config)

def create_scheduler(config: Dict = None) -> InferenceScheduler:
    """Create inference scheduler"""
    manager = create_model_manager(config)
    return InferenceScheduler(manager)

def create_stage_scheduler(config: Dict = None) -> StageAwareScheduler:
    """Create stage-aware scheduler"""
    manager = create_model_manager(config)
    return StageAwareScheduler(manager)