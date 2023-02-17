# Copyright (c) OpenMMLab. All rights reserved.
from typing import List, Tuple

import torch
import torch.nn as nn
from mmcv.cnn.bricks import Swish, build_norm_layer
from mmengine.model import bias_init_with_prob
from torch import Tensor

from mmdet.models.dense_heads.anchor_head import AnchorHead
from mmdet.models.utils import images_to_levels, multi_apply
from mmdet.registry import MODELS
from mmdet.structures.bbox import cat_boxes
from mmdet.utils import (InstanceList, OptConfigType, OptInstanceList,
                         OptMultiConfig, reduce_mean)
from .utils import DepthWiseConvBlock, variance_scaling_trunc


@MODELS.register_module()
class EfficientDetSepBNHead(AnchorHead):
    """EfficientDetHead with separate BN.

    num_classes (int): Number of categories excluding the background
    category. in_channels (int): Number of channels in the input feature map.
    feat_channels (int): Number of hidden channels. stacked_convs (int): Number
    of repetitions of conv norm_cfg (dict): Config dict for normalization
    layer. anchor_generator (dict): Config dict for anchor generator bbox_coder
    (dict): Config of bounding box coder. loss_cls (dict): Config of
    classification loss. loss_bbox (dict): Config of localization loss.
    train_cfg (dict): Training config of anchor head. test_cfg (dict): Testing
    config of anchor head. init_cfg (dict or list[dict], optional):
    Initialization config dict.
    """

    def __init__(self,
                 num_classes: int,
                 num_ins: int,
                 in_channels: int,
                 feat_channels: int,
                 stacked_convs: int = 3,
                 norm_cfg: OptConfigType = dict(
                     type='BN', momentum=1e-2, eps=1e-3),
                 init_cfg: OptMultiConfig = None,
                 **kwargs) -> None:
        self.num_ins = num_ins
        self.stacked_convs = stacked_convs
        self.norm_cfg = norm_cfg
        super().__init__(
            num_classes=num_classes,
            in_channels=in_channels,
            feat_channels=feat_channels,
            init_cfg=init_cfg,
            **kwargs)

    def _init_layers(self) -> None:
        """Initialize layers of the head."""
        self.reg_conv_list = nn.ModuleList()
        self.cls_conv_list = nn.ModuleList()
        for i in range(self.stacked_convs):
            channels = self.in_channels if i == 0 else self.feat_channels
            self.reg_conv_list.append(
                DepthWiseConvBlock(
                    channels, self.feat_channels, apply_norm=False))
            self.cls_conv_list.append(
                DepthWiseConvBlock(
                    channels, self.feat_channels, apply_norm=False))

        self.reg_bn_list = nn.ModuleList([
            nn.ModuleList([
                build_norm_layer(
                    self.norm_cfg, num_features=self.feat_channels)[1]
                for j in range(self.num_ins)
            ]) for i in range(self.stacked_convs)
        ])

        self.cls_bn_list = nn.ModuleList([
            nn.ModuleList([
                build_norm_layer(
                    self.norm_cfg, num_features=self.feat_channels)[1]
                for j in range(self.num_ins)
            ]) for i in range(self.stacked_convs)
        ])

        self.cls_header = DepthWiseConvBlock(
            self.in_channels,
            self.num_base_priors * self.cls_out_channels,
            apply_norm=False)
        self.reg_header = DepthWiseConvBlock(
            self.in_channels, self.num_base_priors * 4, apply_norm=False)
        self.swish = Swish()

    def init_weights(self) -> None:
        """Initialize weights of the head."""
        for m in self.reg_conv_list:
            variance_scaling_trunc(m.depthwise_conv.conv.weight)
            variance_scaling_trunc(m.pointwise_conv.conv.weight)
            nn.init.constant_(m.pointwise_conv.bias, 0.0)
        for m in self.cls_conv_list:
            variance_scaling_trunc(m.depthwise_conv.conv.weight)
            variance_scaling_trunc(m.pointwise_conv.conv.weight)
            nn.init.constant_(m.pointwise_conv.bias, 0.0)
        bias_cls = bias_init_with_prob(0.01)
        variance_scaling_trunc(self.cls_header.depthwise_conv.weight)
        variance_scaling_trunc(self.cls_header.pointwise_conv.weight)
        nn.init.constant_(self.cls_header.pointwise_conv.bias, bias_cls)
        variance_scaling_trunc(self.reg_header.depthwise_conv.weight)
        variance_scaling_trunc(self.reg_header.pointwise_conv.weight)
        nn.init.constant_(self.reg_header.pointwise_conv.bias, 0.0)

    def forward_single_bbox(self, feat: Tensor, level_id: int,
                            i: int) -> Tensor:
        conv_op = self.reg_conv_list[i]
        bn = self.reg_bn_list[i][level_id]

        feat = conv_op(feat)
        feat = bn(feat)
        feat = self.swish(feat)

        return feat

    def forward_single_cls(self, feat: Tensor, level_id: int,
                           i: int) -> Tensor:
        conv_op = self.cls_conv_list[i]
        bn = self.cls_bn_list[i][level_id]

        feat = conv_op(feat)
        feat = bn(feat)
        feat = self.swish(feat)

        return feat

    def forward(self, feats: Tuple[Tensor]) -> tuple:
        cls_scores = []
        bbox_preds = []
        for level_id in range(self.num_ins):
            feat = feats[level_id]
            for i in range(self.stacked_convs):
                feat = self.forward_single_bbox(feat, level_id, i)
            bbox_pred = self.reg_header(feat)
            bbox_preds.append(bbox_pred)
        for level_id in range(self.num_ins):
            feat = feats[level_id]
            for i in range(self.stacked_convs):
                feat = self.forward_single_cls(feat, level_id, i)
            cls_score = self.cls_header(feat)
            cls_scores.append(cls_score)

        return cls_scores, bbox_preds

    def loss_by_feat(
            self,
            cls_scores: List[Tensor],
            bbox_preds: List[Tensor],
            batch_gt_instances: InstanceList,
            batch_img_metas: List[dict],
            batch_gt_instances_ignore: OptInstanceList = None) -> dict:
        """Calculate the loss based on the features extracted by the detection
        head.

        Args:
            cls_scores (list[Tensor]): Box scores for each scale level
                has shape (N, num_anchors * num_classes, H, W).
            bbox_preds (list[Tensor]): Box energies / deltas for each scale
                level with shape (N, num_anchors * 4, H, W).
            batch_gt_instances (list[:obj:`InstanceData`]): Batch of
                gt_instance. It usually includes ``bboxes`` and ``labels``
                attributes.
            batch_img_metas (list[dict]): Meta information of each image, e.g.,
                image size, scaling factor, etc.
            batch_gt_instances_ignore (list[:obj:`InstanceData`], optional):
                Batch of gt_instances_ignore. It includes ``bboxes`` attribute
                data that is ignored during training and testing.
                Defaults to None.

        Returns:
            dict: A dictionary of loss components.
        """
        featmap_sizes = [featmap.size()[-2:] for featmap in cls_scores]
        assert len(featmap_sizes) == self.prior_generator.num_levels

        device = cls_scores[0].device

        anchor_list, valid_flag_list = self.get_anchors(
            featmap_sizes, batch_img_metas, device=device)
        cls_reg_targets = self.get_targets(
            anchor_list,
            valid_flag_list,
            batch_gt_instances,
            batch_img_metas,
            batch_gt_instances_ignore=batch_gt_instances_ignore)
        (labels_list, label_weights_list, bbox_targets_list, bbox_weights_list,
         avg_factor) = cls_reg_targets

        # anchor number of multi levels
        num_level_anchors = [anchors.size(0) for anchors in anchor_list[0]]
        # concat all level anchors and flags to a single tensor
        concat_anchor_list = []
        for i in range(len(anchor_list)):
            concat_anchor_list.append(cat_boxes(anchor_list[i]))
        all_anchor_list = images_to_levels(concat_anchor_list,
                                           num_level_anchors)

        avg_factor = reduce_mean(
            torch.tensor(avg_factor, dtype=torch.float,
                         device=device)).clamp_(min=1).item()
        losses_cls, losses_bbox = multi_apply(
            self.loss_by_feat_single,
            cls_scores,
            bbox_preds,
            all_anchor_list,
            labels_list,
            label_weights_list,
            bbox_targets_list,
            bbox_weights_list,
            avg_factor=avg_factor)
        return dict(loss_cls=losses_cls, loss_bbox=losses_bbox)
