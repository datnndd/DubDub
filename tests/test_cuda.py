import pytest

torch = pytest.importorskip("torch", reason="torch not installed")

# Check if CUDA is available
print(f"\nCUDA available: {'Yes' if torch.cuda.is_available() else 'No'}")

# If CUDA is available, check cuDNN
if torch.cuda.is_available():
    print(f"\ncuDNN available: {'Yes' if torch.backends.cudnn.is_available() else 'No'}")
    print(f"\ncuDNN version: {torch.backends.cudnn.version()}\n\n")


def test_cuda_available():
    # CUDA is not strictly required, print information only
    has_cuda = torch.cuda.is_available()
    print(f"CUDA available: {has_cuda}")
