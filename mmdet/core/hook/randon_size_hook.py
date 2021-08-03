from mmcv.runner.hooks import HOOKS, Hook
import random
from mmcv.runner import get_dist_info

import torch
from torch import distributed as dist


def random_resize(random_size, data_loader, rank, is_distributed, input_size):
    tensor = torch.LongTensor(2).cuda()

    if rank == 0:
        size_factor = input_size[1] * 1. / input_size[0]
        size = random.randint(*random_size)
        size = (int(32 * size), 32 * int(size * size_factor))
        tensor[0] = size[0]
        tensor[1] = size[1]

    if is_distributed:
        dist.barrier()
        dist.broadcast(tensor, 0)

    data_loader.dataset.dynamic_scale = (tensor[0].item(), tensor[1].item())
    return data_loader.dataset.dynamic_scale


@HOOKS.register_module()
class RandomSizeHook(Hook):
    """Change the image size, currently used in YOLOX.

    Args:
        ratio_range (tuple[int]): Random ratio range. It will be multiplied by 32,
            and then change the dataset output image size. Default to (14, 26).
        img_scale (tuple[int]): input image size. Default to (640, 640).
    """
    def __init__(self, ratio_range=(14, 26), img_scale=(640, 640)):
        self.rank, world_size = get_dist_info()
        self.is_distributed = world_size > 1
        self.ratio_range = ratio_range
        self.img_scale = img_scale

    def after_train_iter(self, runner):
        """Change the dataset output image size.
        """
        progress_in_iter = runner.iter
        train_loader = runner.data_loader
        # random resizing
        if self.ratio_range is not None and (progress_in_iter + 1) % self.change_scale_interval == 0:
            random_resize(self.ratio_range, train_loader, self.rank, self.is_distributed, self.img_scale)
