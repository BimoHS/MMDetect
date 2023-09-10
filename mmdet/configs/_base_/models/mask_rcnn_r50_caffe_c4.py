# Copyright (c) OpenMMLab. All rights reserved.
from mmcv.ops import RoIAlign, nms
from mmengine.model.weight_init import PretrainedInit
from torch.nn import BatchNorm2d

from mmdet.models.backbones.resnet import ResNet
from mmdet.models.data_preprocessors.data_preprocessor import \
    DetDataPreprocessor
from mmdet.models.dense_heads.rpn_head import RPNHead
from mmdet.models.detectors.mask_rcnn import MaskRCNN
from mmdet.models.layers import ResLayer
from mmdet.models.losses.cross_entropy_loss import CrossEntropyLoss
from mmdet.models.losses.smooth_l1_loss import L1Loss
from mmdet.models.roi_heads.bbox_heads.bbox_head import BBoxHead
from mmdet.models.roi_heads.mask_heads.fcn_mask_head import FCNMaskHead
from mmdet.models.roi_heads.roi_extractors.single_level_roi_extractor import \
    SingleRoIExtractor
from mmdet.models.roi_heads.standard_roi_head import StandardRoIHead
from mmdet.models.task_modules.assigners.max_iou_assigner import MaxIoUAssigner
from mmdet.models.task_modules.coders.delta_xywh_bbox_coder import \
    DeltaXYWHBBoxCoder
from mmdet.models.task_modules.prior_generators.anchor_generator import \
    AnchorGenerator
from mmdet.models.task_modules.samplers.random_sampler import RandomSampler

# model settings
norm_cfg = dict(type=BatchNorm2d, requires_grad=False)
# model settings
model = dict(
    type=MaskRCNN,
    data_preprocessor=dict(
        type=DetDataPreprocessor,
        mean=[103.530, 116.280, 123.675],
        std=[1.0, 1.0, 1.0],
        bgr_to_rgb=False,
        pad_mask=True,
        pad_size_divisor=32),
    backbone=dict(
        type=ResNet,
        depth=50,
        num_stages=3,
        strides=(1, 2, 2),
        dilations=(1, 1, 1),
        out_indices=(2, ),
        frozen_stages=1,
        norm_cfg=dict(type=BatchNorm2d, requires_grad=True),
        norm_eval=True,
        style='caffe',
        init_cfg=dict(
            type=PretrainedInit,
            checkpoint='open-mmlab://detectron2/resnet50_caffe')),
    # neck=dict(
    #     type=FPN,
    #     in_channels=[256, 512, 1024, 2048],
    #     out_channels=256,
    #     num_outs=5),
    rpn_head=dict(
        type=RPNHead,
        in_channels=1024,
        feat_channels=1024,
        anchor_generator=dict(
            type=AnchorGenerator,
            scales=[2, 4, 8, 16, 32],
            ratios=[0.5, 1.0, 2.0],
            strides=[16]),
        bbox_coder=dict(
            type=DeltaXYWHBBoxCoder,
            target_means=[.0, .0, .0, .0],
            target_stds=[1.0, 1.0, 1.0, 1.0]),
        loss_cls=dict(
            type=CrossEntropyLoss, use_sigmoid=True, loss_weight=1.0),
        loss_bbox=dict(type=L1Loss, loss_weight=1.0)),
    roi_head=dict(
        type=StandardRoIHead,
        shared_head=dict(
            type=ResLayer,
            depth=50,
            stage=3,
            stride=2,
            dilation=1,
            style='caffe',
            norm_cfg=norm_cfg,
            norm_eval=True),
        bbox_roi_extractor=dict(
            type=SingleRoIExtractor,
            roi_layer=dict(type=RoIAlign, output_size=14, sampling_ratio=0),
            out_channels=1024,
            featmap_strides=[16]),
        bbox_head=dict(
            type=BBoxHead,
            with_avg_pool=True,
            roi_feat_size=7,
            in_channels=2048,
            num_classes=80,
            bbox_coder=dict(
                type=DeltaXYWHBBoxCoder,
                target_means=[0., 0., 0., 0.],
                target_stds=[0.1, 0.1, 0.2, 0.2]),
            reg_class_agnostic=False,
            loss_cls=dict(
                type=CrossEntropyLoss, use_sigmoid=False, loss_weight=1.0),
            loss_bbox=dict(type=L1Loss, loss_weight=1.0)),
        mask_roi_extractor=None,
        mask_head=dict(
            type=FCNMaskHead,
            num_convs=0,
            in_channels=2048,
            conv_out_channels=256,
            num_classes=80,
            loss_mask=dict(
                type=CrossEntropyLoss, use_mask=True, loss_weight=1.0))),
    # model training and testing settings
    train_cfg=dict(
        rpn=dict(
            assigner=dict(
                type=MaxIoUAssigner,
                pos_iou_thr=0.7,
                neg_iou_thr=0.3,
                min_pos_iou=0.3,
                match_low_quality=True,
                ignore_iof_thr=-1),
            sampler=dict(
                type=RandomSampler,
                num=256,
                pos_fraction=0.5,
                neg_pos_ub=-1,
                add_gt_as_proposals=False),
            allowed_border=0,
            pos_weight=-1,
            debug=False),
        rpn_proposal=dict(
            nms_pre=12000,
            max_per_img=2000,
            nms=dict(type=nms, iou_threshold=0.7),
            min_bbox_size=0),
        rcnn=dict(
            assigner=dict(
                type=MaxIoUAssigner,
                pos_iou_thr=0.5,
                neg_iou_thr=0.5,
                min_pos_iou=0.5,
                match_low_quality=False,
                ignore_iof_thr=-1),
            sampler=dict(
                type=RandomSampler,
                num=512,
                pos_fraction=0.25,
                neg_pos_ub=-1,
                add_gt_as_proposals=True),
            mask_size=14,
            pos_weight=-1,
            debug=False)),
    test_cfg=dict(
        rpn=dict(
            nms_pre=6000,
            max_per_img=1000,
            nms=dict(type=nms, iou_threshold=0.7),
            min_bbox_size=0),
        rcnn=dict(
            score_thr=0.05,
            nms=dict(type=nms, iou_threshold=0.5),
            max_per_img=100,
            mask_thr_binary=0.5)))
