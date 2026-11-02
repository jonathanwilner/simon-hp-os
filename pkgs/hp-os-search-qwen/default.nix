{ pkgs }:
let
  model = pkgs.fetchurl {
    name = "Qwen3.5-0.8B-Q4_0.gguf";
    url = "https://huggingface.co/ggml-org/Qwen3.5-0.8B-GGUF/resolve/807dfd9a6fadbf703207aac3bfb0b2b3040d077c/Qwen3.5-0.8B-Q4_0.gguf";
    sha256 = "57d1997790d1744fba5b40a7317df71ea5e2acee28c47e78f0cce39c0703f8cf";
    meta.license = pkgs.lib.licenses.asl20;
  };
  server = pkgs.llama-cpp.override {
    cudaSupport = false;
    rocmSupport = false;
    vulkanSupport = false;
    metalSupport = false;
    openclSupport = false;
  };
in pkgs.writeShellApplication {
  name = "hp-os-search-qwen";
  runtimeInputs = [ server ];
  text = ''
    export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2
    exec llama-server \
      --model ${model} \
      --alias hp-os-search-qwen \
      --host 127.0.0.1 --port 30002 \
      --ctx-size 2048 --threads 2 --threads-batch 2 \
      --parallel 1 --n-gpu-layers 0 \
      --jinja --reasoning off \
      --no-webui "$@"
  '';
  passthru = { inherit model server; };
  meta.description = "Small CPU-only Qwen service for local desktop search query expansion";
}
