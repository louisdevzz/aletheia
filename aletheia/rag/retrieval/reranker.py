"""
Reranker Module (Cross-Encoder)
Implements a re-ranking step to filter hybrid search results using a Cross-Encoder model.
Optimized for GPU acceleration and ONNX runtime.
"""

from typing import List, Dict, Tuple, Optional
import torch
import numpy as np


class Reranker:
    """
    Reranks a list of candidate documents based on their semantic relevance to the query.
    Uses a Cross-Encoder model which inputs (query, document) pairs and outputs a similarity score.
    Auto-detects GPU availability and uses optimal inference backend.
    """

    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        device: Optional[str] = None,
        use_onnx: bool = False,
        max_seq_length: int = 512,
    ):
        """
        Initialize the Reranker with a Cross-Encoder model.

        Args:
            model_name: HuggingFace model path. Defaults to a lightweight MS MARCO model.
            device: Device to use ('cuda', 'cpu', or None for auto-detect)
            use_onnx: Whether to use ONNX runtime for faster inference
            max_seq_length: Maximum sequence length for model
        """
        self.model_name = model_name
        self.max_seq_length = max_seq_length

        # Auto-detect device if not specified
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device

        print(f"⏳ Loading Reranker model: {model_name}...")
        print(f"   Device: {device.upper()}")

        try:
            if use_onnx:
                self.model = self._load_onnx_model(model_name)
            else:
                self.model = self._load_hf_model(model_name, device)

            print(f"✓ Reranker model loaded successfully ({device.upper()} mode).")

        except Exception as e:
            print(f"❌ Failed to load Reranker model: {e}")
            print("   Falling back to CPU mode...")
            try:
                from sentence_transformers import CrossEncoder

                self.model = CrossEncoder(model_name, device="cpu")
                print(f"✓ Reranker model loaded successfully (CPU fallback).")
            except Exception as e2:
                print(f"❌ Complete failure: {e2}")
                self.model = None

    def _load_hf_model(self, model_name: str, device: str):
        """Load HuggingFace CrossEncoder model."""
        from sentence_transformers import CrossEncoder

        model = CrossEncoder(model_name, device=device, max_length=self.max_seq_length)

        # Optimize for inference
        if device == "cuda":
            model.model.eval()
            # Enable mixed precision for faster inference
            self.use_amp = True
        else:
            self.use_amp = False

        return model

    def _load_onnx_model(self, model_name: str):
        """Load ONNX optimized model for faster inference."""
        try:
            import onnxruntime as ort

            # Check for available providers
            providers = ort.get_available_providers()

            # Prioritize GPU providers
            if "CUDAExecutionProvider" in providers:
                session_options = ort.SessionOptions()
                session_options.graph_optimization_level = (
                    ort.GraphOptimizationLevel.ORT_ENABLE_ALL
                )
                provider = "CUDAExecutionProvider"
            elif "ROCMExecutionProvider" in providers:
                provider = "ROCMExecutionProvider"
            else:
                provider = "CPUExecutionProvider"

            print(f"   Using ONNX Runtime with {provider}")

            # Note: This is a placeholder - actual ONNX model conversion needed
            # For now, fall back to HF model
            raise NotImplementedError("ONNX model conversion required")

        except ImportError:
            print("   ONNX Runtime not available, using HuggingFace")
            raise

    def rerank(
        self, query: str, candidates: List[Dict], top_k: int = 5, batch_size: int = 32
    ) -> List[Dict]:
        """
        Rerank a list of candidate documents.

        Args:
            query: The user query.
            candidates: List of candidate result dictionaries. Must contain 'text'.
            top_k: Number of top results to return.
            batch_size: Batch size for inference (GPU optimization).

        Returns:
            List of the top-k results, sorted by the new relevance score.
            Updates the 'score' field of the results.
        """
        if not self.model or not candidates:
            return candidates[:top_k]

        # Prepare pairs
        pairs = [[query, doc["text"]] for doc in candidates]

        # Batch inference for GPU efficiency
        if self.device == "cuda" and len(pairs) > batch_size:
            scores = self._batch_predict(pairs, batch_size)
        else:
            scores = self.model.predict(pairs)

        # Attach new scores to candidates
        for i, doc in enumerate(candidates):
            doc["score"] = float(scores[i])

        # Sort by score (descending)
        ranked_candidates = sorted(candidates, key=lambda x: x["score"], reverse=True)

        return ranked_candidates[:top_k]

    def _batch_predict(self, pairs: List[List[str]], batch_size: int) -> List[float]:
        """Predict in batches for GPU efficiency."""
        all_scores = []

        for i in range(0, len(pairs), batch_size):
            batch = pairs[i : i + batch_size]

            if self.use_amp and self.device == "cuda":
                # Use mixed precision for faster inference
                with torch.cuda.amp.autocast():
                    scores = self.model.predict(batch)
            else:
                scores = self.model.predict(batch)

            all_scores.extend(scores)

        return np.array(all_scores)

    def get_model_info(self) -> Dict:
        """Get model information."""
        return {
            "model_name": self.model_name,
            "device": self.device,
            "max_seq_length": self.max_seq_length,
            "using_amp": getattr(self, "use_amp", False),
        }
