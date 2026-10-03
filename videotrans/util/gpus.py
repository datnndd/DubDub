# 1. Get and cache the number of available GPUs
# 2. Get available CUDA device index
# 3. Check if MacOSX supports MPS
import platform
from videotrans.configure.config import app_cfg,settings,logger



# Get available GPU count and cache in config.NVIDIA_GPU_NUMS, 0 = no GPU available
#
# force_cpu: unused parameter
#   True forces CPU usage (i.e. force treat as no GPU)
def getset_gpu(force_cpu=False) -> int:
    if force_cpu:
        return 0
    # -1 means not retrieved yet
    if app_cfg.NVIDIA_GPU_NUMS > -1:
        return app_cfg.NVIDIA_GPU_NUMS
    
    if platform.system() == 'Darwin':
        app_cfg.NVIDIA_GPU_NUMS = 0
        return 0
        
    import torch
    # No GPU available
    app_cfg.NVIDIA_GPU_NUMS = 0 if not torch.cuda.is_available() else torch.cuda.device_count()
    logger.debug(f'可用 Nvidia 显卡数: {app_cfg.NVIDIA_GPU_NUMS}')
    return app_cfg.NVIDIA_GPU_NUMS


# Get index of currently available CUDA device
# return -1: no available GPU, force caller to use CPU or MPS
# >=0: GPU device index
def get_cudaX() -> int:
    if platform.system() == 'Darwin':
        return -1
    try:
        # Available GPU count has not been initialized yet
        if app_cfg.NVIDIA_GPU_NUMS == -1:
            getset_gpu()

        if app_cfg.NVIDIA_GPU_NUMS == 0:
            # No GPU available
            return -1

        if app_cfg.NVIDIA_GPU_NUMS == 1 or not bool(settings.get('multi_gpus', False)):
            # Only one card available or multi-GPU is not enabled
            return 0

        import torch
        # If free VRAM > 24GB exists on default card, return and use it directly
        free_g = (1024 ** 3) * 24
        _default_index = 0
        _default_free, _ = torch.cuda.mem_get_info(_default_index)
        if _default_free > free_g:
            return 0

        # Sequentially check for cards with > 24GB free VRAM; if none, return the card with the largest free VRAM
        for i in range(1, app_cfg.NVIDIA_GPU_NUMS):
            free_bytes, _ = torch.cuda.mem_get_info(i)
            if free_bytes > free_g:
                logger.debug(f'[使用第{i}块显卡],可用显存为 {free_bytes / (1024 ** 3)}GB')
                return i
            if free_bytes > _default_free:
                _default_free = free_bytes
                _default_index = i
        logger.debug(f'[使用第{_default_index}块显卡],可用显存为 {_default_free / (1024 ** 3)}GB')
        return _default_index
    except Exception as e:
        logger.exception(f'获取当前可用显卡索引失败,返回第0块显卡:{e}', exc_info=True)
        return 0


# Check if MacOSX supports MPS
# mps: supported
# cpu: not supported, must use CPU
def mps_or_cpu() -> str:
    if platform.system() != 'Darwin':
        return 'cpu'
    import torch
    if torch.backends.mps.is_built() and torch.backends.mps.is_available():
        return 'mps'
    return 'cpu'
