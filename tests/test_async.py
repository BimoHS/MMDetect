"""Tests for async interface."""

import asyncio
import os

import asynctest
import mmcv
import torch

from mmdet.apis import async_inference_detector, init_detector
from mmdet.utils.contextmanagers import concurrent


class AsyncTestCase(asynctest.TestCase):
    use_default_loop = False
    forbid_get_event_loop = True

    TEST_TIMEOUT = int(os.getenv("ASYNCIO_TEST_TIMEOUT", "30"))

    def _run_test_method(self, method):
        result = method()
        if asyncio.iscoroutine(result):
            self.loop.run_until_complete(
                asyncio.wait_for(result, timeout=self.TEST_TIMEOUT))


class MaskRCNNDetector:

    def __init__(self,
                 model_config,
                 checkpoint=None,
                 streamqueue_size=3,
                 device="cuda:0"):

        # build the model and load checkpoint
        self.device = device
        self.model = init_detector(
            model_config, checkpoint=None, device=self.device)
        self.streamqueue = None
        self.streamqueue_size = streamqueue_size

    async def init(self):
        self.streamqueue = asyncio.Queue()
        for _ in range(self.streamqueue_size):
            self.streamqueue.put_nowait(torch.cuda.Stream(device=self.device))

    async def apredict(self, img):
        if isinstance(img, str):
            img = mmcv.imread(img)
        async with concurrent(self.streamqueue):
            result = await async_inference_detector(self.model, img)
        return result


class AsyncInferenceTestCase(AsyncTestCase):

    async def test_simple_inference(self):
        root_dir = os.path.dirname(os.path.dirname(__name__))
        model_config = os.path.join(root_dir,
                                    "configs/mask_rcnn_r50_fpn_1x.py")
        detector = MaskRCNNDetector(model_config)
        await detector.init()
        img_path = os.path.join(root_dir, "demo/demo.jpg")
        await detector.apredict(img_path)
