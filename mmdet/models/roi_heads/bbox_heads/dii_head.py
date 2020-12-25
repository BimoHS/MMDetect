import torch
import torch.nn as nn
from mmcv.cnn import (bias_init_with_prob, build_activation_layer,
                      build_norm_layer)
from mmcv.runner import auto_fp16, force_fp32

from mmdet.core import multi_apply
from mmdet.models.builder import HEADS, build_loss
from mmdet.models.dense_heads.atss_head import reduce_mean
from mmdet.models.losses import accuracy
from mmdet.models.utils import FFN, MultiheadAttention, build_transformer
from .bbox_head import BBoxHead


@HEADS.register_module()
class DIIHead(BBoxHead):
    r"""Dynamic Instance Interactive Head for `Sparse R-CNN: End-to-End Object
    Detection with Learnable Proposals <https://arxiv.org/abs/2011.12450>`_

    Args:
        num_classes (int): Number of class in dataset. Defaults to 80.
        num_ffn_fcs (int): The number of fully-connected layers in FFNs.
            Defaults to 2.
        num_heads (int): The hidden dimension of FFNs. Defaults to 8.
        num_cls_fcs (int): The number of fully-connected layers in
            classification subnet. Defaults to 1.
        num_reg_fcs (int): The number of fully-connected layers in
            regression subnet. Defaults to 3.
        feedforward_channels (int): The hidden dimension of FFNs.
            Defaults to 2048
        in_channels (int): Hidden_channels of MultiheadAttention.
            Defaults to 256.
        dropout (float): Probability of drop the channel. Defaults to 0.0
        ffn_act_cfg (dict): The activation config for FFNs.
        dynamic_conv_cfg (dict): The convolution config for DynamicConv.
        loss_iou (dict): The config for iou or giou loss.

    """

    def __init__(self,
                 num_classes=80,
                 num_ffn_fcs=2,
                 num_heads=8,
                 num_cls_fcs=1,
                 num_reg_fcs=3,
                 feedforward_channels=2048,
                 in_channels=256,
                 dropout=0.0,
                 ffn_act_cfg=dict(type='ReLU', inplace=True),
                 dynamic_conv_cfg=dict(
                     type='DynamicConv',
                     in_channels=256,
                     feat_channels=64,
                     out_channels=256,
                     input_feat_shape=7,
                     act_cfg=dict(type='ReLU', inplace=True),
                     norm_cfg=dict(type='LN')),
                 loss_iou=dict(type='GIoULoss', loss_weight=2.0),
                 **kwargs):
        super(DIIHead, self).__init__(
            num_classes=num_classes,
            reg_decoded_bbox=True,
            reg_class_agnostic=True,
            **kwargs)
        assert self.reg_class_agnostic is True
        self.loss_iou = build_loss(loss_iou)
        self.in_channels = in_channels
        self.fp16_enabled = False
        self.self_attention = MultiheadAttention(in_channels, num_heads,
                                                 dropout)
        self.self_attention_norm = build_norm_layer(
            dict(type='LN'), in_channels)[1]

        self.instance_interactive_conv = build_transformer(dynamic_conv_cfg)
        self.instance_interactive_conv_dropout = nn.Dropout(dropout)
        self.instance_interactive_conv_norm = build_norm_layer(
            dict(type='LN'), in_channels)[1]

        self.ffn = FFN(
            in_channels,
            feedforward_channels,
            num_ffn_fcs,
            act_cfg=ffn_act_cfg,
            dropout=dropout)
        self.ffn_norm = build_norm_layer(dict(type='LN'), in_channels)[1]

        self.cls_fcs = nn.ModuleList()
        for _ in range(num_cls_fcs):
            self.cls_fcs.append(
                nn.Linear(in_channels, in_channels, bias=False))
            self.cls_fcs.append(
                build_norm_layer(dict(type='LN'), in_channels)[1])
            self.cls_fcs.append(
                build_activation_layer(dict(type='ReLU', inplace=True)))

        # over load the self.fc_cls in BBoxHead
        if self.loss_cls.use_sigmoid:
            self.fc_cls = nn.Linear(in_channels, self.num_classes)
        else:
            self.fc_cls = nn.Linear(in_channels, self.num_classes + 1)

        self.reg_fcs = nn.ModuleList()
        for _ in range(num_reg_fcs):
            self.reg_fcs.append(
                nn.Linear(in_channels, in_channels, bias=False))
            self.reg_fcs.append(
                build_norm_layer(dict(type='LN'), in_channels)[1])
            self.reg_fcs.append(
                build_activation_layer(dict(type='ReLU', inplace=True)))
        # over load the self.fc_cls in BBoxHead
        self.fc_reg = nn.Linear(in_channels, 4)

    def init_weights(self):
        """Use xavier initialization for all weight parameter and set
        classification head bias as a specific value when use focal loss."""
        for p in self.parameters():
            if p.dim() > 1:
                nn.init.xavier_uniform_(p)
        if self.loss_cls.use_sigmoid:
            bias_init = bias_init_with_prob(0.01)
            nn.init.constant_(self.fc_cls.bias, bias_init)

    @auto_fp16()
    def forward(self, roi_feat, proposal_feat):
        """Forward function of Dynamic Instance Interactive Head.

        Args:
            roi_feat (Tensor): Roi-pooling features with shape
                (num_proposals, feature_dimensions, pooling_h , pooling_w).
            proposal_feat: Intermediate feature get from diihead in
                last stage, has shape
                (batch_size, num_proposals, feature_dimensions)

          Returns:
                tuple: Usually a tuple of classification scores \
                    and bbox prediction and a intermediate feature.

                    - cls_scores (Tensor): Classification scores for \
                        all proposals, has shape \
                        (batch_size, num_proposals, num_classes)
                    - bbox_preds (Tensor): Box energies / deltas for \
                        all proposals, has shape \
                        (batch_size, num_proposals, 4)
                    - obj_feat (Tensor): Object feature before classification \
                        and regression subnet, has shape \
                        (batch_size, num_proposal, feature_dimensions) \
        """
        N, num_proposals = proposal_feat.shape[:2]
        # Self attention
        proposal_feat = proposal_feat.view(N, num_proposals,
                                           self.in_channels).permute(1, 0, 2)
        proposal_feat = self.self_attention_norm(
            self.self_attention(proposal_feat))
        # instance interactive
        proposal_feat = proposal_feat.view(
            num_proposals, N,
            self.in_channels).permute(1, 0, 2).reshape(1, N * num_proposals,
                                                       self.in_channels)
        roi_feat = roi_feat.view(N * num_proposals, self.in_channels,
                                 -1).permute(2, 0, 1)
        proposal_feat_iic = self.instance_interactive_conv(
            proposal_feat, roi_feat)
        proposal_feat = proposal_feat + self.instance_interactive_conv_dropout(
            proposal_feat_iic)
        obj_feat = self.instance_interactive_conv_norm(proposal_feat)
        # FFN
        obj_feat = self.ffn_norm(self.ffn(obj_feat))
        fc_feat = obj_feat.transpose(0, 1).reshape(N * num_proposals, -1)
        cls_feat = fc_feat.clone()
        reg_feat = fc_feat.clone()

        for cls_layer in self.cls_fcs:
            cls_feat = cls_layer(cls_feat)
        for reg_layer in self.reg_fcs:
            reg_feat = reg_layer(reg_feat)

        cls_score = self.fc_cls(cls_feat).view(N, num_proposals, -1)
        bbox_delta = self.fc_reg(reg_feat).view(N, num_proposals, -1)

        return cls_score, bbox_delta, obj_feat.view(N, num_proposals, -1)

    @force_fp32(apply_to=('cls_score', 'bbox_pred'))
    def loss(self,
             cls_score,
             bbox_pred,
             labels,
             label_weights,
             bbox_targets,
             bbox_weights,
             avg_factor=None,
             imgs_whwh=None,
             reduction_override=None):
        """"Loss function of DIIHead, get loss of all images.

        Args:
            cls_score (Tensor): Classification prediction
                results of all class, has shape
                (batch_size * num_proposals_single_image, num_classes)
            bbox_pred (Tensor): Regression prediction results,
                has shape
                (batch_size * num_proposals_single_image, 4), the last
                dimension 4 represents [tl_x, tl_y, br_x, br_y].
            labels (Tensor): Label of each proposals, has shape
                (batch_size * num_proposals_single_image
            label_weights (Tensor): Classification loss
                weight of each proposals, has shape
                (batch_size * num_proposals_single_image
            bbox_targets (Tensor): Regression targets of each
                proposals, has shape
                (batch_size * num_proposals_single_image, 4),
                the last dimension 4 represents
                [tl_x, tl_y, br_x, br_y].
            bbox_weights (Tensor): Regression loss weight of each
                proposals's coordinate, has shape
                (batch_size * num_proposals_single_image, 4),
            avg_factor (float): Used in normalized regression
                and classification loss
            imgs_whwh (Tensor): imgs_whwh (Tensor): Tensor with\
                shape (batch_size, num_proposals, 4), the last
                dimension means
                [img_width,img_height, img_width, img_height].
            reduction_override (str, optional): The reduction
                method used to override the original reduction
                method of the loss. Options are "none",
                "mean" and "sum". Defaults to None,

            Returns:
                dict[str, Tensor]: Dictionary of loss components
        """
        losses = dict()
        bg_class_ind = self.num_classes
        # note in spare rcnn num_gt == num_pos
        pos_inds = (labels >= 0) & (labels < bg_class_ind)
        num_pos = pos_inds.sum().float()
        avg_factor = reduce_mean(num_pos)
        if cls_score is not None:
            if cls_score.numel() > 0:
                losses['loss_cls'] = self.loss_cls(
                    cls_score,
                    labels,
                    label_weights,
                    avg_factor=avg_factor,
                    reduction_override=reduction_override)
                losses['pos_acc'] = accuracy(cls_score[pos_inds],
                                             labels[pos_inds])
        if bbox_pred is not None:
            # 0~self.num_classes-1 are FG, self.num_classes is BG
            # do not perform bounding box regression for BG anymore.
            if pos_inds.any():
                pos_bbox_pred = bbox_pred.reshape(bbox_pred.size(0),
                                                  4)[pos_inds.type(torch.bool)]
                imgs_whwh = imgs_whwh.reshape(bbox_pred.size(0),
                                              4)[pos_inds.type(torch.bool)]
                losses['loss_bbox'] = self.loss_bbox(
                    pos_bbox_pred / imgs_whwh,
                    bbox_targets[pos_inds.type(torch.bool)] / imgs_whwh,
                    bbox_weights[pos_inds.type(torch.bool)],
                    avg_factor=avg_factor,
                )
                losses['loss_iou'] = self.loss_iou(
                    pos_bbox_pred,
                    bbox_targets[pos_inds.type(torch.bool)],
                    bbox_weights[pos_inds.type(torch.bool)],
                    avg_factor=avg_factor,
                )
            else:
                losses['loss_bbox'] = bbox_pred.sum() * 0
                losses['loss_iou'] = bbox_pred.sum() * 0
        return losses

    def _get_target_single(self, pos_inds, neg_inds, pos_bboxes, neg_bboxes,
                           pos_gt_bboxes, pos_gt_labels, cfg):
        """Almost the same as the implementation in bbox_head, we add pos_inds
        and neg_inds to select positive and negative samples instead of
        selecting first num_pos as positive samples.

        Args:
            pos_inds (Tensor): The length is equal to the
                positive sample numbers, contains all index
                of positive sample in origin proposal set.
            neg_inds (Tensor): The length is equal to the
                negative sample numbers, contains all index
                of negative sample in origin proposal set.
        """
        num_pos = pos_bboxes.size(0)
        num_neg = neg_bboxes.size(0)
        num_samples = num_pos + num_neg

        # original implementation uses new_zeros since BG are set to be 0
        # now use empty & fill because BG cat_id = num_classes,
        # FG cat_id = [0, num_classes-1]
        labels = pos_bboxes.new_full((num_samples, ),
                                     self.num_classes,
                                     dtype=torch.long)
        label_weights = pos_bboxes.new_zeros(num_samples)
        bbox_targets = pos_bboxes.new_zeros(num_samples, 4)
        bbox_weights = pos_bboxes.new_zeros(num_samples, 4)
        if num_pos > 0:
            labels[pos_inds] = pos_gt_labels
            pos_weight = 1.0 if cfg.pos_weight <= 0 else cfg.pos_weight
            label_weights[pos_inds] = pos_weight
            if not self.reg_decoded_bbox:
                pos_bbox_targets = self.bbox_coder.encode(
                    pos_bboxes, pos_gt_bboxes)
            else:
                pos_bbox_targets = pos_gt_bboxes
            bbox_targets[pos_inds, :] = pos_bbox_targets
            bbox_weights[pos_inds, :] = 1
        if num_neg > 0:
            label_weights[neg_inds] = 1.0

        return labels, label_weights, bbox_targets, bbox_weights

    def get_targets(self,
                    sampling_results,
                    gt_bboxes,
                    gt_labels,
                    rcnn_train_cfg,
                    concat=True):
        """Almost the same as the implementation in bbox_head, we passed
        additional parameters pos_inds_list and neg_inds_list to
        `_get_target_single` function."""
        pos_inds_list = [res.pos_inds for res in sampling_results]
        neg_inds_list = [res.neg_inds for res in sampling_results]
        pos_bboxes_list = [res.pos_bboxes for res in sampling_results]
        neg_bboxes_list = [res.neg_bboxes for res in sampling_results]
        pos_gt_bboxes_list = [res.pos_gt_bboxes for res in sampling_results]
        pos_gt_labels_list = [res.pos_gt_labels for res in sampling_results]
        labels, label_weights, bbox_targets, bbox_weights = multi_apply(
            self._get_target_single,
            pos_inds_list,
            neg_inds_list,
            pos_bboxes_list,
            neg_bboxes_list,
            pos_gt_bboxes_list,
            pos_gt_labels_list,
            cfg=rcnn_train_cfg)
        if concat:
            labels = torch.cat(labels, 0)
            label_weights = torch.cat(label_weights, 0)
            bbox_targets = torch.cat(bbox_targets, 0)
            bbox_weights = torch.cat(bbox_weights, 0)
        return labels, label_weights, bbox_targets, bbox_weights
