import time
import torch


def main() -> None:
    print("torch:", torch.__version__)
    print("hip:", getattr(torch.version, "hip", None))
    assert torch.cuda.is_available(), "No GPU visible to PyTorch (ROCm build expected)"
    print("device:", torch.cuda.get_device_name(0))
    n = 8192
    a = torch.randn(n, n, device="cuda", dtype=torch.float16)
    b = torch.randn(n, n, device="cuda", dtype=torch.float16)
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(10):
        a @ b
    torch.cuda.synchronize()
    dt = time.perf_counter() - t0
    tflops = 10 * 2 * n**3 / dt / 1e12
    print(f"matmul fp16 {n}x{n} x10: {dt:.3f}s  ~{tflops:.1f} TFLOPS")


if __name__ == "__main__":
    main()
